from __future__ import annotations

from graph_agent_automated.infrastructure.evaluation.failure_taxonomy_report import (
    analyze_failure_taxonomy_records,
)


def test_analyze_failure_taxonomy_records_basic_aggregation() -> None:
    records = [
        {
            "task_id": "query_01",
            "task_category": "query",
            "seed": 1,
            "failure_taxonomy": {
                "total_failures": 2,
                "case_items": [
                    {
                        "case_id": "c1",
                        "category": "tool_selection",
                        "severity": "moderate",
                        "signal": "missing tool",
                        "score_gap": 0.32,
                        "auto_score": 0.41,
                        "manual_score": 0.73,
                    },
                    {
                        "case_id": "c2",
                        "category": "execution_grounding",
                        "severity": "severe",
                        "signal": "timeout",
                        "score_gap": 0.61,
                        "auto_score": 0.21,
                        "manual_score": 0.82,
                    },
                ],
            },
        },
        {
            "task_id": "query_01",
            "task_category": "query",
            "seed": 2,
            "failure_taxonomy": {
                "total_failures": 0,
                "case_items": [],
            },
        },
        {
            "task_id": "analytics_01",
            "task_category": "analytics",
            "seed": 1,
            "failure_taxonomy": {
                "total_failures": 1,
                "case_items": [
                    {
                        "case_id": "c3",
                        "category": "decomposition",
                        "severity": "mild",
                        "signal": "missing step",
                        "score_gap": 0.12,
                        "auto_score": 0.68,
                        "manual_score": 0.8,
                    }
                ],
            },
        },
    ]

    report = analyze_failure_taxonomy_records(records, top_k_signals=5, top_k_cases=5)

    assert report["total_runs"] == 3
    assert report["runs_with_failures"] == 2
    assert report["total_failures"] == 3
    assert report["by_category"]["tool_selection"] == 1
    assert report["by_category"]["execution_grounding"] == 1
    assert report["by_category"]["decomposition"] == 1
    assert report["by_severity"]["severe"] == 1
    assert report["by_severity"]["moderate"] == 1
    assert report["by_severity"]["mild"] == 1
    assert report["top_signals"][0]["signal"] == "missing tool"
    assert report["severe_cases_top"][0]["signal"] == "timeout"
    assert report["severe_cases_top"][0]["score_gap"] == 0.61
    assert report["calibration_hints"]


def test_analyze_failure_taxonomy_records_handles_empty_input() -> None:
    report = analyze_failure_taxonomy_records([], top_k_signals=3, top_k_cases=3)

    assert report["total_runs"] == 0
    assert report["total_failures"] == 0
    assert report["failure_run_rate"] == 0.0
    assert report["by_category_ratio"]["tool_selection"] == 0.0
    assert report["by_severity_ratio"]["severe"] == 0.0
    assert report["calibration_hints"] == [
        "No failure signals found; taxonomy calibration can focus on edge cases."
    ]
