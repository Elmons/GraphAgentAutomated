#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from graph_agent_automated.infrastructure.evaluation.experiment_arm_compare import (
    analyze_arm_comparison,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze paired arm comparisons from experiment matrix records",
    )
    parser.add_argument(
        "--records-path",
        required=True,
        help="Path to experiment records.json",
    )
    parser.add_argument(
        "--baseline-arm",
        default="full_system",
        help="Baseline arm name used for paired deltas",
    )
    parser.add_argument(
        "--target-arms",
        default="",
        help="Comma-separated target arm names; empty means all non-baseline arms",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Output path for comparison report (default: same dir as records)",
    )
    parser.add_argument(
        "--fail-on-empty-pairs",
        action="store_true",
        help="Exit non-zero if any target has zero paired samples",
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

    payload = _read_json(records_path)
    if not isinstance(payload, list):
        raise ValueError("records payload must be a JSON list")

    target_arms = [item.strip() for item in args.target_arms.split(",") if item.strip()]
    report = analyze_arm_comparison(
        payload,
        baseline_arm=args.baseline_arm,
        target_arms=target_arms if target_arms else None,
    )
    report["generated_at"] = datetime.utcnow().isoformat() + "Z"
    report["input"] = {
        "records_path": str(records_path),
        "baseline_arm": args.baseline_arm,
        "target_arms": target_arms,
    }

    output_path = (
        Path(args.output_path).expanduser().resolve()
        if args.output_path.strip()
        else records_path.parent / "arm_comparison_summary.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"baseline={report['baseline_arm']}")
    empty_targets: list[str] = []
    for row in report["targets"]:
        summary = row["summary"]
        print(
            " - target={target} n={n} mean_delta={delta:.4f} ci95=[{lo:.4f}, {hi:.4f}] "
            "p10={p10:.4f} wilcoxon_p={p:.4f} win_rate={win:.2%}".format(
                target=row["target_arm"],
                n=summary["n_pairs"],
                delta=summary["mean_score_delta"],
                lo=summary["score_delta_ci95"][0],
                hi=summary["score_delta_ci95"][1],
                p10=summary["p10_score_delta"],
                p=summary["wilcoxon"]["p_value"],
                win=summary["win_rate"],
            )
        )
        if int(summary["n_pairs"]) == 0:
            empty_targets.append(str(row["target_arm"]))

    print(f"report: {output_path}")
    if args.fail_on_empty_pairs and empty_targets:
        print(f"empty_pairs_targets: {','.join(empty_targets)}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
