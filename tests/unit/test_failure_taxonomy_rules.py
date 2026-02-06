from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph_agent_automated.domain.models import CaseExecution
from graph_agent_automated.infrastructure.evaluation.failure_taxonomy import (
    classify_failure_case,
    classify_failure_severity,
    load_failure_taxonomy_rules,
)


def _case(score: float, output: str, rationale: str) -> CaseExecution:
    return CaseExecution(
        case_id="c1",
        question="q",
        expected="e",
        output=output,
        score=score,
        rationale=rationale,
        latency_ms=1.0,
        token_cost=0.001,
    )


def test_load_failure_taxonomy_rules_v1() -> None:
    rules = load_failure_taxonomy_rules("docs/benchmarks/failure_taxonomy_rules_v1.json")
    assert rules.rules_id == "failure_taxonomy_rules_v1"
    assert "timeout" in rules.execution_keywords
    assert rules.severe_gap_threshold == 0.4


def test_load_failure_taxonomy_rules_rejects_bad_thresholds(tmp_path: Path) -> None:
    payload = {
        "rules_id": "bad",
        "version": "1.0.0",
        "keywords": {
            "execution_grounding": ["timeout"],
            "tool_selection": ["tool"],
            "decomposition": ["step"],
            "verifier_mismatch": ["expected"],
        },
        "thresholds": {
            "severe_gap": 0.2,
            "moderate_gap": 0.3,
            "fallback_decomposition_gap": 0.2,
        },
    }
    file_path = tmp_path / "bad_rules.json"
    file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="moderate_gap must be <="):
        load_failure_taxonomy_rules(file_path)


def test_classification_uses_custom_rules(tmp_path: Path) -> None:
    payload = {
        "rules_id": "custom",
        "version": "1.0.0",
        "keywords": {
            "execution_grounding": ["custom_exec"],
            "tool_selection": ["custom_tool"],
            "decomposition": ["custom_decomp"],
            "verifier_mismatch": ["custom_verifier"],
        },
        "thresholds": {
            "severe_gap": 0.5,
            "moderate_gap": 0.25,
            "fallback_decomposition_gap": 0.3,
        },
    }
    file_path = tmp_path / "custom_rules.json"
    file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    rules = load_failure_taxonomy_rules(file_path)

    auto_case = _case(0.2, "output", "contains custom_tool")
    manual_case = _case(0.8, "manual", "manual")
    category, signal = classify_failure_case(auto_case, manual_case, rules=rules)
    severity = classify_failure_severity(auto_case.score, manual_case.score, rules=rules)

    assert category == "tool_selection"
    assert signal == "custom_tool"
    assert severity == "severe"
