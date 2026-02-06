from __future__ import annotations

import json
from dataclasses import dataclass, field
from statistics import mean, pstdev

from openai import OpenAI

from graph_agent_automated.core.config import Settings
from graph_agent_automated.domain.models import JudgeVote
from graph_agent_automated.domain.protocols import LLMJudge


class RuleBasedJudge(LLMJudge):
    """Rule-based judge prioritizing strict answer consistency checks."""

    def judge(self, question: str, expected: str, prediction: str, rubric: str) -> tuple[float, str]:
        normalized_expected = expected.strip().lower()
        normalized_prediction = prediction.strip().lower()

        if not normalized_prediction:
            return 0.0, "empty output"
        if normalized_expected and normalized_expected != "unknown":
            if normalized_expected in normalized_prediction:
                return 0.95, "expected answer included"
            if normalized_prediction in normalized_expected:
                return 0.75, "prediction is partial expected answer"
            return 0.2, "expected answer not supported"

        # No trusted reference: fallback to conservative structure checks.
        if "unknown" in normalized_prediction:
            return 0.65, "uncertainty explicitly stated"
        if len(normalized_prediction.split()) < 4:
            return 0.3, "insufficient answer detail"
        return 0.55, "rule-based plausibility"


class HeuristicJudge(LLMJudge):
    """Deterministic lexical overlap judge for local validation."""

    def judge(self, question: str, expected: str, prediction: str, rubric: str) -> tuple[float, str]:
        normalized_expected = expected.strip().lower()
        normalized_prediction = prediction.strip().lower()
        if not normalized_prediction:
            return 0.0, "empty prediction"

        if normalized_expected and normalized_expected != "unknown":
            if normalized_expected == normalized_prediction:
                return 1.0, "exact match"
            overlap = self._overlap(normalized_expected, normalized_prediction)
            return overlap, f"token overlap={overlap:.2f}"

        overlap = self._overlap(question.lower(), normalized_prediction)
        return max(0.1, min(0.8, overlap)), "weak-supervision overlap"

    def _overlap(self, lhs: str, rhs: str) -> float:
        lhs_tokens = set(lhs.split())
        rhs_tokens = set(rhs.split())
        if not lhs_tokens:
            return 0.0
        return len(lhs_tokens & rhs_tokens) / len(lhs_tokens)


@dataclass
class OpenAIJudge(LLMJudge):
    """LLM-as-a-judge implementation based on OpenAI-compatible API."""

    settings: Settings

    def __post_init__(self) -> None:
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when JUDGE_BACKEND=openai")

        client_args: dict[str, str] = {"api_key": self.settings.openai_api_key}
        if self.settings.openai_base_url:
            client_args["base_url"] = self.settings.openai_base_url
        self._client = OpenAI(**client_args)

    def judge(self, question: str, expected: str, prediction: str, rubric: str) -> tuple[float, str]:
        prompt = (
            "You are a strict evaluator. Return valid JSON only: "
            "{\"score\": <0..1 float>, \"rationale\": <string>}\n"
            f"Rubric: {rubric}\n"
            f"Question: {question}\n"
            f"Expected: {expected}\n"
            f"Prediction: {prediction}\n"
        )

        response = self._client.responses.create(
            model=self.settings.judge_model,
            input=prompt,
            temperature=0,
        )
        return self._parse(response.output_text)

    def _parse(self, text: str) -> tuple[float, str]:
        fallback = (0.0, f"unable to parse judge response: {text[:120]}")
        try:
            payload = json.loads(text)
            score = float(payload.get("score", 0.0))
            rationale = str(payload.get("rationale", ""))
            return max(0.0, min(1.0, score)), rationale
        except Exception:
            return fallback


@dataclass
class EnsembleJudge(LLMJudge):
    """Weighted multi-judge aggregator with reliability signals."""

    judges: list[tuple[str, LLMJudge, float]]
    last_votes: list[JudgeVote] = field(default_factory=list)
    last_agreement: float = 0.0
    last_confidence: float = 0.0

    def judge(self, question: str, expected: str, prediction: str, rubric: str) -> tuple[float, str]:
        if not self.judges:
            raise ValueError("EnsembleJudge requires at least one judge")

        votes: list[JudgeVote] = []
        weighted_scores: list[float] = []
        weights: list[float] = []

        for judge_name, judge, weight in self.judges:
            score, rationale = judge.judge(question, expected, prediction, rubric)
            votes.append(JudgeVote(judge_name=judge_name, score=score, rationale=rationale))
            weighted_scores.append(max(0.0, min(1.0, score)) * weight)
            weights.append(weight)

        denom = sum(weights) if sum(weights) > 0 else float(len(weights))
        score = sum(weighted_scores) / denom

        agreement = self._agreement([vote.score for vote in votes])
        confidence = max(0.0, min(1.0, 0.5 * score + 0.5 * agreement))

        self.last_votes = votes
        self.last_agreement = agreement
        self.last_confidence = confidence

        rationale = " | ".join(f"{vote.judge_name}:{vote.rationale}" for vote in votes)
        return score, rationale

    def _agreement(self, scores: list[float]) -> float:
        if len(scores) <= 1:
            return 1.0
        deviation = pstdev(scores)
        normalized = max(0.0, min(1.0, 1.0 - deviation))
        # Also reward concentration near the mean.
        mean_score = mean(scores)
        closeness = mean([1.0 - abs(score - mean_score) for score in scores])
        return max(0.0, min(1.0, 0.5 * normalized + 0.5 * closeness))


def build_default_judge_ensemble(settings: Settings) -> EnsembleJudge:
    """Build default judge ensemble.

    - Always include rule-based and heuristic judges.
    - Optionally include OpenAI judge when backend is configured.
    """
    judges: list[tuple[str, LLMJudge, float]] = [
        ("rule", RuleBasedJudge(), 1.0),
        ("heuristic", HeuristicJudge(), 1.0),
    ]
    if settings.judge_backend.lower() == "openai":
        judges.append(("openai", OpenAIJudge(settings), 1.4))
    return EnsembleJudge(judges=judges)
