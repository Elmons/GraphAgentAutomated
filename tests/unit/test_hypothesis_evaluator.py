from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph_agent_automated.infrastructure.evaluation.hypothesis_evaluator import (
    evaluate_hypothesis,
    load_hypothesis_spec,
)


def _arm_report(mean_delta: float = 0.02) -> dict[str, object]:
    return {
        "baseline_arm": "full_system",
        "targets": [
            {
                "target_arm": "idea_failure_aware_mutation",
                "summary": {
                    "n_pairs": 30,
                    "mean_score_delta": mean_delta,
                    "score_delta_std": 0.08,
                    "score_delta_ci95": [-0.01, 0.05],
                    "p10_score_delta": -0.03,
                    "win_rate": 0.57,
                    "loss_rate": 0.36,
                    "tie_rate": 0.07,
                    "wilcoxon": {"p_value": 0.11},
                    "cliffs_delta": {"value": 0.09, "magnitude": "negligible"},
                },
            }
        ],
    }


def test_load_hypothesis_spec_v1() -> None:
    spec = load_hypothesis_spec("docs/benchmarks/hypothesis_idea1_v1.json")
    assert spec.hypothesis_id == "idea1_failure_aware_mutation"
    assert spec.baseline_arm == "full_system"
    assert spec.target_arm == "idea_failure_aware_mutation"


def test_evaluate_hypothesis_supported() -> None:
    spec = load_hypothesis_spec("docs/benchmarks/hypothesis_idea1_v1.json")
    report = evaluate_hypothesis(arm_comparison_report=_arm_report(), spec=spec)
    assert report["supported"] is True
    assert all(item["passed"] for item in report["checks"])


def test_evaluate_hypothesis_not_supported_when_mean_delta_negative() -> None:
    spec = load_hypothesis_spec("docs/benchmarks/hypothesis_idea1_v1.json")
    report = evaluate_hypothesis(arm_comparison_report=_arm_report(mean_delta=-0.05), spec=spec)
    assert report["supported"] is False
    failed = [item for item in report["checks"] if not item["passed"]]
    assert failed


def test_load_hypothesis_spec_rejects_missing_fields(tmp_path: Path) -> None:
    bad_payload = {
        "hypothesis_id": "h",
        "version": "1.0.0",
        "baseline_arm": "full_system",
        "criteria": {
            "min_pairs": 10,
            "min_mean_score_delta": 0.0,
            "min_ci95_lower_bound": -0.1,
            "min_p10_score_delta": -0.1,
            "max_score_delta_std": 0.2,
            "min_win_rate": 0.3,
            "require_wilcoxon_significance": False,
            "wilcoxon_alpha": 0.05,
            "min_cliffs_delta": -0.1,
        },
    }
    file_path = tmp_path / "bad_hypothesis.json"
    file_path.write_text(json.dumps(bad_payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="target_arm"):
        load_hypothesis_spec(file_path)
