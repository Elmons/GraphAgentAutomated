from __future__ import annotations

from graph_agent_automated.domain.enums import Difficulty, TaskIntent, TopologyPattern
from graph_agent_automated.domain.models import (
    ActionSpec,
    CaseExecution,
    EvaluationSummary,
    ExpertBlueprint,
    OperatorBlueprint,
    SearchConfig,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.optimization.prompt_optimizer import (
    ReflectionPromptOptimizer,
)
from graph_agent_automated.infrastructure.optimization.search_engine import AFlowXSearchEngine
from graph_agent_automated.infrastructure.optimization.tool_selector import IntentAwareToolSelector


class FakeEvaluator:
    def evaluate(self, blueprint: WorkflowBlueprint, cases: list[SyntheticCase]) -> EvaluationSummary:
        base = 0.4
        topology_bonus = {
            TopologyPattern.LINEAR: 0.0,
            TopologyPattern.PLANNER_WORKER_REVIEWER: 0.15,
            TopologyPattern.ROUTER_PARALLEL: 0.2,
        }[blueprint.topology]
        tool_bonus = min(0.2, len(blueprint.tools) * 0.03)
        score = min(0.95, base + topology_bonus + tool_bonus)

        case_results = [
            CaseExecution(
                case_id=case.case_id,
                question=case.question,
                expected=case.verifier,
                output="mock",
                score=score,
                rationale="fake",
                latency_ms=12.0,
                token_cost=0.003,
            )
            for case in cases
        ]

        return EvaluationSummary(
            blueprint_id=blueprint.blueprint_id,
            mean_score=score,
            mean_latency_ms=12.0,
            mean_token_cost=0.003,
            total_cases=len(cases),
            reflection="fake reflection",
            case_results=case_results,
        )


def _root_blueprint() -> WorkflowBlueprint:
    op = OperatorBlueprint(
        name="worker",
        instruction="solve",
        output_schema="answer",
        actions=["use_cypherexecutor"],
    )
    expert = ExpertBlueprint(name="Expert", description="d", operators=[op])
    return WorkflowBlueprint(
        blueprint_id="bp-root",
        app_name="demo",
        task_desc="query and analytics",
        topology=TopologyPattern.LINEAR,
        tools=[ToolSpec(name="CypherExecutor", description="query")],
        actions=[ActionSpec(name="use_cypherexecutor", description="d", tools=["CypherExecutor"])],
        experts=[expert],
        leader_actions=["use_cypherexecutor"],
    )


def _cases() -> list[SyntheticCase]:
    return [
        SyntheticCase(
            case_id=f"c{i}",
            question="Find nodes",
            verifier="UNKNOWN",
            intent=TaskIntent.QUERY,
            difficulty=Difficulty.L1,
        )
        for i in range(1, 6)
    ]


def test_search_engine_improves_or_keeps_best() -> None:
    engine = AFlowXSearchEngine(
        evaluator=FakeEvaluator(),
        prompt_optimizer=ReflectionPromptOptimizer(),
        tool_selector=IntentAwareToolSelector(),
        config=SearchConfig(rounds=4, expansions_per_round=2, patience=2),
    )

    tool_catalog = [
        ToolSpec(name="CypherExecutor", description="query", tags=["query"]),
        ToolSpec(name="PageRankExecutor", description="analysis", tags=["analysis"]),
    ]

    result = engine.optimize(
        root_blueprint=_root_blueprint(),
        cases=_cases(),
        intents=[TaskIntent.QUERY, TaskIntent.ANALYTICS],
        tool_catalog=tool_catalog,
    )

    assert result.history
    assert result.best_evaluation.total_cases > 0
    assert result.best_blueprint.blueprint_id
