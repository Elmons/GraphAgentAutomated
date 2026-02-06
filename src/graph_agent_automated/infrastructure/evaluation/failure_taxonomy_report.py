from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from graph_agent_automated.infrastructure.evaluation.failure_taxonomy import (
    FAILURE_CATEGORIES,
    FAILURE_SEVERITIES,
)


def analyze_failure_taxonomy_records(
    records: list[dict[str, Any]],
    *,
    top_k_signals: int = 15,
    top_k_cases: int = 20,
) -> dict[str, Any]:
    if top_k_signals <= 0:
        raise ValueError("top_k_signals must be positive")
    if top_k_cases <= 0:
        raise ValueError("top_k_cases must be positive")

    total_runs = len(records)
    runs_with_failures = 0
    total_failures = 0

    by_category: Counter[str] = Counter({name: 0 for name in FAILURE_CATEGORIES})
    by_severity: Counter[str] = Counter({name: 0 for name in FAILURE_SEVERITIES})
    by_task_category: Counter[str] = Counter()
    by_task_id: Counter[str] = Counter()
    signal_counter: Counter[str] = Counter()
    signal_by_category: dict[str, Counter[str]] = {
        category: Counter() for category in FAILURE_CATEGORIES
    }

    gap_values: list[float] = []
    severe_items: list[dict[str, Any]] = []

    for row in records:
        task_id = str(row.get("task_id") or "").strip()
        task_category = str(row.get("task_category") or "").strip()
        seed = row.get("seed")
        taxonomy = row.get("failure_taxonomy")
        if not isinstance(taxonomy, dict):
            continue

        run_failures = int(taxonomy.get("total_failures", 0))
        if run_failures > 0:
            runs_with_failures += 1
            total_failures += run_failures

        case_items = taxonomy.get("case_items")
        if not isinstance(case_items, list):
            continue

        for case_item in case_items:
            if not isinstance(case_item, dict):
                continue
            category = str(case_item.get("category") or "").strip()
            severity = str(case_item.get("severity") or "").strip()
            signal = str(case_item.get("signal") or "").strip()
            score_gap = _to_float(case_item.get("score_gap"), default=0.0)

            if category not in FAILURE_CATEGORIES:
                category = "other"
            if severity not in FAILURE_SEVERITIES:
                severity = "mild"
            if not signal:
                signal = "unknown"

            by_category[category] += 1
            by_severity[severity] += 1
            by_task_category[task_category or "unknown"] += 1
            by_task_id[task_id or "unknown"] += 1
            signal_counter[signal] += 1
            signal_by_category[category][signal] += 1
            gap_values.append(score_gap)

            if severity == "severe":
                severe_items.append(
                    {
                        "task_id": task_id or "unknown",
                        "task_category": task_category or "unknown",
                        "seed": int(seed) if isinstance(seed, int) and not isinstance(seed, bool) else None,
                        "case_id": str(case_item.get("case_id") or ""),
                        "category": category,
                        "signal": signal,
                        "score_gap": score_gap,
                        "auto_score": _to_float(case_item.get("auto_score"), default=0.0),
                        "manual_score": _to_float(case_item.get("manual_score"), default=0.0),
                    }
                )

    severe_items.sort(key=lambda row: float(row["score_gap"]), reverse=True)
    overall_top_signals = _top_counter(signal_counter, top_k_signals, key_name="signal")
    top_signals_by_category = {
        category: _top_counter(counter, top_k_signals, key_name="signal")
        for category, counter in signal_by_category.items()
    }

    ratio_by_category = _ratio_map(by_category, total_failures)
    ratio_by_severity = _ratio_map(by_severity, total_failures)

    runs_without_failures = max(0, total_runs - runs_with_failures)
    failure_run_rate = (runs_with_failures / total_runs) if total_runs > 0 else 0.0
    no_failure_run_rate = (runs_without_failures / total_runs) if total_runs > 0 else 0.0
    mean_failures_per_run = (total_failures / total_runs) if total_runs > 0 else 0.0

    return {
        "total_runs": total_runs,
        "runs_with_failures": runs_with_failures,
        "runs_without_failures": runs_without_failures,
        "failure_run_rate": failure_run_rate,
        "no_failure_run_rate": no_failure_run_rate,
        "total_failures": total_failures,
        "mean_failures_per_run": mean_failures_per_run,
        "mean_score_gap": mean(gap_values) if gap_values else 0.0,
        "by_category": {name: int(by_category[name]) for name in FAILURE_CATEGORIES},
        "by_category_ratio": ratio_by_category,
        "by_severity": {name: int(by_severity[name]) for name in FAILURE_SEVERITIES},
        "by_severity_ratio": ratio_by_severity,
        "top_signals": overall_top_signals,
        "top_signals_by_category": top_signals_by_category,
        "top_failure_task_categories": _top_counter(
            by_task_category,
            top_k_signals,
            key_name="task_category",
        ),
        "top_failure_tasks": _top_counter(by_task_id, top_k_signals, key_name="task_id"),
        "severe_cases_top": severe_items[:top_k_cases],
        "calibration_hints": build_calibration_hints(
            by_category_ratio=ratio_by_category,
            top_signals_by_category=top_signals_by_category,
        ),
    }


def build_calibration_hints(
    *,
    by_category_ratio: dict[str, float],
    top_signals_by_category: dict[str, list[dict[str, Any]]],
) -> list[str]:
    hints: list[str] = []
    sorted_categories = sorted(
        by_category_ratio.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    for category, ratio in sorted_categories:
        if ratio <= 0:
            continue
        top_signals = top_signals_by_category.get(category, [])
        signal_names = [str(row.get("signal", "")) for row in top_signals[:3] if row.get("signal")]
        joined = ", ".join(signal_names) if signal_names else "no clear signal"
        hints.append(
            f"{category}: ratio={ratio:.2%}, top_signals=[{joined}]",
        )
    if not hints:
        hints.append("No failure signals found; taxonomy calibration can focus on edge cases.")
    return hints


def _top_counter(counter: Counter[str], top_k: int, *, key_name: str) -> list[dict[str, Any]]:
    return [
        {key_name: name, "count": int(count)}
        for name, count in counter.most_common(top_k)
    ]


def _ratio_map(counter: Counter[str], denominator: int) -> dict[str, float]:
    if denominator <= 0:
        return {key: 0.0 for key in counter}
    return {key: counter[key] / denominator for key in counter}


def _to_float(value: Any, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default
