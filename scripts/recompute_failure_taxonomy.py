#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from graph_agent_automated.domain.models import CaseExecution, EvaluationSummary, JudgeVote
from graph_agent_automated.infrastructure.evaluation.failure_taxonomy import (
    build_failure_taxonomy,
    get_default_failure_taxonomy_rules,
    load_failure_taxonomy_rules,
)
from graph_agent_automated.infrastructure.evaluation.failure_taxonomy_report import (
    analyze_failure_taxonomy_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute failure taxonomy from case reports with configurable rules",
    )
    parser.add_argument("--records-path", required=True, help="Path to manual parity records.json")
    parser.add_argument(
        "--rules-path",
        default="docs/benchmarks/failure_taxonomy_rules_v1.json",
        help="Failure taxonomy rules JSON path (empty string means built-in default)",
    )
    parser.add_argument(
        "--failure-margin-override",
        type=float,
        default=None,
        help="Optional failure margin override for recomputation",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Output report path (default: same dir as records/recomputed_failure_taxonomy.json)",
    )
    parser.add_argument(
        "--write-records-path",
        default="",
        help="Optional path to write records with recomputed failure_taxonomy",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _to_case_execution(row: dict[str, Any]) -> CaseExecution:
    votes: list[JudgeVote] = []
    raw_votes = row.get("judge_votes")
    if isinstance(raw_votes, list):
        for vote_row in raw_votes:
            if not isinstance(vote_row, dict):
                continue
            votes.append(
                JudgeVote(
                    judge_name=str(vote_row.get("judge_name") or ""),
                    score=float(vote_row.get("score") or 0.0),
                    rationale=str(vote_row.get("rationale") or ""),
                )
            )

    return CaseExecution(
        case_id=str(row.get("case_id") or ""),
        question=str(row.get("question") or ""),
        expected=str(row.get("expected") or ""),
        output=str(row.get("output") or ""),
        score=float(row.get("score") or 0.0),
        rationale=str(row.get("rationale") or ""),
        latency_ms=float(row.get("latency_ms") or 0.0),
        token_cost=float(row.get("token_cost") or 0.0),
        confidence=float(row.get("confidence") or 0.0),
        judge_votes=votes,
    )


def _to_summary(cases: list[CaseExecution], split: str) -> EvaluationSummary:
    if cases:
        mean_score = mean([case.score for case in cases])
        mean_latency = mean([case.latency_ms for case in cases])
        mean_cost = mean([case.token_cost for case in cases])
    else:
        mean_score = 0.0
        mean_latency = 0.0
        mean_cost = 0.0
    return EvaluationSummary(
        blueprint_id="recompute",
        mean_score=mean_score,
        mean_latency_ms=mean_latency,
        mean_token_cost=mean_cost,
        total_cases=len(cases),
        reflection=f"recomputed split={split}",
        split=split,
        case_results=cases,
    )


def _load_case_report(auto_artifact_path: str) -> dict[str, Any]:
    workflow_path = Path(auto_artifact_path).expanduser().resolve()
    case_report_path = workflow_path.parent / "manual_parity_case_report.json"
    if not case_report_path.exists() or not case_report_path.is_file():
        raise ValueError(f"case report file not found: {case_report_path}")
    payload = _read_json(case_report_path)
    if not isinstance(payload, dict):
        raise ValueError(f"case report payload must be object: {case_report_path}")
    return payload


def main() -> None:
    args = parse_args()
    records_path = Path(args.records_path).expanduser().resolve()
    if not records_path.exists() or not records_path.is_file():
        raise ValueError(f"records file not found: {records_path}")

    records = _read_json(records_path)
    if not isinstance(records, list):
        raise ValueError("records payload must be a JSON list")

    if args.rules_path.strip():
        rules = load_failure_taxonomy_rules(args.rules_path)
    else:
        rules = get_default_failure_taxonomy_rules()

    recomputed_records: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for row in records:
        if not isinstance(row, dict):
            continue
        row_copy = dict(row)
        auto_artifact_path = str(row.get("auto_artifact_path") or "").strip()
        if not auto_artifact_path:
            warnings.append(
                {
                    "run_id": str(row.get("run_id") or ""),
                    "reason": "missing auto_artifact_path",
                }
            )
            recomputed_records.append(row_copy)
            continue

        try:
            case_report = _load_case_report(auto_artifact_path)
            auto_raw_cases = case_report.get("auto_cases")
            manual_raw_cases = case_report.get("manual_cases")
            if not isinstance(auto_raw_cases, list) or not isinstance(manual_raw_cases, list):
                raise ValueError("case report missing auto_cases/manual_cases arrays")

            auto_cases = [_to_case_execution(item) for item in auto_raw_cases if isinstance(item, dict)]
            manual_cases = [_to_case_execution(item) for item in manual_raw_cases if isinstance(item, dict)]
            auto_eval = _to_summary(auto_cases, split=str(case_report.get("split") or "test"))
            manual_eval = _to_summary(manual_cases, split=str(case_report.get("split") or "test"))

            failure_margin = (
                float(args.failure_margin_override)
                if args.failure_margin_override is not None
                else float(row.get("parity_margin") or 0.0)
            )
            recomputed_taxonomy = build_failure_taxonomy(
                auto_eval=auto_eval,
                manual_eval=manual_eval,
                failure_margin=failure_margin,
                rules=rules,
            )
            row_copy["failure_taxonomy"] = recomputed_taxonomy
            recomputed_records.append(row_copy)
        except Exception as exc:
            warnings.append(
                {
                    "run_id": str(row.get("run_id") or ""),
                    "task_id": str(row.get("task_id") or ""),
                    "seed": row.get("seed"),
                    "reason": str(exc),
                }
            )
            recomputed_records.append(row_copy)

    original_analysis = analyze_failure_taxonomy_records(
        [row for row in records if isinstance(row, dict)],
    )
    recomputed_analysis = analyze_failure_taxonomy_records(recomputed_records)

    output_payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "rules_id": rules.rules_id,
        "rules_version": rules.version,
        "records_path": str(records_path),
        "warnings": warnings,
        "original_analysis": original_analysis,
        "recomputed_analysis": recomputed_analysis,
    }

    output_path = (
        Path(args.output_path).expanduser().resolve()
        if args.output_path.strip()
        else records_path.parent / "recomputed_failure_taxonomy.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    if args.write_records_path.strip():
        records_out_path = Path(args.write_records_path).expanduser().resolve()
        records_out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(records_out_path, "w", encoding="utf-8") as f:
            json.dump(recomputed_records, f, ensure_ascii=False, indent=2)
        print(f"recomputed_records: {records_out_path}")

    print(f"rules={rules.rules_id}@{rules.version} warnings={len(warnings)}")
    print(f"report: {output_path}")


if __name__ == "__main__":
    main()
