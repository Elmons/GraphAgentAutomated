from __future__ import annotations

from statistics import mean
from typing import Sequence

from graph_agent_automated.domain.models import (
    CaseExecution,
    EvaluationSummary,
    SyntheticCase,
    WorkflowBlueprint,
)
from graph_agent_automated.domain.protocols import LLMJudge, RuntimeAdapter, WorkflowEvaluator


class ReflectionWorkflowEvaluator(WorkflowEvaluator):
    """Evaluate workflow candidates and generate reflection feedback."""

    def __init__(
        self,
        runtime: RuntimeAdapter,
        judge: LLMJudge,
        rubric: str | None = None,
    ):
        self._runtime = runtime
        self._judge = judge
        self._rubric = rubric or (
            "Score by factual correctness, graph-domain precision, and task completion."
        )

    def evaluate(self, blueprint: WorkflowBlueprint, cases: Sequence[SyntheticCase]) -> EvaluationSummary:
        results: list[CaseExecution] = []
        for case in cases:
            execution = self._runtime.execute_case(blueprint, case)
            score, rationale = self._judge.judge(
                question=case.question,
                expected=case.verifier,
                prediction=execution.output,
                rubric=self._rubric,
            )
            execution.score = score
            execution.rationale = rationale
            results.append(execution)

        if not results:
            return EvaluationSummary(
                blueprint_id=blueprint.blueprint_id,
                mean_score=0.0,
                mean_latency_ms=0.0,
                mean_token_cost=0.0,
                total_cases=0,
                reflection="no evaluation results",
                case_results=[],
            )

        reflection = self._reflect(results)
        return EvaluationSummary(
            blueprint_id=blueprint.blueprint_id,
            mean_score=mean([result.score for result in results]),
            mean_latency_ms=mean([result.latency_ms for result in results]),
            mean_token_cost=mean([result.token_cost for result in results]),
            total_cases=len(results),
            reflection=reflection,
            case_results=results,
        )

    def _reflect(self, results: Sequence[CaseExecution]) -> str:
        failed = [result for result in results if result.score < 0.6]
        if not failed:
            return "stable candidate, preserve current constraints and evidence discipline"

        snippets = [
            f"{case.case_id} score={case.score:.2f} reason={case.rationale}" for case in failed[:3]
        ]
        snippets.append("Improve prompt grounding, prune noisy tools, and add reviewer checks.")
        return " | ".join(snippets)
