from __future__ import annotations

from graph_agent_automated.domain.models import CaseExecution, EvaluationSummary
from graph_agent_automated.infrastructure.evaluation.failure_taxonomy import (
    build_failure_taxonomy,
    classify_failure_case,
    classify_failure_severity,
)


def _case(case_id: str, score: float, output: str, rationale: str) -> CaseExecution:
    return CaseExecution(
        case_id=case_id,
        question=f"question-{case_id}",
        expected=f"expected-{case_id}",
        output=output,
        score=score,
        rationale=rationale,
        latency_ms=10.0,
        token_cost=0.001,
    )


def _summary(cases: list[CaseExecution]) -> EvaluationSummary:
    return EvaluationSummary(
        blueprint_id="bp",
        mean_score=sum(case.score for case in cases) / len(cases),
        mean_latency_ms=10.0,
        mean_token_cost=0.001,
        total_cases=len(cases),
        reflection="summary",
        case_results=cases,
    )


def test_build_failure_taxonomy_counts_expected_categories() -> None:
    auto_cases = [
        _case("c1", 0.2, "RUNTIME_ERROR[TIMEOUT]: executor timeout", "runtime fail"),
        _case("c2", 0.4, "normal output", "wrong tool selection: missing tool"),
        _case("c3", 0.5, "normal output", "expected mismatch with verifier format"),
        _case("c4", 0.45, "normal output", "decomposition missed step"),
        _case("c5", 0.75, "normal output", "tiny gap should be ignored"),
    ]
    manual_cases = [
        _case("c1", 0.8, "manual", "manual"),
        _case("c2", 0.7, "manual", "manual"),
        _case("c3", 0.7, "manual", "manual"),
        _case("c4", 0.65, "manual", "manual"),
        _case("c5", 0.76, "manual", "manual"),
    ]

    taxonomy = build_failure_taxonomy(
        auto_eval=_summary(auto_cases),
        manual_eval=_summary(manual_cases),
        failure_margin=0.05,
    )

    assert taxonomy["total_failures"] == 4
    assert taxonomy["by_category"]["execution_grounding"] == 1
    assert taxonomy["by_category"]["tool_selection"] == 1
    assert taxonomy["by_category"]["verifier_mismatch"] == 1
    assert taxonomy["by_category"]["decomposition"] == 1
    assert taxonomy["by_severity"]["severe"] == 1
    assert taxonomy["by_severity"]["moderate"] == 3


def test_classify_failure_case_fallback_and_severity() -> None:
    auto_case = _case("c1", 0.1, "generic output", "generic rationale")
    manual_case = _case("c1", 0.5, "manual output", "manual rationale")

    category, signal = classify_failure_case(auto_case, manual_case)
    severity = classify_failure_severity(auto_case.score, manual_case.score)

    assert category == "decomposition"
    assert signal == "manual_gap>=0.2"
    assert severity == "severe"
