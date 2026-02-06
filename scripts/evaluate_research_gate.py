#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from graph_agent_automated.infrastructure.evaluation.research_gate import (
    evaluate_research_gate,
    load_research_gate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate parity artifacts against a fixed research gate",
    )
    parser.add_argument(
        "--records-path",
        required=True,
        help="Path to manual parity records.json",
    )
    parser.add_argument(
        "--parity-stats-path",
        default="",
        help="Optional parity_stats.json path (default: same dir as records)",
    )
    parser.add_argument(
        "--failure-taxonomy-path",
        default="",
        help="Optional failure_taxonomy_summary.json path (default: same dir as records)",
    )
    parser.add_argument(
        "--gate-spec-path",
        default="docs/benchmarks/research_gate_v1.json",
        help="Research gate JSON path",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Optional output report path (default: same dir as records/gate_report.json)",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    args = parse_args()
    records_path = Path(args.records_path).expanduser().resolve()
    if not records_path.exists() or not records_path.is_file():
        raise ValueError(f"records file not found: {records_path}")

    base_dir = records_path.parent
    parity_stats_path = (
        Path(args.parity_stats_path).expanduser().resolve()
        if args.parity_stats_path.strip()
        else base_dir / "parity_stats.json"
    )
    failure_taxonomy_path = (
        Path(args.failure_taxonomy_path).expanduser().resolve()
        if args.failure_taxonomy_path.strip()
        else base_dir / "failure_taxonomy_summary.json"
    )
    output_path = (
        Path(args.output_path).expanduser().resolve()
        if args.output_path.strip()
        else base_dir / "gate_report.json"
    )

    gate = load_research_gate(args.gate_spec_path)
    records = _read_json(records_path)
    parity_stats = _read_json(parity_stats_path)
    failure_taxonomy_summary = _read_json(failure_taxonomy_path)

    if not isinstance(records, list):
        raise ValueError("records.json must be a list")
    if not isinstance(parity_stats, dict):
        raise ValueError("parity_stats.json must be an object")
    if not isinstance(failure_taxonomy_summary, dict):
        raise ValueError("failure_taxonomy_summary.json must be an object")

    report = evaluate_research_gate(
        records=records,
        parity_stats=parity_stats,
        failure_taxonomy_summary=failure_taxonomy_summary,
        gate=gate,
    )
    report["generated_at"] = datetime.utcnow().isoformat() + "Z"
    report["input"] = {
        "records_path": str(records_path),
        "parity_stats_path": str(parity_stats_path),
        "failure_taxonomy_path": str(failure_taxonomy_path),
        "gate_spec_path": str(Path(args.gate_spec_path).expanduser().resolve()),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    status = "PASS" if report["gate_passed"] else "FAIL"
    print(f"[{status}] gate={report['gate_id']} version={report['version']}")
    for check in report["checks"]:
        flag = "ok" if check["passed"] else "x"
        print(
            " - [{flag}] {name}: observed={obs:.6f} {op} threshold={th:.6f}".format(
                flag=flag,
                name=check["name"],
                obs=float(check["observed"]),
                op=check["operator"],
                th=float(check["threshold"]),
            )
        )
    print(f"report: {output_path}")

    if not report["gate_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
