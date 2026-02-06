#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

from graph_agent_automated.infrastructure.evaluation.failure_taxonomy import (
    FAILURE_CATEGORIES,
    FAILURE_SEVERITIES,
)
from graph_agent_automated.infrastructure.evaluation.parity_statistics import (
    cliffs_delta,
    paired_bootstrap_mean_ci,
    wilcoxon_signed_rank,
)
from graph_agent_automated.infrastructure.runtime.async_job_client import (
    poll_job_until_complete,
)
from graph_agent_automated.infrastructure.runtime.research_benchmark import (
    BenchmarkTaskSpec,
    load_research_benchmark,
    resolve_manual_blueprint_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run manual parity benchmark via GraphAgentAutomated API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008", help="API base URL")
    parser.add_argument(
        "--benchmark-path",
        default="docs/benchmarks/research_benchmark_v1.json",
        help="Frozen benchmark specification JSON path",
    )
    parser.add_argument(
        "--manual-blueprints-root",
        default="docs/manual_blueprints/research_benchmark_v1",
        help="Root directory for benchmark manual blueprints",
    )
    parser.add_argument(
        "--manual-blueprint-path",
        default="",
        help="Optional override path for all tasks (must be under MANUAL_BLUEPRINTS_DIR on server)",
    )
    parser.add_argument("--profile", default="full_system", help="Optimization profile for auto generation")
    parser.add_argument("--dataset-size", type=int, default=12, help="Dataset size")
    parser.add_argument(
        "--seeds",
        type=int,
        default=None,
        help="Optional override for seed count per task; default uses benchmark default_seeds",
    )
    parser.add_argument("--parity-margin", type=float, default=0.03, help="Accepted score gap margin")
    parser.add_argument("--prefix", default="parity", help="Agent name prefix")
    parser.add_argument("--output-dir", default="artifacts/manual_parity", help="Output directory")
    parser.add_argument(
        "--resume-records-path",
        default="",
        help="Optional existing records.json path used to resume unfinished task/seed runs",
    )
    parser.add_argument(
        "--async-submit",
        action="store_true",
        help="Use async parity endpoint and poll job status until completion",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=1.0,
        help="Polling interval for async job status",
    )
    parser.add_argument(
        "--job-timeout-seconds",
        type=float,
        default=1800.0,
        help="Timeout for one async job to finish",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=180.0,
        help="HTTP request timeout seconds for submit/sync request",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately when one task/seed run fails",
    )
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit non-zero if any run fails",
    )
    parser.add_argument(
        "--idempotency-prefix",
        default="parity-matrix",
        help="Idempotency key prefix; empty string disables idempotency header",
    )
    parser.add_argument("--api-key", default="", help="Optional X-API-Key header value")
    parser.add_argument("--bearer-token", default="", help="Optional bearer token for Authorization header")
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow httpx to inherit proxy settings from environment variables",
    )
    return parser.parse_args()


def run_once_sync(
    client: httpx.Client,
    agent_name: str,
    task: BenchmarkTaskSpec,
    seed: int,
    manual_blueprint_path: str,
    profile: str,
    dataset_size: int,
    parity_margin: float,
    request_timeout_seconds: float,
    headers: dict[str, str],
) -> dict[str, Any]:
    payload = {
        "agent_name": agent_name,
        "task_desc": task.task_desc,
        "manual_blueprint_path": manual_blueprint_path,
        "dataset_size": dataset_size,
        "profile": profile,
        "seed": seed,
        "parity_margin": parity_margin,
    }
    resp = client.post(
        "/v1/agents/benchmark/manual-parity",
        json=payload,
        headers=headers,
        timeout=request_timeout_seconds,
    )
    resp.raise_for_status()
    return resp.json()


def run_once_async(
    client: httpx.Client,
    agent_name: str,
    task: BenchmarkTaskSpec,
    seed: int,
    manual_blueprint_path: str,
    profile: str,
    dataset_size: int,
    parity_margin: float,
    request_timeout_seconds: float,
    poll_interval_seconds: float,
    job_timeout_seconds: float,
    headers: dict[str, str],
) -> dict[str, Any]:
    payload = {
        "agent_name": agent_name,
        "task_desc": task.task_desc,
        "manual_blueprint_path": manual_blueprint_path,
        "dataset_size": dataset_size,
        "profile": profile,
        "seed": seed,
        "parity_margin": parity_margin,
    }
    submit_resp = client.post(
        "/v1/agents/benchmark/manual-parity/async",
        json=payload,
        headers=headers,
        timeout=request_timeout_seconds,
    )
    submit_resp.raise_for_status()
    submit_body = submit_resp.json()
    if not isinstance(submit_body, dict):
        raise ValueError("manual parity async submit response must be a JSON object")
    job_id = str(submit_body.get("job_id") or "").strip()
    if not job_id:
        raise ValueError("manual parity async submit response missing job_id")

    result = poll_job_until_complete(
        client,
        job_id=job_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=job_timeout_seconds,
        headers=headers,
    )
    result["job_id"] = job_id
    return result


