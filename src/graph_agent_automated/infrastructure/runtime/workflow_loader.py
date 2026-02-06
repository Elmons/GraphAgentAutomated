from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from graph_agent_automated.domain.enums import TopologyPattern
from graph_agent_automated.domain.models import (
    ActionSpec,
    ExpertBlueprint,
    OperatorBlueprint,
    ToolSpec,
    WorkflowBlueprint,
)


class WorkflowBlueprintLoader:
    """Load workflow blueprint from JSON/YAML into internal dataclass."""

    def load(
        self,
        path: str | Path,
        app_name: str,
        task_desc: str,
    ) -> WorkflowBlueprint:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists() or not file_path.is_file():
            raise ValueError(f"manual blueprint file not found: {file_path}")
        if file_path.suffix.lower() not in {".yml", ".yaml", ".json"}:
            raise ValueError("manual blueprint must be .yml/.yaml/.json")

        payload = self._read_payload(file_path)
        if self._looks_like_internal(payload):
            return self._from_internal(payload, app_name=app_name, task_desc=task_desc)
        return self._from_chat2graph_payload(payload, app_name=app_name, task_desc=task_desc)

    def _read_payload(self, file_path: Path) -> dict[str, Any]:
        with open(file_path, encoding="utf-8") as f:
            if file_path.suffix.lower() == ".json":
                payload = json.load(f)
            else:
                payload = yaml.safe_load(f)
        if not isinstance(payload, dict):
            raise ValueError("manual blueprint payload must be a JSON/YAML object")
        return payload

    def _looks_like_internal(self, payload: dict[str, Any]) -> bool:
        return "blueprint_id" in payload and "experts" in payload and "actions" in payload

    def _from_internal(
        self,
        payload: dict[str, Any],
        app_name: str,
        task_desc: str,
    ) -> WorkflowBlueprint:
        topology = self._parse_topology(payload.get("topology"))
        tools = [self._parse_tool(item) for item in self._as_list(payload.get("tools"))]
        actions = [self._parse_action(item) for item in self._as_list(payload.get("actions"))]
        experts = [
            self._parse_expert(item, fallback_name=f"expert_{idx + 1}")
            for idx, item in enumerate(self._as_list(payload.get("experts")))
        ]
        leader_actions = [str(item) for item in self._as_list(payload.get("leader_actions")) if str(item)]
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        return WorkflowBlueprint(
            blueprint_id=str(payload.get("blueprint_id") or f"manual-{uuid4().hex[:12]}"),
            app_name=str(payload.get("app_name") or app_name),
            task_desc=str(payload.get("task_desc") or task_desc),
            topology=topology,
            tools=tools,
            actions=actions,
            experts=experts,
            leader_actions=leader_actions or [action.name for action in actions[:2]],
            metadata=metadata,
        )

    def _from_chat2graph_payload(
        self,
        payload: dict[str, Any],
        app_name: str,
        task_desc: str,
    ) -> WorkflowBlueprint:
        app = payload.get("app")
        env = payload.get("env")
        app_row = app if isinstance(app, dict) else {}
        env_row = env if isinstance(env, dict) else {}
        metadata = env_row.get("meta")
        if not isinstance(metadata, dict):
            metadata = {}

        tools = [self._parse_tool(item) for item in self._as_list(payload.get("tools"))]
        actions = [self._parse_action(item) for item in self._as_list(payload.get("actions"))]

        experts: list[ExpertBlueprint] = []
        for e_idx, raw_expert in enumerate(self._as_list(payload.get("experts"))):
            if not isinstance(raw_expert, dict):
                continue
            profile = raw_expert.get("profile")
            profile_row = profile if isinstance(profile, dict) else {}
            workflow_raw = raw_expert.get("workflow")
            workflow = self._as_list(workflow_raw)
            operators_payload = workflow[0] if workflow and isinstance(workflow[0], list) else workflow

            operators: list[OperatorBlueprint] = []
            for o_idx, raw_op in enumerate(self._as_list(operators_payload)):
                if not isinstance(raw_op, dict):
                    continue
                action_refs = self._as_list(raw_op.get("actions"))
                action_names: list[str] = []
                for ref in action_refs:
                    if isinstance(ref, dict):
                        name = ref.get("name")
                        if name:
                            action_names.append(str(name))
                    elif ref:
                        action_names.append(str(ref))

                operators.append(
                    OperatorBlueprint(
                        name=f"op_{o_idx + 1}",
                        instruction=str(raw_op.get("instruction", "")),
                        output_schema=str(raw_op.get("output_schema", "")),
                        actions=action_names,
                    )
                )

            experts.append(
                ExpertBlueprint(
                    name=str(profile_row.get("name") or f"expert_{e_idx + 1}"),
                    description=str(profile_row.get("desc", "")),
                    operators=operators,
                )
            )

        leader = payload.get("leader")
        leader_row = leader if isinstance(leader, dict) else {}
        leader_actions: list[str] = []
        for ref in self._as_list(leader_row.get("actions")):
            if isinstance(ref, dict):
                name = ref.get("name")
                if name:
                    leader_actions.append(str(name))
            elif ref:
                leader_actions.append(str(ref))
        if not leader_actions:
            leader_actions = [action.name for action in actions[:2]]

        topology = self._parse_topology(env_row.get("topology"))
        return WorkflowBlueprint(
            blueprint_id=str(metadata.get("blueprint_id") or f"manual-{uuid4().hex[:12]}"),
            app_name=str(app_row.get("name") or app_name),
            task_desc=str(app_row.get("desc") or task_desc),
            topology=topology,
            tools=tools,
            actions=actions,
            experts=experts,
            leader_actions=leader_actions,
            metadata=metadata,
        )

    def _parse_topology(self, value: Any) -> TopologyPattern:
        text = str(value or TopologyPattern.PLANNER_WORKER_REVIEWER.value)
        try:
            return TopologyPattern(text)
        except ValueError:
            return TopologyPattern.PLANNER_WORKER_REVIEWER

    def _parse_tool(self, payload: Any) -> ToolSpec:
        if not isinstance(payload, dict):
            return ToolSpec(name=str(payload))
        tags = payload.get("tags")
        parsed_tags = [str(item) for item in self._as_list(tags)]
        return ToolSpec(
            name=str(payload.get("name", "")),
            module_path=str(payload.get("module_path", "")),
            description=str(payload.get("description") or payload.get("desc") or ""),
            tags=parsed_tags,
            tool_type=str(payload.get("tool_type") or payload.get("type") or "LOCAL_TOOL"),
        )

    def _parse_action(self, payload: Any) -> ActionSpec:
        if not isinstance(payload, dict):
            name = str(payload)
            return ActionSpec(name=name, description=name, tools=[])

        tools_raw = payload.get("tools")
        tools: list[str] = []
        for item in self._as_list(tools_raw):
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    tools.append(str(name))
            elif item:
                tools.append(str(item))

        return ActionSpec(
            name=str(payload.get("name", "")),
            description=str(payload.get("description") or payload.get("desc") or ""),
            tools=tools,
        )

    def _parse_expert(self, payload: Any, fallback_name: str) -> ExpertBlueprint:
        if not isinstance(payload, dict):
            return ExpertBlueprint(name=fallback_name, description="", operators=[])
        operators = [
            self._parse_operator(item, idx)
            for idx, item in enumerate(self._as_list(payload.get("operators")))
        ]
        return ExpertBlueprint(
            name=str(payload.get("name") or fallback_name),
            description=str(payload.get("description", "")),
            operators=operators,
        )

    def _parse_operator(self, payload: Any, idx: int) -> OperatorBlueprint:
        if not isinstance(payload, dict):
            return OperatorBlueprint(name=f"op_{idx + 1}", instruction="", output_schema="", actions=[])
        return OperatorBlueprint(
            name=str(payload.get("name") or f"op_{idx + 1}"),
            instruction=str(payload.get("instruction", "")),
            output_schema=str(payload.get("output_schema", "")),
            actions=[str(item) for item in self._as_list(payload.get("actions")) if str(item)],
        )

    def _as_list(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return []
