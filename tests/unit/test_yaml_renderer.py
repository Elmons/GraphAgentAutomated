from __future__ import annotations

from pathlib import Path

import yaml

from graph_agent_automated.domain.enums import TopologyPattern
from graph_agent_automated.domain.models import (
    ActionSpec,
    ExpertBlueprint,
    OperatorBlueprint,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.runtime.yaml_renderer import Chat2GraphYamlRenderer


def test_yaml_renderer_outputs_chat2graph_style_yaml(tmp_path: Path) -> None:
    renderer = Chat2GraphYamlRenderer()
    blueprint = WorkflowBlueprint(
        blueprint_id="bp-x",
        app_name="demo",
        task_desc="task",
        topology=TopologyPattern.LINEAR,
        tools=[ToolSpec(name="CypherExecutor", module_path="app.plugin.neo4j.resource.graph_query")],
        actions=[ActionSpec(name="use_cypherexecutor", description="run cypher", tools=["CypherExecutor"])],
        experts=[
            ExpertBlueprint(
                name="Expert",
                description="desc",
                operators=[
                    OperatorBlueprint(
                        name="worker",
                        instruction="do work",
                        output_schema="answer",
                        actions=["use_cypherexecutor"],
                    )
                ],
            )
        ],
        leader_actions=["use_cypherexecutor"],
    )

    out = renderer.render(blueprint, tmp_path / "workflow.yml")
    assert out.exists()

    with open(out, encoding="utf-8") as f:
        payload = yaml.safe_load(f)

    assert payload["app"]["name"] == "demo"
    assert payload["experts"][0]["profile"]["name"] == "Expert"
    assert payload["leader"]["actions"][0]["name"] == "use_cypherexecutor"