def build_request_headers(
    *,
    api_key: str,
    bearer_token: str,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    key = api_key.strip()
    if key:
        headers["X-API-Key"] = key
    token = bearer_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idempotency_key is not None and idempotency_key.strip():
        headers["Idempotency-Key"] = idempotency_key.strip()
    return headers


def build_idempotency_key(
    *,
    prefix: str,
    task_id: str,
    seed: int,
    profile: str,
    manual_blueprint_path: str,
) -> str | None:
    normalized_prefix = prefix.strip()
    if not normalized_prefix:
        return None
    digest = hashlib.sha1(
        f"{task_id}|{seed}|{profile}|{manual_blueprint_path}".encode(),
    ).hexdigest()[:16]
    return f"{normalized_prefix}-{task_id}-s{seed}-{digest}"


def load_resume_records(path: str) -> list[dict[str, Any]]:
    resume_path = Path(path).expanduser().resolve()
    if not resume_path.exists() or not resume_path.is_file():
        raise ValueError(f"resume records file not found: {resume_path}")
    with open(resume_path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise ValueError("resume records payload must be a JSON list")
    rows: list[dict[str, Any]] = []
    for row in payload:
        if isinstance(row, dict):
            rows.append(dict(row))
    return rows


def build_completed_keys(records: list[dict[str, Any]]) -> set[tuple[str, int]]:
    output: set[tuple[str, int]] = set()
    for row in records:
        task_id = str(row.get("task_id") or "").strip()
        seed = row.get("seed")
        if not task_id:
            continue
        if isinstance(seed, bool) or not isinstance(seed, int):
            continue
        output.add((task_id, seed))
    return output


def write_checkpoint(
    out_dir: Path,
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    with open(out_dir / "records.partial.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    with open(out_dir / "errors.partial.json", "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_task[str(row["task_id"])].append(row)

    summary: list[dict[str, Any]] = []
    for task_id, rows in by_task.items():
        parity_rate = mean([1.0 if row["parity_achieved"] else 0.0 for row in rows])
        avg_delta = mean([float(row["score_delta"]) for row in rows])
        summary.append(
            {
                "task_id": task_id,
                "task_desc": str(rows[0]["task_desc"]) if rows else "",
                "task_category": str(rows[0]["task_category"]) if rows else "",
                "runs": len(rows),
                "parity_rate": parity_rate,
                "avg_score_delta": avg_delta,
                "avg_auto_score": mean([float(row["auto_score"]) for row in rows]),
                "avg_manual_score": mean([float(row["manual_score"]) for row in rows]),
                "avg_auto_latency_ms": mean([float(row["auto_mean_latency_ms"]) for row in rows]),
                "avg_manual_latency_ms": mean([float(row["manual_mean_latency_ms"]) for row in rows]),
                "avg_auto_token_cost": mean([float(row["auto_mean_token_cost"]) for row in rows]),
                "avg_manual_token_cost": mean([float(row["manual_mean_token_cost"]) for row in rows]),
            }
        )
    return summary


def build_parity_statistics(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "n_runs": 0,
            "parity_rate": 0.0,
            "mean_score_delta": 0.0,
            "mean_score_delta_ci95": [0.0, 0.0],
            "wilcoxon": {
                "n_pairs": 0.0,
                "n_non_zero": 0.0,
                "w_plus": 0.0,
                "w_minus": 0.0,
                "z_score": 0.0,
                "p_value": 1.0,
            },
            "cliffs_delta": {"value": 0.0, "magnitude": "negligible"},
        }

    auto_scores = [float(row["auto_score"]) for row in records]
    manual_scores = [float(row["manual_score"]) for row in records]
    deltas = [auto - manual for auto, manual in zip(auto_scores, manual_scores, strict=True)]
    ci_lo, ci_hi = paired_bootstrap_mean_ci(deltas)
    wilcoxon = wilcoxon_signed_rank(auto_scores, manual_scores)
    cliffs_value, cliffs_magnitude = cliffs_delta(auto_scores, manual_scores)
    parity_rate = mean([1.0 if row["parity_achieved"] else 0.0 for row in records])

    return {
        "n_runs": len(records),
        "parity_rate": parity_rate,
        "mean_score_delta": mean(deltas),
        "mean_score_delta_ci95": [ci_lo, ci_hi],
        "mean_auto_latency_ms": mean([float(row["auto_mean_latency_ms"]) for row in records]),
        "mean_manual_latency_ms": mean([float(row["manual_mean_latency_ms"]) for row in records]),
        "mean_auto_token_cost": mean([float(row["auto_mean_token_cost"]) for row in records]),
        "mean_manual_token_cost": mean([float(row["manual_mean_token_cost"]) for row in records]),
        "wilcoxon": wilcoxon,
        "cliffs_delta": {"value": cliffs_value, "magnitude": cliffs_magnitude},
    }


def aggregate_failure_taxonomy(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_category = {category: 0 for category in FAILURE_CATEGORIES}
    by_severity = {severity: 0 for severity in FAILURE_SEVERITIES}
    total_failures = 0

    for row in records:
        taxonomy = row.get("failure_taxonomy")
        if not isinstance(taxonomy, dict):
            continue
        total_failures += int(taxonomy.get("total_failures", 0))

        category_map = taxonomy.get("by_category", {})
        if isinstance(category_map, dict):
            for category in FAILURE_CATEGORIES:
                by_category[category] += int(category_map.get(category, 0))

        severity_map = taxonomy.get("by_severity", {})
        if isinstance(severity_map, dict):
            for severity in FAILURE_SEVERITIES:
                by_severity[severity] += int(severity_map.get(severity, 0))

    by_category_ratio = (
        {category: by_category[category] / total_failures for category in FAILURE_CATEGORIES}
        if total_failures > 0
        else {category: 0.0 for category in FAILURE_CATEGORIES}
    )
    by_severity_ratio = (
        {severity: by_severity[severity] / total_failures for severity in FAILURE_SEVERITIES}
        if total_failures > 0
        else {severity: 0.0 for severity in FAILURE_SEVERITIES}
    )

    return {
        "total_failures": total_failures,
        "by_category": by_category,
        "by_category_ratio": by_category_ratio,
        "by_severity": by_severity,
        "by_severity_ratio": by_severity_ratio,
    }


def main() -> None:
    args = parse_args()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    benchmark = load_research_benchmark(args.benchmark_path)
    seeds = list(range(1, args.seeds + 1)) if args.seeds is not None else list(benchmark.default_seeds)
    seeds_source = "cli_count" if args.seeds is not None else "benchmark_default_seeds"
    manual_blueprints_root = Path(args.manual_blueprints_root).expanduser().resolve()
    override_manual_blueprint_path = args.manual_blueprint_path.strip()
    run_mode = "async" if args.async_submit else "sync"
    if args.poll_interval_seconds <= 0:
        raise ValueError("poll-interval-seconds must be positive")
    if args.job_timeout_seconds <= 0:
        raise ValueError("job-timeout-seconds must be positive")
    if args.request_timeout_seconds <= 0:
        raise ValueError("request-timeout-seconds must be positive")

    if args.resume_records_path.strip():
        resumed_records = load_resume_records(args.resume_records_path)
        records.extend(resumed_records)
    completed_keys = build_completed_keys(records)

    if override_manual_blueprint_path:
        override_path = Path(override_manual_blueprint_path).expanduser().resolve()
        if not override_path.exists() or not override_path.is_file():
            raise ValueError(f"manual blueprint override path not found: {override_path}")

    with httpx.Client(base_url=args.base_url, trust_env=args.trust_env) as client:
        for task_idx, task in enumerate(benchmark.task_items, start=1):
            if override_manual_blueprint_path:
                manual_blueprint_path = str(override_path)
            else:
                manual_blueprint_path = str(resolve_manual_blueprint_path(task, manual_blueprints_root))
            for seed in seeds:
                pair_key = (task.task_id, seed)
                if pair_key in completed_keys:
                    print(f"[skip] task={task.task_id} seed={seed} already completed in resume records")
                    continue
                agent_name = f"{args.prefix}-t{task_idx}-s{seed}"
                idempotency_key = build_idempotency_key(
                    prefix=args.idempotency_prefix,
                    task_id=task.task_id,
                    seed=seed,
                    profile=args.profile,
                    manual_blueprint_path=manual_blueprint_path,
                )
                headers = build_request_headers(
                    api_key=args.api_key,
                    bearer_token=args.bearer_token,
                    idempotency_key=idempotency_key,
                )
                try:
                    if args.async_submit:
                        row = run_once_async(
                            client=client,
                            agent_name=agent_name,
                            task=task,
                            seed=seed,
                            manual_blueprint_path=manual_blueprint_path,
                            profile=args.profile,
                            dataset_size=args.dataset_size,
                            parity_margin=args.parity_margin,
                            request_timeout_seconds=args.request_timeout_seconds,
                            poll_interval_seconds=args.poll_interval_seconds,
                            job_timeout_seconds=args.job_timeout_seconds,
                            headers=headers,
                        )
                    else:
                        row = run_once_sync(
                            client=client,
                            agent_name=agent_name,
                            task=task,
                            seed=seed,
                            manual_blueprint_path=manual_blueprint_path,
                            profile=args.profile,
                            dataset_size=args.dataset_size,
                            parity_margin=args.parity_margin,
                            request_timeout_seconds=args.request_timeout_seconds,
                            headers=headers,
                        )

                    row["task_id"] = task.task_id
                    row["task_category"] = task.category
                    row["task_desc"] = task.task_desc
                    row["seed"] = seed
                    row["agent_name"] = agent_name
                    row["manual_blueprint_path"] = manual_blueprint_path
                    row["failure_taxonomy"] = (
                        row.get("failure_taxonomy")
                        if isinstance(row.get("failure_taxonomy"), dict)
                        else {}
                    )
                    records.append(row)
                    completed_keys.add(pair_key)
                    print(
                        f"[ok] mode={run_mode} task={task.task_id} seed={seed} "
                        f"auto={row['auto_score']:.4f} manual={row['manual_score']:.4f} "
                        f"parity={row['parity_achieved']}"
                    )
                except Exception as exc:
                    error_row = {
                        "task_id": task.task_id,
                        "task_category": task.category,
                        "task_desc": task.task_desc,
                        "seed": seed,
                        "agent_name": agent_name,
                        "manual_blueprint_path": manual_blueprint_path,
                        "mode": run_mode,
                        "error": str(exc),
                    }
                    errors.append(error_row)
                    print(f"[err] mode={run_mode} task={task.task_id} seed={seed} error={exc}")
                    if args.stop_on_error:
                        write_checkpoint(out_dir, records, errors)
                        raise

                write_checkpoint(out_dir, records, errors)

    summary = summarize(records)
    parity_stats = build_parity_statistics(records)
    failure_taxonomy_summary = aggregate_failure_taxonomy(records)

    with open(out_dir / "records.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(out_dir / "parity_stats.json", "w", encoding="utf-8") as f:
        json.dump(parity_stats, f, ensure_ascii=False, indent=2)
    with open(out_dir / "failure_taxonomy_summary.json", "w", encoding="utf-8") as f:
        json.dump(failure_taxonomy_summary, f, ensure_ascii=False, indent=2)
    with open(out_dir / "errors.json", "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "base_url": args.base_url,
                "benchmark_path": str(Path(args.benchmark_path).expanduser().resolve()),
                "benchmark_id": benchmark.benchmark_id,
                "benchmark_version": benchmark.version,
                "manual_blueprints_root": str(manual_blueprints_root),
                "manual_blueprint_path_override": (
                    str(Path(override_manual_blueprint_path).expanduser().resolve())
                    if override_manual_blueprint_path
                    else None
                ),
                "profile": args.profile,
                "dataset_size": args.dataset_size,
                "seeds": seeds,
                "seeds_source": seeds_source,
                "parity_margin": args.parity_margin,
                "run_mode": run_mode,
                "poll_interval_seconds": args.poll_interval_seconds if args.async_submit else None,
                "job_timeout_seconds": args.job_timeout_seconds if args.async_submit else None,
                "request_timeout_seconds": args.request_timeout_seconds,
                "resume_records_path": (
                    str(Path(args.resume_records_path).expanduser().resolve())
                    if args.resume_records_path.strip()
                    else None
                ),
                "stop_on_error": args.stop_on_error,
                "fail_on_errors": args.fail_on_errors,
                "idempotency_prefix_enabled": bool(args.idempotency_prefix.strip()),
                "auth_mode": (
                    "api_key"
                    if args.api_key.strip()
                    else ("bearer" if args.bearer_token.strip() else "none")
                ),
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "category": task.category,
                        "task_desc": task.task_desc,
                        "manual_blueprint": task.manual_blueprint,
                    }
                    for task in benchmark.task_items
                ],
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
                task=row["task_id"],
                runs=row["runs"],
                rate=row["parity_rate"],
                delta=row["avg_score_delta"],
            )
        )
    print(
        " - global parity_rate={rate:.2%} mean_delta={delta:.4f} ci95=[{lo:.4f}, {hi:.4f}] "
        "wilcoxon_p={p:.4f} cliffs_delta={effect:.4f}({magnitude})".format(
            rate=parity_stats["parity_rate"],
            delta=parity_stats["mean_score_delta"],
            lo=parity_stats["mean_score_delta_ci95"][0],
            hi=parity_stats["mean_score_delta_ci95"][1],
            p=parity_stats["wilcoxon"]["p_value"],
            effect=parity_stats["cliffs_delta"]["value"],
            magnitude=parity_stats["cliffs_delta"]["magnitude"],
        )
    )
    print(
        " - failures total={total} categories={categories}".format(
            total=failure_taxonomy_summary["total_failures"],
            categories=failure_taxonomy_summary["by_category"],
        )
    )
    if errors:
        print(f" - errors count={len(errors)} (see {out_dir / 'errors.json'})")
        if args.fail_on_errors:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
