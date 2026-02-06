#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

DEFAULT_TASKS = [
    "Find risky transfer chains with graph query and explain evidence",
    "Run graph analytics to rank influential accounts and justify reasoning",
    "Design schema evolution and validation plan for new relationship types",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run manual parity benchmark via GraphAgentAutomated API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008", help="API base URL")
    parser.add_argument("--manual-blueprint-path", required=True, help="Path to manual workflow yaml/json")
    parser.add_argument("--profile", default="full_system", help="Optimization profile for auto generation")
    parser.add_argument("--dataset-size", type=int, default=12, help="Dataset size")
    parser.add_argument("--seeds", type=int, default=3, help="Number of seeds per task")
    parser.add_argument("--parity-margin", type=float, default=0.03, help="Accepted score gap margin")
    parser.add_argument("--prefix", default="parity", help="Agent name prefix")
    parser.add_argument("--output-dir", default="artifacts/manual_parity", help="Output directory")
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow httpx to inherit proxy settings from environment variables",
    )
    return parser.parse_args()


def run_once(
    client: httpx.Client,
    agent_name: str,
    task_desc: str,
    seed: int,
    manual_blueprint_path: str,
    profile: str,
    dataset_size: int,
    parity_margin: float,
) -> dict[str, Any]:
    payload = {
        "agent_name": agent_name,
        "task_desc": task_desc,
        "manual_blueprint_path": manual_blueprint_path,
        "dataset_size": dataset_size,
        "profile": profile,
        "seed": seed,
        "parity_margin": parity_margin,
    }
    resp = client.post("/v1/agents/benchmark/manual-parity", json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_task[str(row["task_desc"])].append(row)

    summary: list[dict[str, Any]] = []
    for task, rows in by_task.items():
        parity_rate = mean([1.0 if row["parity_achieved"] else 0.0 for row in rows])
        avg_delta = mean([float(row["score_delta"]) for row in rows])
        summary.append(
            {
                "task_desc": task,
                "runs": len(rows),
                "parity_rate": parity_rate,
                "avg_score_delta": avg_delta,
            }
        )
    return summary


def main() -> None:
    args = parse_args()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.base_url, trust_env=args.trust_env) as client:
        for task_idx, task_desc in enumerate(DEFAULT_TASKS, start=1):
            for seed in range(1, args.seeds + 1):
                agent_name = f"{args.prefix}-t{task_idx}-s{seed}"
                row = run_once(
                    client=client,
                    agent_name=agent_name,
                    task_desc=task_desc,
                    seed=seed,
                    manual_blueprint_path=args.manual_blueprint_path,
                    profile=args.profile,
                    dataset_size=args.dataset_size,
                    parity_margin=args.parity_margin,
                )
                row["task_desc"] = task_desc
                row["seed"] = seed
                row["agent_name"] = agent_name
                records.append(row)
                print(
                    f"[ok] task={task_desc[:36]} seed={seed} "
                    f"auto={row['auto_score']:.4f} manual={row['manual_score']:.4f} "
                    f"parity={row['parity_achieved']}"
                )

    summary = summarize(records)

    with open(out_dir / "records.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "base_url": args.base_url,
                "manual_blueprint_path": str(Path(args.manual_blueprint_path).expanduser().resolve()),
                "profile": args.profile,
                "dataset_size": args.dataset_size,
                "seeds": args.seeds,
                "parity_margin": args.parity_margin,
                "tasks": DEFAULT_TASKS,
                "trust_env": args.trust_env,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\nSummary")
    for row in summary:
        print(
            " - task={task} n={runs} parity_rate={rate:.2%} avg_delta={delta:.4f}".format(
                task=row["task_desc"][:36],
                runs=row["runs"],
                rate=row["parity_rate"],
                delta=row["avg_score_delta"],
            )
        )


if __name__ == "__main__":
    main()
