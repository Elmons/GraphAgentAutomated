from __future__ import annotations

import json
from pathlib import Path

import yaml

from graph_agent_automated.domain.enums import TopologyPattern
from graph_agent_automated.infrastructure.runtime.workflow_loader import WorkflowBlueprintLoader


def test_workflow_loader_supports_chat2graph_yaml(tmp_path: Path) -> None:
    payload = {
        "app": {"name": "manual-agent", "desc": "manual task"},
        "tools": [
            {
                "name": "CypherExecutor",
                "type": "LOCAL_TOOL",
                "module_path": "app.plugin.neo4j.resource.graph_query",
            }
        ],
        "actions": [
            {
                "name": "use_cypherexecutor",
                "desc": "run query",
                "tools": [{"name": "CypherExecutor"}],
            }
        ],
        "experts": [
            {
                "profile": {"name": "GraphExpert", "desc": "manual expert"},
                "workflow": [
                    [
                        {
                            "instruction": "answer with evidence",
                            "output_schema": "final_answer: str",
                            "actions": [{"name": "use_cypherexecutor"}],
                        }
                    ]
                ],
            }
        ],
        "leader": {"actions": [{"name": "use_cypherexecutor"}]},
        "env": {"topology": "planner_worker_reviewer", "meta": {"source": "manual"}},
    }
    file_path = tmp_path / "manual.yml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    loader = WorkflowBlueprintLoader()
    blueprint = loader.load(file_path, app_name="fallback", task_desc="fallback task")

    assert blueprint.app_name == "manual-agent"
    assert blueprint.task_desc == "manual task"
    assert blueprint.topology == TopologyPattern.PLANNER_WORKER_REVIEWER
    assert blueprint.tools[0].name == "CypherExecutor"
    assert blueprint.actions[0].name == "use_cypherexecutor"
    assert blueprint.experts[0].name == "GraphExpert"
    assert blueprint.leader_actions == ["use_cypherexecutor"]
    assert blueprint.metadata["source"] == "manual"


def test_workflow_loader_supports_internal_json(tmp_path: Path) -> None:
    payload = {
        "blueprint_id": "bp-manual",
        "app_name": "manual-json",
        "task_desc": "manual json task",
        "topology": "linear",
        "tools": [{"name": "SchemaGetter"}],
        "actions": [{"name": "use_schemagetter", "description": "read schema", "tools": ["SchemaGetter"]}],
        "experts": [
            {
                "name": "JsonExpert",
                "description": "desc",
                "operators": [
                    {
                        "name": "worker",
                        "instruction": "do task",
                        "output_schema": "answer: str",
                        "actions": ["use_schemagetter"],
                    }
                ],
            }
        ],
        "leader_actions": ["use_schemagetter"],
        "metadata": {"source": "manual-json"},
    }
    file_path = tmp_path / "manual.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    loader = WorkflowBlueprintLoader()
    blueprint = loader.load(file_path, app_name="fallback", task_desc="fallback task")

    assert blueprint.blueprint_id == "bp-manual"
    assert blueprint.topology == TopologyPattern.LINEAR
    assert blueprint.experts[0].operators[0].name == "worker"
    assert blueprint.metadata["source"] == "manual-json"
