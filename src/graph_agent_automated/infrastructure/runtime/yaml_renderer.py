from __future__ import annotations

from pathlib import Path

import yaml

from graph_agent_automated.domain.models import WorkflowBlueprint


class Chat2GraphYamlRenderer:
    """Render optimized workflow blueprints into chat2graph SDK YAML format."""

    def render(self, blueprint: WorkflowBlueprint, output_path: Path) -> Path:
        payload = self._to_payload(blueprint)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
        return output_path

    def _to_payload(self, blueprint: WorkflowBlueprint) -> dict[str, object]:
        tools = []
        for tool in blueprint.tools:
            tool_row: dict[str, object] = {
                "name": tool.name,
                "type": tool.tool_type,
            }
            if tool.module_path:
                tool_row["module_path"] = tool.module_path
            tools.append(tool_row)

        actions = []
        for action in blueprint.actions:
            actions.append(
                {
                    "name": action.name,
                    "desc": action.description,
                    "tools": [{"name": name} for name in action.tools],
                }
            )

        toolkit = [[{"name": action.name}] for action in blueprint.actions]

        experts = []
        for expert in blueprint.experts:
            operators = []
            for op in expert.operators:
                operators.append(
                    {
                        "instruction": op.instruction,
                        "output_schema": op.output_schema,
                        "actions": [{"name": action} for action in op.actions],
                    }
                )

            experts.append(
                {
                    "profile": {"name": expert.name, "desc": expert.description},
                    "workflow": [operators],
                }
            )

        return {
            "app": {"name": blueprint.app_name, "desc": blueprint.task_desc, "version": "0.1.0"},
            "plugin": {"workflow_platform": "BUILTIN"},
            "reasoner": {"type": "DUAL"},
            "tools": tools,
            "actions": actions,
            "toolkit": toolkit,
            "experts": experts,
            "leader": {"actions": [{"name": name} for name in blueprint.leader_actions]},
            "knowledgebase": {},
            "memory": {},
            "env": {
                "topology": blueprint.topology.value,
                "meta": blueprint.metadata,
            },
        }
