#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from graph_agent_automated.infrastructure.runtime.research_pipeline import (
    resolve_new_run_dir,
    snapshot_subdir_names,
)


@dataclass
class StepResult:
    name: str
    status: str
    command: list[str]
    started_at: str
    ended_at: str
    duration_seconds: float
    detail: str = ""
    output_path: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end research pipeline and generate reproducible artifacts",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8008", help="API base URL")
    parser.add_argument(
        "--benchmark-path",
        default="docs/benchmarks/research_benchmark_v1.json",
        help="Frozen benchmark JSON path",
    )
    parser.add_argument(
        "--gate-spec-path",
        default="docs/benchmarks/research_gate_v1.json",
        help="Research gate JSON path",
    )
    parser.add_argument(
        "--failure-rules-path",
        default="docs/benchmarks/failure_taxonomy_rules_v1.json",
        help="Failure taxonomy rules JSON path used by recompute step",
    )
    parser.add_argument(
        "--manual-blueprints-root",
        default="docs/manual_blueprints/research_benchmark_v1",
        help="Manual blueprints root path",
    )
    parser.add_argument("--experiment-output-dir", default="artifacts/experiments", help="Experiment output root")
    parser.add_argument("--parity-output-dir", default="artifacts/manual_parity", help="Parity output root")
    parser.add_argument("--seeds", type=int, default=5, help="Seed count override for matrix/parity scripts")
    parser.add_argument("--profile", default="full_system", help="Parity optimization profile")
    parser.add_argument("--dataset-size", type=int, default=12, help="Parity dataset size")
    parser.add_argument("--parity-margin", type=float, default=0.03, help="Parity accepted delta margin")
    parser.add_argument("--prefix", default="pipeline", help="Agent name prefix")
    parser.add_argument(
        "--include-ablations",
        action="store_true",
        help="Include ablation arms in experiment matrix",
    )
    parser.add_argument(
        "--include-idea-arms",
        action="store_true",
        help="Include idea arms in experiment matrix",
    )
    parser.add_argument(
        "--idea-target-arms",
        default="idea_failure_aware_mutation",
        help="Comma-separated target arms for paired analysis",
    )
    parser.add_argument(
        "--parity-async-submit",
        action="store_true",
        help="Use async mode for manual parity matrix",
    )
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0, help="Async parity polling interval")
    parser.add_argument("--job-timeout-seconds", type=float, default=1800.0, help="Async parity job timeout")
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0, help="Request timeout seconds")
    parser.add_argument(
        "--parity-stop-on-error",
        action="store_true",
        help="Stop parity matrix immediately when one run fails",
    )
    parser.add_argument(
        "--parity-fail-on-errors",
        action="store_true",
        help="Parity script exits non-zero when errors.json is non-empty",
    )
    parser.add_argument("--api-key", default="", help="Optional X-API-Key for protected endpoints")
    parser.add_argument("--bearer-token", default="", help="Optional bearer token for protected endpoints")
    parser.add_argument(
        "--idempotency-prefix",
        default="pipeline",
        help="Idempotency prefix for parity matrix requests",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow scripts to inherit proxy env variables",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip /healthz preflight check",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining steps when one step fails",
    )
    parser.add_argument(
        "--skip-experiment-matrix",
        action="store_true",
        help="Skip run_experiment_matrix.py",
    )
    parser.add_argument(
        "--skip-arm-analysis",
        action="store_true",
        help="Skip analyze_experiment_arms.py",
    )
    parser.add_argument(
        "--skip-hypothesis-eval",
        action="store_true",
        help="Skip evaluate_hypothesis.py",
    )
    parser.add_argument(
        "--hypothesis-spec-path",
        default="docs/benchmarks/hypothesis_idea1_v1.json",
        help="Hypothesis spec JSON path for idea evaluation",
    )
    parser.add_argument(
        "--skip-manual-parity",
        action="store_true",
        help="Skip run_manual_parity_matrix.py",
    )
    parser.add_argument(
        "--skip-failure-analysis",
        action="store_true",
        help="Skip analyze_failure_taxonomy.py",
    )
    parser.add_argument(
        "--skip-failure-recompute",
        action="store_true",
        help="Skip recompute_failure_taxonomy.py",
    )
    parser.add_argument(
        "--skip-gate-eval",
        action="store_true",
        help="Skip evaluate_research_gate.py",
    )
    parser.add_argument(
        "--report-path",
        default="",
        help="Optional output report path (default: artifacts/pipeline/pipeline_<timestamp>.json)",
    )
    return parser.parse_args()


def run_step(name: str, command: list[str]) -> StepResult:
    started_wall = datetime.now(timezone.utc).isoformat()
    started = perf_counter()
    try:
        subprocess.run(command, check=True)
        status = "ok"
        detail = ""
    except subprocess.CalledProcessError as exc:
        status = "failed"
        detail = f"exit_code={exc.returncode}"
    ended = perf_counter()
    ended_wall = datetime.now(timezone.utc).isoformat()
    return StepResult(
        name=name,
        status=status,
        command=command,
        started_at=started_wall,
        ended_at=ended_wall,
        duration_seconds=ended - started,
        detail=detail,
    )


