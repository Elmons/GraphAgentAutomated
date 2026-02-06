from __future__ import annotations

from dataclasses import dataclass

from graph_agent_automated.domain.models import ToolSpec
from graph_agent_automated.domain.protocols import ToolSelector


@dataclass
class ToolCapabilityProfile:
    tool_name: str
    capabilities: set[str]
    average_gain: float = 0.0
    usage_count: int = 0


class ToolCapabilityMapper:
    """Map tools to normalized capabilities for policy scoring."""

    _capability_keywords: dict[str, tuple[str, ...]] = {
        "query": ("query", "cypher", "search", "retrieve"),
        "analytics": ("analysis", "algorithm", "rank", "community"),
        "modeling": ("schema", "label", "vertex", "edge", "model"),
        "import": ("import", "extract", "ingest", "etl"),
        "qa": ("knowledge", "qa", "summarize", "browser"),
    }

    def build_profiles(self, catalog: list[ToolSpec]) -> dict[str, ToolCapabilityProfile]:
        profiles: dict[str, ToolCapabilityProfile] = {}
        for tool in catalog:
            profiles[tool.name] = ToolCapabilityProfile(
                tool_name=tool.name,
                capabilities=self.infer_capabilities(tool),
            )
        return profiles

    def infer_capabilities(self, tool: ToolSpec) -> set[str]:
        text = f"{tool.name} {tool.description} {' '.join(tool.tags)}".lower()
        capabilities: set[str] = set()
        for capability, keywords in self._capability_keywords.items():
            if any(keyword in text for keyword in keywords):
                capabilities.add(capability)
        if not capabilities:
            capabilities.add("general")
        return capabilities


class IntentAwareToolSelector(ToolSelector):
    """Capability-aware selector combining lexical relevance and historical gain."""

    _intent_keywords: dict[str, tuple[str, ...]] = {
        "query": ("query", "cypher", "search", "schema"),
        "analytics": ("algorithm", "analysis", "rank", "community"),
        "modeling": ("schema", "model", "label", "vertex", "edge"),
        "import": ("import", "ingest", "extract", "etl"),
        "qa": ("retrieval", "knowledge", "browser", "search"),
    }

    def __init__(self) -> None:
        self._mapper = ToolCapabilityMapper()

    def rank(
        self,
        task_desc: str,
        intents: list[str],
        catalog: list[ToolSpec],
        top_k: int,
        historical_gain: dict[str, float] | None = None,
    ) -> list[ToolSpec]:
        historical_gain = historical_gain or {}
        profiles = self._mapper.build_profiles(catalog)

        normalized_task = task_desc.lower()
        weighted: list[tuple[float, str, ToolSpec]] = []

        for tool in catalog:
            profile = profiles[tool.name]
            text = f"{tool.name} {tool.description} {' '.join(tool.tags)}".lower()
            lexical = 0.0
            capability_alignment = 0.0
            for intent in intents:
                for keyword in self._intent_keywords.get(intent, ()):  # pragma: no branch
                    if keyword in text:
                        lexical += 1.8
                    if keyword in normalized_task:
                        lexical += 0.8
                if intent in profile.capabilities:
                    capability_alignment += 1.5

            gain_bonus = historical_gain.get(tool.name, 0.0)
            score = lexical + capability_alignment + 0.5 * gain_bonus
            weighted.append((score, tool.name, tool))

        weighted.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in weighted[: max(1, top_k)]]
