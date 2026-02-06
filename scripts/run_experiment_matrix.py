#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import httpx


@dataclass(frozen=True)
class ExperimentArm:
    name: str
    profile: str
    dataset_size: int


BASELINE_ARMS = [
    ExperimentArm(name="baseline_static_prompt_only", profile="baseline_static_prompt_only", dataset_size=12),
    ExperimentArm(name="dynamic_prompt_only", profile="dynamic_prompt_only", dataset_size=12),
    ExperimentArm(name="dynamic_prompt_tool", profile="dynamic_prompt_tool", dataset_size=12),
    ExperimentArm(name="full_system", profile="full_system", dataset_size=12),
]

ABLATION_ARMS = [
    ExperimentArm(name="ablation_no_holdout", profile="ablation_no_holdout", dataset_size=12),
    ExperimentArm(name="ablation_single_judge", profile="ablation_single_judge", dataset_size=12),
    ExperimentArm(name="ablation_no_hard_negative", profile="ablation_no_hard_negative", dataset_size=12),
    ExperimentArm(name="ablation_no_tool_gain", profile="ablation_no_tool_gain", dataset_size=12),
    ExperimentArm(
        name="ablation_no_topology_mutation",
        profile="ablation_no_topology_mutation",
        dataset_size=12,
    ),
]

DEFAULT_TASKS = [
    "Find risky transfer chains with graph query and explain evidence",
    "Run graph analytics to rank influential accounts and justify reasoning",
    "Design schema evolution and validation plan for new relationship types",
]


def bootstrap_ci(values: list[float], n_resample: int = 2000, alpha: float = 0.05) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(7)
    samples: list[float] = []
    for _ in range(n_resample):
        resample = [rng.choice(values) for _ in range(len(values))]
        samples.append(mean(resample))
    samples.sort()
    lo_idx = int((alpha / 2) * (len(samples) - 1))
    hi_idx = int((1 - alpha / 2) * (len(samples) - 1))
    return samples[lo_idx], samples[hi_idx]


def run_arm(
    client: httpx.Client,
    arm: ExperimentArm,
    task_desc: str,
    seed: int,
    prefix: str,
) -> dict[str, Any]:
    agent_name = f"{prefix}-{arm.name}-s{seed}"
    payload = {
        "agent_name": agent_name,
        "task_desc": task_desc,
        "dataset_size": arm.dataset_size,
        "profile": arm.profile,
        "seed": seed,
    }
    resp = client.post("/v1/agents/optimize", json=payload, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    return {
        "arm": arm.name,
        "profile": arm.profile,
        "task_desc": task_desc,
        "seed": seed,
        "agent_name": agent_name,
        "run_id": body.get("run_id"),
        "train_score": float(body.get("train_score", 0.0)),
        "val_score": float(body.get("val_score", 0.0) or 0.0),
        "test_score": float(body.get("test_score", 0.0) or 0.0),
        "artifact_path": body.get("artifact_path", ""),
    }


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[str, list[float]] = defaultdict(list)
    for row in records:
        bucket[row["arm"]].append(float(row["test_score"]))

    summary: list[dict[str, Any]] = []
    for arm, values in sorted(bucket.items()):
        ci_lo, ci_hi = bootstrap_ci(values)
        summary.append(
            {
                "arm": arm,
                "runs": len(values),
                "test_mean": mean(values),
                "test_std": pstdev(values) if len(values) > 1 else 0.0,
                "test_ci95": [ci_lo, ci_hi],
            }
        )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run experiment matrix via GraphAgentAutomated API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008", help="API base URL")
    parser.add_argument("--seeds", type=int, default=3, help="Number of seeds per task and arm")
    parser.add_argument(
        "--output-dir",
        default="artifacts/experiments",
        help="Directory for raw and summary artifacts",
    )
    parser.add_argument(
        "--prefix",
        default="exp",
        help="Agent name prefix to avoid conflicts",
    )
    parser.add_argument(
        "--include-ablations",
        action="store_true",
        help="Include ablation arms in addition to baselines",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow httpx to inherit proxy settings from environment variables",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    arms = list(BASELINE_ARMS)
    if args.include_ablations:
        arms.extend(ABLATION_ARMS)

    with httpx.Client(base_url=args.base_url, trust_env=args.trust_env) as client:
        for task in DEFAULT_TASKS:
            for arm in arms:
                for seed in range(1, args.seeds + 1):
                    row = run_arm(client, arm, task, seed, args.prefix)
                    records.append(row)
                    print(
                        f"[ok] task={task[:36]} arm={arm.name} "
                        f"profile={arm.profile} seed={seed} test={row['test_score']:.4f}"
                    )

    summary = summarize(records)

    with open(out_dir / "records.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\nSummary")
    for row in summary:
        print(
            " - {arm}: n={runs} mean={test_mean:.4f} std={test_std:.4f} ci95=[{lo:.4f}, {hi:.4f}]".format(
                arm=row["arm"],
                runs=row["runs"],
                test_mean=row["test_mean"],
                test_std=row["test_std"],
                lo=row["test_ci95"][0],
                hi=row["test_ci95"][1],
            )
        )

    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "base_url": args.base_url,
                "seeds": args.seeds,
                "arms": [asdict(arm) for arm in arms],
                "tasks": DEFAULT_TASKS,
                "include_ablations": args.include_ablations,
                "trust_env": args.trust_env,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":
    main()
