from __future__ import annotations

from graph_agent_automated.domain.enums import Difficulty, TaskIntent, TopologyPattern
from graph_agent_automated.domain.models import (
    ActionSpec,
    ExpertBlueprint,
    OperatorBlueprint,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.evaluation.judges import (
    EnsembleJudge,
    HeuristicJudge,
    RuleBasedJudge,
)
from graph_agent_automated.infrastructure.evaluation.workflow_evaluator import (
    ReflectionWorkflowEvaluator,
)
from graph_agent_automated.infrastructure.runtime.mock_runtime import MockRuntimeAdapter


def _build_blueprint() -> WorkflowBlueprint:
    operator = OperatorBlueprint(
        name="worker",
        instruction="answer graph question",
        output_schema="answer: str",
        actions=["use_cypherexecutor"],
    )
    expert = ExpertBlueprint(
        name="GraphTaskExpert",
        description="desc",
        operators=[operator],
    )
    return WorkflowBlueprint(
        blueprint_id="bp-1",
        app_name="demo",
        task_desc="task",
        topology=TopologyPattern.LINEAR,
        tools=[ToolSpec(name="CypherExecutor")],
        actions=[ActionSpec(name="use_cypherexecutor", description="d", tools=["CypherExecutor"])],
        experts=[expert],
        leader_actions=["use_cypherexecutor"],
    )


def test_reflection_evaluator_runs_cases() -> None:
    runtime = MockRuntimeAdapter()
    judge = HeuristicJudge()
    evaluator = ReflectionWorkflowEvaluator(runtime=runtime, judge=judge)

    blueprint = _build_blueprint()
    cases = [
        SyntheticCase(
            case_id="c1",
            question="Find Person by OWNS",
            verifier="UNKNOWN",
            intent=TaskIntent.QUERY,
            difficulty=Difficulty.L1,
        )
    ]

    summary = evaluator.evaluate(blueprint, cases)

    assert summary.total_cases == 1
    assert 0.0 <= summary.mean_score <= 1.0
    assert len(summary.case_results) == 1
    assert summary.reflection


def test_reflection_evaluator_with_ensemble_exposes_reliability_fields() -> None:
    runtime = MockRuntimeAdapter()
    judge = EnsembleJudge(
        judges=[
            ("rule", RuleBasedJudge(), 1.0),
            ("heuristic", HeuristicJudge(), 1.0),
        ]
    )
    evaluator = ReflectionWorkflowEvaluator(runtime=runtime, judge=judge)
    blueprint = _build_blueprint()
    cases = [
        SyntheticCase(
            case_id="c2",
            question="Find Person by OWNS",
            verifier="UNKNOWN",
            intent=TaskIntent.QUERY,
            difficulty=Difficulty.L1,
        )
    ]

    summary = evaluator.evaluate(blueprint, cases, split="val")

    assert summary.split == "val"
    assert 0.0 <= summary.judge_agreement <= 1.0
    assert summary.case_results[0].judge_votes
    assert 0.0 <= summary.case_results[0].confidence <= 1.0
