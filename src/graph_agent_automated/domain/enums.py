from __future__ import annotations

from enum import Enum


class TaskIntent(str, Enum):
    QUERY = "query"
    ANALYTICS = "analytics"
    MODELING = "modeling"
    IMPORT = "import"
    QA = "qa"


class Difficulty(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class TopologyPattern(str, Enum):
    LINEAR = "linear"
    PLANNER_WORKER_REVIEWER = "planner_worker_reviewer"
    ROUTER_PARALLEL = "router_parallel"


class AgentLifecycle(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"


class ExperimentProfile(str, Enum):
    FULL_SYSTEM = "full_system"
    IDEA_FAILURE_AWARE_MUTATION = "idea_failure_aware_mutation"
    BASELINE_STATIC_PROMPT_ONLY = "baseline_static_prompt_only"
    DYNAMIC_PROMPT_ONLY = "dynamic_prompt_only"
    DYNAMIC_PROMPT_TOOL = "dynamic_prompt_tool"
    ABLATION_NO_HOLDOUT = "ablation_no_holdout"
    ABLATION_SINGLE_JUDGE = "ablation_single_judge"
    ABLATION_NO_HARD_NEGATIVE = "ablation_no_hard_negative"
    ABLATION_NO_TOOL_GAIN = "ablation_no_tool_gain"
    ABLATION_NO_TOPOLOGY_MUTATION = "ablation_no_topology_mutation"
