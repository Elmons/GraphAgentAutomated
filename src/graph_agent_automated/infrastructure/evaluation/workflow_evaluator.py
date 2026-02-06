from __future__ import annotations

from statistics import mean, pstdev
from typing import Sequence

from graph_agent_automated.domain.models import (
    CaseExecution,
    EvaluationSummary,
    JudgeVote,
    SyntheticCase,
    WorkflowBlueprint,
)
from graph_agent_automated.domain.protocols import LLMJudge, RuntimeAdapter, WorkflowEvaluator


class ReflectionWorkflowEvaluator(WorkflowEvaluator):
    """Evaluate workflow candidates and generate reflection feedback.

    Supports both single-judge and ensemble-judge modes. When ensemble metadata
    is available (votes/agreement/confidence), it is attached to case execution.
    """

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

    def evaluate(
        self,
        blueprint: WorkflowBlueprint,
        cases: Sequence[SyntheticCase],
        split: str = "train",
    ) -> EvaluationSummary:
        results: list[CaseExecution] = []
        agreements: list[float] = []

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

            # Optional ensemble metadata.
            votes = getattr(self._judge, "last_votes", None)
            if isinstance(votes, list):
                execution.judge_votes = [
                    vote
                    if isinstance(vote, JudgeVote)
                    else JudgeVote(
                        judge_name=str(getattr(vote, "judge_name", "unknown")),
                        score=float(getattr(vote, "score", 0.0)),
                        rationale=str(getattr(vote, "rationale", "")),
                    )
                    for vote in votes
                ]

            confidence = getattr(self._judge, "last_confidence", None)
            if isinstance(confidence, (int, float)):
                execution.confidence = float(max(0.0, min(1.0, confidence)))

            agreement = getattr(self._judge, "last_agreement", None)
            if isinstance(agreement, (int, float)):
                agreements.append(float(max(0.0, min(1.0, agreement))))

            results.append(execution)

        if not results:
            return EvaluationSummary(
                blueprint_id=blueprint.blueprint_id,
                mean_score=0.0,
                mean_latency_ms=0.0,
                mean_token_cost=0.0,
                total_cases=0,
                reflection="no evaluation results",
                split=split,
                case_results=[],
            )

        scores = [result.score for result in results]
        reflection = self._reflect(results, split)
        return EvaluationSummary(
            blueprint_id=blueprint.blueprint_id,
            mean_score=mean(scores),
            mean_latency_ms=mean([result.latency_ms for result in results]),
            mean_token_cost=mean([result.token_cost for result in results]),
            total_cases=len(results),
            reflection=reflection,
            judge_agreement=mean(agreements) if agreements else 1.0,
            score_std=pstdev(scores) if len(scores) > 1 else 0.0,
            split=split,
            case_results=results,
        )

    def _reflect(self, results: Sequence[CaseExecution], split: str) -> str:
        failed = [result for result in results if result.score < 0.6]
        if not failed:
            return f"{split}: stable candidate, preserve current constraints and evidence discipline"

        snippets = [
            f"{case.case_id} score={case.score:.2f} confidence={case.confidence:.2f} reason={case.rationale}"
            for case in failed[:3]
        ]
        snippets.append("Improve prompt grounding, prune noisy tools, and add reviewer checks.")
        return " | ".join(snippets)
