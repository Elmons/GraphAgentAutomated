from __future__ import annotations

import json
from dataclasses import dataclass

from openai import OpenAI

from graph_agent_automated.core.config import Settings
from graph_agent_automated.domain.protocols import LLMJudge


class HeuristicJudge(LLMJudge):
    """Deterministic judge for local testing without external models."""

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
            "You are a strict evaluator. Return JSON with keys score (0..1 float) and rationale.\n"
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
        text = response.output_text
        score, rationale = self._parse(text)
        return score, rationale

    def _parse(self, text: str) -> tuple[float, str]:
        fallback = (0.0, f"unable to parse judge response: {text[:120]}")
        try:
            payload = json.loads(text)
            score = float(payload.get("score", 0.0))
            rationale = str(payload.get("rationale", ""))
            return max(0.0, min(1.0, score)), rationale
        except Exception:
            return fallback
