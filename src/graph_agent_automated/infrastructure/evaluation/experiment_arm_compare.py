from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

from graph_agent_automated.infrastructure.evaluation.parity_statistics import (
    cliffs_delta,
    paired_bootstrap_mean_ci,
    wilcoxon_signed_rank,
)


def analyze_arm_comparison(
    records: list[dict[str, Any]],
    *,
    baseline_arm: str = "full_system",
    target_arms: list[str] | None = None,
) -> dict[str, Any]:
    all_arms = sorted({str(row.get("arm", "")).strip() for row in records if str(row.get("arm", "")).strip()})
    if baseline_arm not in all_arms:
        raise ValueError(f"baseline arm not found in records: {baseline_arm}")

    resolved_targets = target_arms or [arm for arm in all_arms if arm != baseline_arm]
    result_rows: list[dict[str, Any]] = []
    for target_arm in resolved_targets:
        if target_arm == baseline_arm:
            continue
        pairs = collect_paired_runs(records, baseline_arm=baseline_arm, target_arm=target_arm)
        result_rows.append(
            {
                "target_arm": target_arm,
                "n_pairs": len(pairs),
                "summary": summarize_pairs(pairs),
                "by_category": summarize_pairs_by(pairs, field="task_category"),
                "by_task": summarize_pairs_by(pairs, field="task_id"),
            }
        )

    return {
        "baseline_arm": baseline_arm,
        "targets": result_rows,
    }


def collect_paired_runs(
    records: list[dict[str, Any]],
    *,
    baseline_arm: str,
    target_arm: str,
) -> list[dict[str, Any]]:
    baseline_map = _index_records_by_key(records, arm=baseline_arm)
    target_map = _index_records_by_key(records, arm=target_arm)
    keys = sorted(set(baseline_map).intersection(target_map))

    output: list[dict[str, Any]] = []
    for key in keys:
        baseline_row = baseline_map[key]
        target_row = target_map[key]
        baseline_score = _to_float(baseline_row.get("test_score"), "test_score")
        target_score = _to_float(target_row.get("test_score"), "test_score")
        output.append(
            {
                "task_id": str(target_row.get("task_id") or baseline_row.get("task_id") or ""),
                "task_category": str(
                    target_row.get("task_category") or baseline_row.get("task_category") or ""
                ),
                "seed": int(target_row.get("seed") or baseline_row.get("seed") or 0),
                "baseline_arm": baseline_arm,
                "target_arm": target_arm,
                "baseline_score": baseline_score,
                "target_score": target_score,
                "score_delta": target_score - baseline_score,
            }
        )
    return output


def summarize_pairs(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    if not pairs:
        return {
            "n_pairs": 0,
            "mean_score_delta": 0.0,
            "score_delta_std": 0.0,
            "score_delta_ci95": [0.0, 0.0],
            "p10_score_delta": 0.0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "tie_rate": 0.0,
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

    deltas = [_to_float(row["score_delta"], "score_delta") for row in pairs]
    target_scores = [_to_float(row["target_score"], "target_score") for row in pairs]
    baseline_scores = [_to_float(row["baseline_score"], "baseline_score") for row in pairs]
    ci_lo, ci_hi = paired_bootstrap_mean_ci(deltas)
    wilcoxon = wilcoxon_signed_rank(target_scores, baseline_scores)
    cliffs_value, cliffs_magnitude = cliffs_delta(target_scores, baseline_scores)

    wins = sum(1 for delta in deltas if delta > 0)
    losses = sum(1 for delta in deltas if delta < 0)
    ties = len(deltas) - wins - losses

    return {
        "n_pairs": len(pairs),
        "mean_score_delta": mean(deltas),
        "score_delta_std": pstdev(deltas) if len(deltas) > 1 else 0.0,
        "score_delta_ci95": [ci_lo, ci_hi],
        "p10_score_delta": percentile(deltas, 0.10),
        "win_rate": wins / len(deltas),
        "loss_rate": losses / len(deltas),
        "tie_rate": ties / len(deltas),
        "wilcoxon": wilcoxon,
        "cliffs_delta": {"value": cliffs_value, "magnitude": cliffs_magnitude},
    }


def summarize_pairs_by(pairs: list[dict[str, Any]], *, field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pairs:
        key = str(row.get(field) or "")
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for key in sorted(grouped):
        row_summary = summarize_pairs(grouped[key])
        output.append(
            {
                field: key,
                **row_summary,
            }
        )
    return output


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    if not (0.0 <= ratio <= 1.0):
        raise ValueError("ratio must be in [0, 1]")

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = ratio * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    weight = position - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def _index_records_by_key(records: list[dict[str, Any]], *, arm: str) -> dict[tuple[str, int], dict[str, Any]]:
    output: dict[tuple[str, int], dict[str, Any]] = {}
    for row in records:
        row_arm = str(row.get("arm") or "").strip()
        if row_arm != arm:
            continue
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("task_id must not be empty")
        seed_row = row.get("seed")
        if isinstance(seed_row, bool) or not isinstance(seed_row, int):
            raise ValueError("seed must be integer")
        key = (task_id, seed_row)
        if key in output:
            raise ValueError(f"duplicate pair key for arm {arm}: {key}")
        output[key] = row
    return output


def _to_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be number")
    return float(value)
