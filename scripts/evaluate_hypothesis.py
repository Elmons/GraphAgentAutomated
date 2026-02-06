#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from graph_agent_automated.infrastructure.evaluation.hypothesis_evaluator import (
    evaluate_hypothesis,
    load_hypothesis_spec,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate whether a research hypothesis is supported by arm comparison artifacts",
    )
    parser.add_argument(
        "--arm-comparison-path",
        required=True,
        help="Path to arm_comparison_summary.json",
    )
    parser.add_argument(
        "--hypothesis-spec-path",
        default="docs/benchmarks/hypothesis_idea1_v1.json",
        help="Hypothesis spec JSON path",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Output report path (default: same dir as arm comparison/hypothesis_report.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when hypothesis is not supported",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    args = parse_args()
    arm_comparison_path = Path(args.arm_comparison_path).expanduser().resolve()
    if not arm_comparison_path.exists() or not arm_comparison_path.is_file():
        raise ValueError(f"arm comparison file not found: {arm_comparison_path}")

    arm_report = _read_json(arm_comparison_path)
    if not isinstance(arm_report, dict):
        raise ValueError("arm comparison payload must be a JSON object")
    hypothesis_spec = load_hypothesis_spec(args.hypothesis_spec_path)

    report = evaluate_hypothesis(
        arm_comparison_report=arm_report,
        spec=hypothesis_spec,
    )
    report["generated_at"] = datetime.utcnow().isoformat() + "Z"
    report["input"] = {
        "arm_comparison_path": str(arm_comparison_path),
        "hypothesis_spec_path": str(Path(args.hypothesis_spec_path).expanduser().resolve()),
    }

    output_path = (
        Path(args.output_path).expanduser().resolve()
        if args.output_path.strip()
        else arm_comparison_path.parent / "hypothesis_report.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    status = "SUPPORTED" if report["supported"] else "NOT_SUPPORTED"
    print(
        "[{status}] hypothesis={hid} version={ver} target={target}".format(
            status=status,
            hid=report["hypothesis_id"],
            ver=report["version"],
            target=report["target_arm"],
        )
    )
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

    if args.strict and not report["supported"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
