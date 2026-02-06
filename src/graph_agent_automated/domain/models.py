from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from graph_agent_automated.domain.enums import (
    AgentLifecycle,
    Difficulty,
    TaskIntent,
    TopologyPattern,
)


@dataclass
class ToolSpec:
    name: str
    module_path: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    tool_type: str = "LOCAL_TOOL"


@dataclass
class ActionSpec:
    name: str
    description: str
    tools: list[str] = field(default_factory=list)


@dataclass
class OperatorBlueprint:
    name: str
    instruction: str
    output_schema: str
    actions: list[str] = field(default_factory=list)


@dataclass
class ExpertBlueprint:
    name: str
    description: str
    operators: list[OperatorBlueprint]


@dataclass
class WorkflowBlueprint:
    blueprint_id: str
    app_name: str
    task_desc: str
    topology: TopologyPattern
    tools: list[ToolSpec]
    actions: list[ActionSpec]
    experts: list[ExpertBlueprint]
    leader_actions: list[str]
    parent_id: str | None = None
    mutation_trace: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyntheticCase:
    case_id: str
    question: str
    verifier: str
    intent: TaskIntent
    difficulty: Difficulty
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyntheticDataset:
    name: str
    task_desc: str
    cases: list[SyntheticCase]
    schema_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CaseExecution:
    case_id: str
    question: str
    expected: str
    output: str
    score: float
    rationale: str
    latency_ms: float
    token_cost: float


@dataclass
class EvaluationSummary:
    blueprint_id: str
    mean_score: float
    mean_latency_ms: float
    mean_token_cost: float
    total_cases: int
    reflection: str
    case_results: list[CaseExecution] = field(default_factory=list)


@dataclass
class SearchNode:
    node_id: str
    blueprint: WorkflowBlueprint
    parent_id: str | None = None
    visits: int = 0
    value_sum: float = 0.0
    best_score: float = -1.0
    last_reflection: str = ""
    children_ids: list[str] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.value_sum / self.visits


@dataclass
class SearchConfig:
    rounds: int = 10
    expansions_per_round: int = 3
    evaluation_budget: int = 8
    exploration_weight: float = 1.2
    novelty_weight: float = 0.15
    latency_penalty: float = 0.05
    cost_penalty: float = 0.05
    complexity_penalty: float = 0.02
    min_improvement: float = 0.005
    patience: int = 3


@dataclass
class AgentVersionRecord:
    agent_name: str
    version: int
    lifecycle: AgentLifecycle
    blueprint_id: str
    score: float
    artifact_path: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""


@dataclass
class OptimizationReport:
    dataset: SyntheticDataset
    best_blueprint: WorkflowBlueprint
    best_evaluation: EvaluationSummary
    history: list[EvaluationSummary]
    registry_record: AgentVersionRecord | None = None
