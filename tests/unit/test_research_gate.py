from __future__ import annotations

from graph_agent_automated.infrastructure.evaluation.research_gate import (
    evaluate_research_gate,
    load_research_gate,
    percentile,
)


def test_load_research_gate_v1() -> None:
    gate = load_research_gate("docs/benchmarks/research_gate_v1.json")
    assert gate.gate_id == "research_gate_v1"
    assert gate.criteria.min_runs >= 1


def test_evaluate_research_gate_passes_on_strong_records() -> None:
    gate = load_research_gate("docs/benchmarks/research_gate_v1.json")

    records = []
    for i in range(24):
        records.append(
            {
                "score_delta": 0.03 if i % 4 else -0.01,
                "parity_achieved": i % 5 != 0,
            }
        )

    parity_stats = {
        "mean_score_delta_ci95": [-0.01, 0.04],
        "mean_auto_latency_ms": 12000.0,
        "mean_auto_token_cost": 0.04,
        "wilcoxon": {"p_value": 0.08},
    }
    failure_taxonomy_summary = {
        "by_severity_ratio": {"mild": 0.55, "moderate": 0.35, "severe": 0.1}
    }

    report = evaluate_research_gate(
        records=records,
        parity_stats=parity_stats,
        failure_taxonomy_summary=failure_taxonomy_summary,
        gate=gate,
    )

    assert report["gate_passed"] is True
    assert len(report["checks"]) >= 9


def test_evaluate_research_gate_fails_when_parity_rate_too_low() -> None:
    gate = load_research_gate("docs/benchmarks/research_gate_v1.json")

    records = [
        {"score_delta": -0.2, "parity_achieved": False},
        {"score_delta": -0.18, "parity_achieved": False},
        {"score_delta": -0.1, "parity_achieved": False},
        {"score_delta": -0.05, "parity_achieved": True},
    ] * 6
    parity_stats = {
        "mean_score_delta_ci95": [-0.2, -0.06],
        "mean_auto_latency_ms": 5000.0,
        "mean_auto_token_cost": 0.03,
        "wilcoxon": {"p_value": 0.12},
    }
    failure_taxonomy_summary = {
        "by_severity_ratio": {"mild": 0.1, "moderate": 0.3, "severe": 0.6}
    }

    report = evaluate_research_gate(
        records=records,
        parity_stats=parity_stats,
        failure_taxonomy_summary=failure_taxonomy_summary,
        gate=gate,
    )

    assert report["gate_passed"] is False
    failed = [item for item in report["checks"] if not item["passed"]]
    assert failed


def test_percentile_interpolates() -> None:
    values = [1.0, 2.0, 10.0]
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 1.0) == 10.0
    assert percentile(values, 0.5) == 2.0
