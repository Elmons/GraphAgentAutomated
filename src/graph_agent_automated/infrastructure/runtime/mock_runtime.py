from __future__ import annotations

from pathlib import Path
from time import perf_counter

from graph_agent_automated.domain.models import (
    CaseExecution,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.runtime.yaml_renderer import Chat2GraphYamlRenderer


class MockRuntimeAdapter:
    """Deterministic runtime used for tests and dry-run workflows."""

    def __init__(self) -> None:
        self._renderer = Chat2GraphYamlRenderer()

    def fetch_schema_snapshot(self) -> dict[str, object]:
        return {
            "labels": ["Person", "Account", "Loan", "Transaction"],
            "relations": ["OWNS", "TRANSFERS", "BORROWS", "DEPOSITS_TO"],
        }

    def fetch_tool_catalog(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="SchemaGetter",
                module_path="app.plugin.neo4j.resource.data_importation",
                description="Read graph schema",
                tags=["schema", "query"],
            ),
            ToolSpec(
                name="CypherExecutor",
                module_path="app.plugin.neo4j.resource.graph_query",
                description="Execute Cypher query",
                tags=["query", "cypher"],
            ),
            ToolSpec(
                name="PageRankExecutor",
                module_path="app.plugin.neo4j.resource.graph_analysis",
                description="Run PageRank analytics",
                tags=["analysis", "algorithm", "rank"],
            ),
            ToolSpec(
                name="KnowledgeBaseRetriever",
                module_path="app.plugin.neo4j.resource.question_answering",
                description="Retrieve external knowledge",
                tags=["qa", "retrieval"],
            ),
        ]

    def execute_case(self, blueprint: WorkflowBlueprint, case: SyntheticCase) -> CaseExecution:
        started = perf_counter()
        # Stable deterministic heuristic for repeatable tests.
        branch_bonus = 0.1 if blueprint.topology.value != "linear" else 0.0
        tool_bonus = min(0.3, len(blueprint.tools) * 0.05)
        hard_negative_penalty = (
            0.08 if case.metadata.get("lineage", {}).get("is_hard_negative", False) else 0.0
        )
        output = f"Mock answer for {case.question}"
        latency_ms = (perf_counter() - started) * 1000 + 10 + len(blueprint.actions)
        token_cost = 0.001 * (len(case.question.split()) + len(blueprint.actions))
        return CaseExecution(
            case_id=case.case_id,
            question=case.question,
            expected=case.verifier,
            output=output,
            score=max(0.0, min(0.95, 0.45 + branch_bonus + tool_bonus - hard_negative_penalty)),
            rationale="mock runtime heuristic",
            latency_ms=latency_ms,
            token_cost=token_cost,
            confidence=min(0.95, 0.55 + branch_bonus + tool_bonus - hard_negative_penalty / 2.0),
        )

    def materialize(self, blueprint: WorkflowBlueprint, output_dir: Path) -> Path:
        return self._renderer.render(blueprint, output_dir / "workflow.yml")
