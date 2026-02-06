from __future__ import annotations

from graph_agent_automated.domain.models import CaseExecution
from graph_agent_automated.infrastructure.optimization.prompt_optimizer import (
    CandidatePromptOptimizer,
)


def _failures() -> list[CaseExecution]:
    return [
        CaseExecution(
            case_id="c1",
            question="q1",
            expected="e1",
            output="o1",
            score=0.2,
            rationale="missing evidence and fallback process",
            latency_ms=10.0,
            token_cost=0.001,
        ),
        CaseExecution(
            case_id="c2",
            question="q2",
            expected="e2",
            output="o2",
            score=0.3,
            rationale="schema mismatch in analytics branch",
            latency_ms=11.0,
            token_cost=0.0012,
        ),
    ]


def test_candidate_prompt_optimizer_returns_improved_prompt_and_registry() -> None:
    optimizer = CandidatePromptOptimizer(max_candidates=4)
    prompt = "Answer graph question"

    optimized = optimizer.optimize(prompt=prompt, failures=_failures(), task_desc="graph analytics")

    assert optimized
    variants = optimizer.registry.list()
    assert len(variants) >= 2
    assert all(0.0 <= item.score <= 1.0 for item in variants)
    assert any("evidence" in item.prompt.lower() for item in variants)
