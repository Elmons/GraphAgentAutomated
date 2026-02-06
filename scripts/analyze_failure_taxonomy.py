#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from graph_agent_automated.infrastructure.evaluation.failure_taxonomy_report import (
    analyze_failure_taxonomy_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze failure taxonomy records for calibration hints",
    )
    parser.add_argument(
        "--records-path",
        required=True,
        help="Path to manual parity records.json",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Optional output path (default: same dir as records/failure_taxonomy_analysis.json)",
    )
    parser.add_argument(
        "--top-k-signals",
        type=int,
        default=15,
        help="Number of top signals/tasks/categories to keep",
    )
    parser.add_argument(
        "--top-k-cases",
        type=int,
        default=20,
        help="Number of top severe cases to keep",
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

    report = analyze_failure_taxonomy_records(
        payload,
        top_k_signals=args.top_k_signals,
        top_k_cases=args.top_k_cases,
    )
    report["generated_at"] = datetime.utcnow().isoformat() + "Z"
    report["input"] = {
        "records_path": str(records_path),
        "top_k_signals": args.top_k_signals,
        "top_k_cases": args.top_k_cases,
    }

    output_path = (
        Path(args.output_path).expanduser().resolve()
        if args.output_path.strip()
        else records_path.parent / "failure_taxonomy_analysis.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(
        "runs={runs} failures={failures} failure_run_rate={rate:.2%}".format(
            runs=report["total_runs"],
            failures=report["total_failures"],
            rate=report["failure_run_rate"],
        )
    )
    print(
        "category_ratio={ratio}".format(
            ratio=report["by_category_ratio"],
        )
    )
    print(
        "severity_ratio={ratio}".format(
            ratio=report["by_severity_ratio"],
        )
    )
    hints = report.get("calibration_hints", [])
    if isinstance(hints, list):
        for hint in hints[:5]:
            print(f"hint: {hint}")
    print(f"report: {output_path}")


if __name__ == "__main__":
    main()
