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
    train_cases: list[SyntheticCase] = field(default_factory=list)
    val_cases: list[SyntheticCase] = field(default_factory=list)
    test_cases: list[SyntheticCase] = field(default_factory=list)
    schema_snapshot: dict[str, Any] = field(default_factory=dict)
    synthesis_report: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class JudgeVote:
    judge_name: str
    score: float
    rationale: str


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
    confidence: float = 0.0
    judge_votes: list[JudgeVote] = field(default_factory=list)


@dataclass
class EvaluationSummary:
    blueprint_id: str
    mean_score: float
    mean_latency_ms: float
    mean_token_cost: float
    total_cases: int
    reflection: str
    judge_agreement: float = 0.0
    score_std: float = 0.0
    split: str = "train"
    case_results: list[CaseExecution] = field(default_factory=list)


@dataclass
class PromptVariant:
    variant_id: str
    prompt: str
    source: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchRoundTrace:
    round_num: int
    selected_node_id: str
    selected_blueprint_id: str
    mutation: str
    train_objective: float
    val_objective: float
    best_train_objective: float
    best_val_objective: float
    improvement: float
    regret: float


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
    validation_budget: int = 6
    test_budget: int = 6
    exploration_weight: float = 1.2
    novelty_weight: float = 0.15
    latency_penalty: float = 0.05
    cost_penalty: float = 0.05
    complexity_penalty: float = 0.02
    confidence_weight: float = 0.15
    min_improvement: float = 0.005
    patience: int = 3
    max_prompt_candidates: int = 4
    train_ratio: float = 0.6
    val_ratio: float = 0.2
    test_ratio: float = 0.2


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
    run_id: str
    dataset: SyntheticDataset
    best_blueprint: WorkflowBlueprint
    best_evaluation: EvaluationSummary
    validation_evaluation: EvaluationSummary | None
    test_evaluation: EvaluationSummary | None
    round_traces: list[SearchRoundTrace]
    history: list[EvaluationSummary]
    registry_record: AgentVersionRecord | None = None
