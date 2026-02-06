from __future__ import annotations

from collections.abc import Sequence

from graph_agent_automated.domain.models import ToolSpec
from graph_agent_automated.domain.protocols import ToolSelector


class IntentAwareToolSelector(ToolSelector):
    """Strategy selector that ranks tools by intent-keyword coverage."""

    keyword_map = {
        "query": ("query", "cypher", "schema", "search"),
        "analytics": ("algorithm", "analysis", "rank", "community"),
        "modeling": ("schema", "model", "label", "vertex", "edge"),
        "import": ("import", "ingest", "extract", "etl"),
        "qa": ("retrieval", "knowledge", "browser", "search"),
    }

    def rank(
        self,
        task_desc: str,
        intents: Sequence[str],
        catalog: Sequence[ToolSpec],
        top_k: int,
    ) -> list[ToolSpec]:
        normalized_task = task_desc.lower()
        scored: list[tuple[int, str, ToolSpec]] = []

        for tool in catalog:
            text = f"{tool.name} {tool.description} {' '.join(tool.tags)}".lower()
            score = 0
            for intent in intents:
                for keyword in self.keyword_map.get(intent, ()):  # pragma: no branch
                    if keyword in text:
                        score += 2
                    if keyword in normalized_task:
                        score += 1
            scored.append((score, tool.name, tool))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in scored[: max(1, top_k)]]
