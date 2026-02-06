from __future__ import annotations

from typing import Sequence

from graph_agent_automated.domain.models import CaseExecution
from graph_agent_automated.domain.protocols import PromptOptimizer


class ReflectionPromptOptimizer(PromptOptimizer):
    """Prompt optimization strategy guided by failure reflections."""

    def optimize(self, prompt: str, failures: Sequence[CaseExecution], task_desc: str) -> str:
        if not failures:
            return prompt

        condensed = "; ".join(
            f"{case.case_id}:{case.rationale}" for case in list(failures)[:3]
        )
        suffix = (
            "\n[Refined Constraints]\n"
            "- Ground answers in tool output and graph schema facts.\n"
            "- If evidence is missing, request clarification before final answer.\n"
            "- Report assumptions explicitly in one short line.\n"
            f"- Known failure modes: {condensed}\n"
        )

        if "[Refined Constraints]" in prompt:
            return prompt
        return prompt.strip() + suffix
