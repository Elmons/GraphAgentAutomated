from __future__ import annotations

import pytest

from graph_agent_automated.infrastructure.evaluation.experiment_arm_compare import (
    analyze_arm_comparison,
    collect_paired_runs,
    summarize_pairs,
)


def _records_fixture() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for task_id in ("t1", "t2"):
        for seed in (1, 2, 3):
            baseline_score = 0.70 + seed * 0.01
            idea_score = baseline_score + 0.03
            records.append(
                {
                    "arm": "full_system",
                    "task_id": task_id,
                    "task_category": "query" if task_id == "t1" else "analytics",
                    "seed": seed,
                    "test_score": baseline_score,
                }
            )
            records.append(
                {
                    "arm": "idea_failure_aware_mutation",
                    "task_id": task_id,
                    "task_category": "query" if task_id == "t1" else "analytics",
                    "seed": seed,
                    "test_score": idea_score,
                }
            )
    return records


def test_collect_paired_runs_by_task_and_seed() -> None:
    pairs = collect_paired_runs(
        _records_fixture(),
        baseline_arm="full_system",
        target_arm="idea_failure_aware_mutation",
    )
    assert len(pairs) == 6
    assert all(abs(float(pair["score_delta"]) - 0.03) < 1e-9 for pair in pairs)


def test_summarize_pairs_reports_positive_shift() -> None:
    pairs = collect_paired_runs(
        _records_fixture(),
        baseline_arm="full_system",
        target_arm="idea_failure_aware_mutation",
    )
    summary = summarize_pairs(pairs)
    assert summary["n_pairs"] == 6
    assert summary["mean_score_delta"] > 0
    assert summary["win_rate"] == 1.0
    assert summary["loss_rate"] == 0.0


def test_analyze_arm_comparison_contains_task_and_category_breakdown() -> None:
    report = analyze_arm_comparison(
        _records_fixture(),
        baseline_arm="full_system",
        target_arms=["idea_failure_aware_mutation"],
    )
    assert report["baseline_arm"] == "full_system"
    assert len(report["targets"]) == 1
    row = report["targets"][0]
    assert row["target_arm"] == "idea_failure_aware_mutation"
    assert row["summary"]["n_pairs"] == 6
    assert len(row["by_category"]) == 2
    assert len(row["by_task"]) == 2


def test_collect_paired_runs_rejects_duplicate_key() -> None:
    records = _records_fixture()
    records.append(
        {
            "arm": "full_system",
            "task_id": "t1",
            "task_category": "query",
            "seed": 1,
            "test_score": 0.91,
        }
    )
    with pytest.raises(ValueError, match="duplicate pair key"):
        collect_paired_runs(
            records,
            baseline_arm="full_system",
            target_arm="idea_failure_aware_mutation",
        )
