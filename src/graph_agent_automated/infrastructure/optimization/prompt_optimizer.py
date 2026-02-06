from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from graph_agent_automated.domain.models import CaseExecution, PromptVariant
from graph_agent_automated.domain.protocols import PromptOptimizer


class PromptVariantRegistry:
    """In-memory registry for generated prompt variants.

    The registry is intentionally lightweight and serializable so that the
    application service can persist it inside optimization artifacts.
    """

    def __init__(self) -> None:
        self._variants: list[PromptVariant] = []

    def add(self, variant: PromptVariant) -> None:
        self._variants.append(variant)

    def list(self) -> list[PromptVariant]:
        return list(self._variants)

    def as_dict(self) -> list[dict[str, object]]:
        return [asdict(item) for item in self._variants]


class CandidatePromptOptimizer(PromptOptimizer):
    """Prompt optimizer with candidate generation and heuristic selection."""

    def __init__(self, max_candidates: int = 4):
        self._max_candidates = max(2, max_candidates)
        self._registry = PromptVariantRegistry()

    @property
    def registry(self) -> PromptVariantRegistry:
        return self._registry

    def optimize(self, prompt: str, failures: list[CaseExecution], task_desc: str) -> str:
        candidates = self.generate_candidates(prompt=prompt, failures=failures, task_desc=task_desc)
        scored = self.score_candidates(candidates, failures)
        best = max(scored, key=lambda item: item.score)
        for candidate in scored:
            self._registry.add(candidate)
        return best.prompt

    def generate_candidates(
        self,
        prompt: str,
        failures: list[CaseExecution],
        task_desc: str,
    ) -> list[str]:
        failure_hints = [entry.rationale for entry in failures[:3] if entry.rationale]
        failure_text = "; ".join(failure_hints) if failure_hints else "no explicit failure"

        candidates = [
            prompt,
            (
                f"{prompt.strip()}\n\n[Refined Constraints]\n"
                "- Use graph-tool evidence for every claim.\n"
                "- State unknown instead of hallucinating.\n"
                f"- Prior failure pattern: {failure_text}.\n"
            ),
            (
                f"{prompt.strip()}\n\n[Task Intent]\n{task_desc}\n"
                "[Output Discipline]\n"
                "1) Answer\n2) Evidence\n3) Assumptions"
            ),
            (
                f"{prompt.strip()}\n\n[Safety Checks]\n"
                "- Validate schema alignment before answering.\n"
                "- If tools disagree, explain discrepancy and choose conservative output."
            ),
            (
                f"{prompt.strip()}\n\n[Failure Recovery]\n"
                "- If a tool call fails, retry with fallback query plan.\n"
                "- Summarize fallback and confidence in final answer."
            ),
        ]
        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = " ".join(candidate.split())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
            if len(deduped) >= self._max_candidates:
                break
        return deduped

    def score_candidates(
        self,
        candidates: list[str],
        failures: list[CaseExecution],
    ) -> list[PromptVariant]:
        output: list[PromptVariant] = []
        failure_keywords = self._extract_failure_keywords(failures)
        for idx, candidate in enumerate(candidates):
            score = 0.5
            lowered = candidate.lower()
            if "evidence" in lowered:
                score += 0.15
            if "unknown" in lowered:
                score += 0.1
            if "fallback" in lowered:
                score += 0.05

            # Reward explicit coverage of failure tokens.
            covered = sum(1 for token in failure_keywords if token in lowered)
            if failure_keywords:
                score += 0.2 * (covered / len(failure_keywords))

            # Mild brevity penalty to avoid prompt bloat.
            score -= min(0.12, len(candidate) / 6000)

            output.append(
                PromptVariant(
                    variant_id=f"pv-{uuid4().hex[:12]}",
                    prompt=candidate,
                    source=f"candidate_{idx}",
                    score=max(0.0, min(1.0, score)),
                    metadata={
                        "failure_keywords": list(failure_keywords),
                        "length": len(candidate),
                    },
                )
            )
        return output

    def _extract_failure_keywords(self, failures: list[CaseExecution]) -> set[str]:
        tokens: set[str] = set()
        for failure in failures[:5]:
            for token in failure.rationale.lower().split():
                token = token.strip(".,:;()[]{}\"'")
                if len(token) >= 5:
                    tokens.add(token)
        return tokens