def make_output_report_path(arg_path: str) -> Path:
    if arg_path.strip():
        return Path(arg_path).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return (Path("artifacts/pipeline") / f"pipeline_{timestamp}.json").resolve()


def build_common_flags(args: argparse.Namespace) -> list[str]:
    flags: list[str] = []
    if args.trust_env:
        flags.append("--trust-env")
    return flags


def main() -> None:
    args = parse_args()
    report_path = make_output_report_path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    step_rows: list[StepResult] = []
    failed_steps: list[str] = []
    common_flags = build_common_flags(args)

    experiment_run_dir: Path | None = None
    parity_run_dir: Path | None = None

    if not args.skip_health_check:
        health_step = run_step(
            "health_check",
            [
                sys.executable,
                "-c",
                (
                    "import httpx;"
                    f"c=httpx.Client(base_url='{args.base_url}', trust_env={str(args.trust_env)});"
                    "r=c.get('/healthz');"
                    "r.raise_for_status();"
                    "p=r.json();"
                    "assert isinstance(p, dict) and p.get('status')=='ok'"
                ),
            ],
        )
        step_rows.append(health_step)
        if health_step.status != "ok":
            failed_steps.append("health_check")
            if not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, None, None)
                raise SystemExit(2)

    if not args.skip_experiment_matrix:
        exp_root = Path(args.experiment_output_dir).expanduser().resolve()
        before_names = snapshot_subdir_names(exp_root)
        command = [
            sys.executable,
            "scripts/run_experiment_matrix.py",
            "--base-url",
            args.base_url,
            "--benchmark-path",
            args.benchmark_path,
            "--output-dir",
            args.experiment_output_dir,
            "--prefix",
            args.prefix,
            "--seeds",
            str(args.seeds),
        ]
        if args.include_ablations:
            command.append("--include-ablations")
        if args.include_idea_arms:
            command.append("--include-idea-arms")
        command.extend(common_flags)
        step = run_step("run_experiment_matrix", command)
        if step.status == "ok":
            experiment_run_dir = resolve_new_run_dir(exp_root, before_names)
            step.output_path = str(experiment_run_dir)
        else:
            failed_steps.append(step.name)
        step_rows.append(step)
        if step.status != "ok" and not args.continue_on_error:
            _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
            raise SystemExit(2)

    if not args.skip_arm_analysis:
        if experiment_run_dir is None:
            failed_steps.append("analyze_experiment_arms")
            step_rows.append(
                StepResult(
                    name="analyze_experiment_arms",
                    status="failed",
                    command=[],
                    started_at=datetime.now(timezone.utc).isoformat(),
                    ended_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=0.0,
                    detail="missing experiment_run_dir",
                )
            )
            if not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)
        else:
            command = [
                sys.executable,
                "scripts/analyze_experiment_arms.py",
                "--records-path",
                str(experiment_run_dir / "records.json"),
                "--baseline-arm",
                "full_system",
                "--target-arms",
                args.idea_target_arms,
            ]
            step = run_step("analyze_experiment_arms", command)
            if step.status == "ok":
                step.output_path = str(experiment_run_dir / "arm_comparison_summary.json")
            else:
                failed_steps.append(step.name)
            step_rows.append(step)
            if step.status != "ok" and not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)

    if not args.skip_hypothesis_eval:
        if experiment_run_dir is None:
            failed_steps.append("evaluate_hypothesis")
            step_rows.append(
                StepResult(
                    name="evaluate_hypothesis",
                    status="failed",
                    command=[],
                    started_at=datetime.now(timezone.utc).isoformat(),
                    ended_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=0.0,
                    detail="missing experiment_run_dir",
                )
            )
            if not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)
        else:
            command = [
                sys.executable,
                "scripts/evaluate_hypothesis.py",
                "--arm-comparison-path",
                str(experiment_run_dir / "arm_comparison_summary.json"),
                "--hypothesis-spec-path",
                args.hypothesis_spec_path,
            ]
            step = run_step("evaluate_hypothesis", command)
            if step.status == "ok":
                step.output_path = str(experiment_run_dir / "hypothesis_report.json")
            else:
                failed_steps.append(step.name)
            step_rows.append(step)
            if step.status != "ok" and not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)

    if not args.skip_manual_parity:
        parity_root = Path(args.parity_output_dir).expanduser().resolve()
        before_names = snapshot_subdir_names(parity_root)
        command = [
            sys.executable,
            "scripts/run_manual_parity_matrix.py",
            "--base-url",
            args.base_url,
            "--benchmark-path",
            args.benchmark_path,
            "--manual-blueprints-root",
            args.manual_blueprints_root,
            "--profile",
            args.profile,
            "--dataset-size",
            str(args.dataset_size),
            "--parity-margin",
            str(args.parity_margin),
            "--output-dir",
            args.parity_output_dir,
            "--prefix",
            args.prefix,
            "--seeds",
            str(args.seeds),
            "--request-timeout-seconds",
            str(args.request_timeout_seconds),
            "--idempotency-prefix",
            args.idempotency_prefix,
        ]
        if args.parity_async_submit:
            command.extend(
                [
                    "--async-submit",
                    "--poll-interval-seconds",
                    str(args.poll_interval_seconds),
                    "--job-timeout-seconds",
                    str(args.job_timeout_seconds),
                ]
            )
        if args.parity_stop_on_error:
            command.append("--stop-on-error")
        if args.parity_fail_on_errors:
            command.append("--fail-on-errors")
        if args.api_key.strip():
            command.extend(["--api-key", args.api_key])
        if args.bearer_token.strip():
            command.extend(["--bearer-token", args.bearer_token])
        command.extend(common_flags)
        step = run_step("run_manual_parity_matrix", command)
        if step.status == "ok":
            parity_run_dir = resolve_new_run_dir(parity_root, before_names)
            step.output_path = str(parity_run_dir)
        else:
            failed_steps.append(step.name)
        step_rows.append(step)
        if step.status != "ok" and not args.continue_on_error:
            _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
            raise SystemExit(2)

    if not args.skip_failure_analysis:
        if parity_run_dir is None:
            failed_steps.append("analyze_failure_taxonomy")
            step_rows.append(
                StepResult(
                    name="analyze_failure_taxonomy",
                    status="failed",
                    command=[],
                    started_at=datetime.now(timezone.utc).isoformat(),
                    ended_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=0.0,
                    detail="missing parity_run_dir",
                )
            )
            if not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)
        else:
            command = [
                sys.executable,
                "scripts/analyze_failure_taxonomy.py",
                "--records-path",
                str(parity_run_dir / "records.json"),
            ]
            step = run_step("analyze_failure_taxonomy", command)
            if step.status == "ok":
                step.output_path = str(parity_run_dir / "failure_taxonomy_analysis.json")
            else:
                failed_steps.append(step.name)
            step_rows.append(step)
            if step.status != "ok" and not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)

    if not args.skip_failure_recompute:
        if parity_run_dir is None:
            failed_steps.append("recompute_failure_taxonomy")
            step_rows.append(
                StepResult(
                    name="recompute_failure_taxonomy",
                    status="failed",
                    command=[],
                    started_at=datetime.now(timezone.utc).isoformat(),
                    ended_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=0.0,
                    detail="missing parity_run_dir",
                )
            )
            if not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)
        else:
            command = [
                sys.executable,
                "scripts/recompute_failure_taxonomy.py",
                "--records-path",
                str(parity_run_dir / "records.json"),
                "--rules-path",
                args.failure_rules_path,
            ]
            step = run_step("recompute_failure_taxonomy", command)
            if step.status == "ok":
                step.output_path = str(parity_run_dir / "recomputed_failure_taxonomy.json")
            else:
                failed_steps.append(step.name)
            step_rows.append(step)
            if step.status != "ok" and not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)

    if not args.skip_gate_eval:
        if parity_run_dir is None:
            failed_steps.append("evaluate_research_gate")
            step_rows.append(
                StepResult(
                    name="evaluate_research_gate",
                    status="failed",
                    command=[],
                    started_at=datetime.now(timezone.utc).isoformat(),
                    ended_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=0.0,
                    detail="missing parity_run_dir",
                )
            )
            if not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)
        else:
            command = [
                sys.executable,
                "scripts/evaluate_research_gate.py",
                "--records-path",
                str(parity_run_dir / "records.json"),
                "--gate-spec-path",
                args.gate_spec_path,
            ]
            step = run_step("evaluate_research_gate", command)
            if step.status == "ok":
                step.output_path = str(parity_run_dir / "gate_report.json")
            else:
                failed_steps.append(step.name)
            step_rows.append(step)
            if step.status != "ok" and not args.continue_on_error:
                _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
                raise SystemExit(2)

    _write_report(report_path, args, step_rows, failed_steps, experiment_run_dir, parity_run_dir)
    print(f"pipeline_report: {report_path}")
    if failed_steps:
        print(f"pipeline_failed_steps: {failed_steps}")
        raise SystemExit(2)
    print("pipeline_status: PASS")


def _write_report(
    report_path: Path,
    args: argparse.Namespace,
    steps: list[StepResult],
    failed_steps: list[str],
    experiment_run_dir: Path | None,
    parity_run_dir: Path | None,
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_passed": not failed_steps,
        "failed_steps": failed_steps,
        "experiment_run_dir": str(experiment_run_dir) if experiment_run_dir else None,
        "parity_run_dir": str(parity_run_dir) if parity_run_dir else None,
        "args": vars(args),
        "steps": [asdict(step) for step in steps],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
