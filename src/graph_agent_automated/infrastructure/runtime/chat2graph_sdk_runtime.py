from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from time import perf_counter

import yaml

from graph_agent_automated.core.config import Settings
from graph_agent_automated.domain.models import (
    CaseExecution,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.runtime.yaml_renderer import Chat2GraphYamlRenderer


class Chat2GraphSDKRuntimeAdapter:
    """External adapter that treats chat2graph as an out-of-process SDK/runtime."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._root = Path(settings.chat2graph_root).resolve()
        self._renderer = Chat2GraphYamlRenderer()

        if not self._root.exists():
            raise ValueError(
                "chat2graph_root does not exist. Set CHAT2GRAPH_ROOT to a valid external repository path."
            )

        self._ensure_importable(self._root)
        from app.core.sdk.agentic_service import AgenticService  # type: ignore

        self._agentic_service_cls = AgenticService

    def fetch_schema_snapshot(self) -> dict[str, object]:
        schema_file = self._settings.chat2graph_schema_file
        if schema_file:
            path = Path(schema_file)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    return payload

        return {
            "labels": ["Node"],
            "relations": ["RELATED_TO"],
            "source": "fallback",
        }

    def fetch_tool_catalog(self) -> list[ToolSpec]:
        config_path = self._root / "app/core/sdk/chat2graph.yml"
        if not config_path.exists():
            return []

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        tools = config.get("tools", [])
        output: list[ToolSpec] = []
        for row in tools:
            if not isinstance(row, dict):
                continue
            output.append(
                ToolSpec(
                    name=str(row.get("name", "")),
                    module_path=str(row.get("module_path", "")),
                    description=str(row.get("desc", "")),
                    tags=[str(row.get("type", ""))],
                    tool_type=str(row.get("type", "LOCAL_TOOL")),
                )
            )
        return output

    def execute_case(self, blueprint: WorkflowBlueprint, case: SyntheticCase) -> CaseExecution:
        runtime_dir = Path(self._settings.artifacts_dir) / "runtime_tmp" / blueprint.blueprint_id
        runtime_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = self.materialize(blueprint, runtime_dir)

        started = perf_counter()
        output_text = ""
        error = ""

        try:
            service = self._agentic_service_cls.load(yaml_path=str(workflow_path))
            result = service.execute(case.question)
            output_text = str(result.get_payload())
        except Exception as exc:  # pragma: no cover - depends on external runtime
            error = str(exc)

        latency_ms = (perf_counter() - started) * 1000
        if error:
            output_text = f"RUNTIME_ERROR: {error}"

        return CaseExecution(
            case_id=case.case_id,
            question=case.question,
            expected=case.verifier,
            output=output_text,
            score=0.0,
            rationale="runtime output before LLM judge",
            latency_ms=latency_ms,
            token_cost=0.0,
        )

    def materialize(self, blueprint: WorkflowBlueprint, output_dir: Path) -> Path:
        return self._renderer.render(blueprint, output_dir / "workflow.yml")

    def _ensure_importable(self, root: Path) -> None:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        marker = root / "app/core/sdk/agentic_service.py"
        if not marker.exists():
            raise ValueError(
                "chat2graph sdk entry not found at app/core/sdk/agentic_service.py under CHAT2GRAPH_ROOT"
            )

        spec = importlib.util.spec_from_file_location("chat2graph_marker", marker)
        if spec is None:
            raise ValueError("unable to inspect chat2graph sdk marker module")
