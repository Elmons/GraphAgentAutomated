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
