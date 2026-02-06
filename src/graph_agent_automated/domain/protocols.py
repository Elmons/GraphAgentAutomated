from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from graph_agent_automated.domain.models import (
    CaseExecution,
    EvaluationSummary,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)


class RuntimeAdapter(Protocol):
    def fetch_schema_snapshot(self) -> dict[str, object]:
        """Return graph schema summary for dynamic synthesis."""

    def fetch_tool_catalog(self) -> list[ToolSpec]:
        """Return candidate tools that can be selected by optimizer."""

    def execute_case(self, blueprint: WorkflowBlueprint, case: SyntheticCase) -> CaseExecution:
        """Execute one case in runtime."""

    def materialize(self, blueprint: WorkflowBlueprint, output_dir: Path) -> Path:
        """Persist runtime artifact for deployment."""


class DatasetSynthesizer(Protocol):
    def synthesize(self, task_desc: str, dataset_name: str, size: int):
        """Generate dynamic synthetic dataset."""


class PromptOptimizer(Protocol):
    def optimize(self, prompt: str, failures: Sequence[CaseExecution], task_desc: str) -> str:
        """Revise prompt based on failures."""


class ToolSelector(Protocol):
    def rank(
        self,
        task_desc: str,
        intents: Sequence[str],
        catalog: Sequence[ToolSpec],
        top_k: int,
        historical_gain: dict[str, float] | None = None,
    ) -> list[ToolSpec]:
        """Return ranked tools."""


class LLMJudge(Protocol):
    def judge(self, question: str, expected: str, prediction: str, rubric: str) -> tuple[float, str]:
        """Return score [0,1] and textual rationale."""


class WorkflowEvaluator(Protocol):
    def evaluate(
        self,
        blueprint: WorkflowBlueprint,
        cases: Sequence[SyntheticCase],
        split: str = "train",
    ) -> EvaluationSummary:
        """Evaluate one candidate workflow on dataset slice."""
