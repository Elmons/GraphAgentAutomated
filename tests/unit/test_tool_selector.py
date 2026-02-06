from __future__ import annotations

from graph_agent_automated.domain.models import ToolSpec
from graph_agent_automated.infrastructure.optimization.tool_selector import IntentAwareToolSelector


def test_intent_aware_tool_selector_uses_capability_and_gain() -> None:
    selector = IntentAwareToolSelector()
    catalog = [
        ToolSpec(name="CypherExecutor", description="query cypher executor", tags=["query", "cypher"]),
        ToolSpec(
            name="PageRankExecutor",
            description="graph analysis pagerank",
            tags=["analysis", "rank"],
        ),
        ToolSpec(name="GenericTool", description="helper", tags=[]),
    ]

    ranked = selector.rank(
        task_desc="need query and rank analysis",
        intents=["query", "analytics"],
        catalog=catalog,
        top_k=2,
        historical_gain={"GenericTool": 10.0},
    )

    assert len(ranked) == 2
    assert {tool.name for tool in ranked} & {"CypherExecutor", "PageRankExecutor"}
