from __future__ import annotations

from graph_agent_automated.domain.enums import Difficulty, TaskIntent, TopologyPattern
from graph_agent_automated.domain.models import (
    ActionSpec,
    ExpertBlueprint,
    OperatorBlueprint,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.runtime.mock_runtime import MockRuntimeAdapter
from graph_agent_automated.infrastructure.synthesis.dynamic_synthesizer import (
    DynamicDatasetSynthesizer,
)


def _blueprint() -> WorkflowBlueprint:
    return WorkflowBlueprint(
        blueprint_id="bp-mock",
        app_name="demo",
        task_desc="task",
        topology=TopologyPattern.LINEAR,
        tools=[ToolSpec(name="CypherExecutor", description="query", tags=["query"])],
        actions=[
            ActionSpec(name="use_cypherexecutor", description="run query", tools=["CypherExecutor"])
        ],
        experts=[
            ExpertBlueprint(
                name="GraphExpert",
                description="desc",
                operators=[
                    OperatorBlueprint(
                        name="worker",
                        instruction="answer with evidence",
                        output_schema="answer",
                        actions=["use_cypherexecutor"],
                    )
                ],
            )
        ],
        leader_actions=["use_cypherexecutor"],
    )


def test_property_dataset_size_is_bounded_and_splits_sum() -> None:
    runtime = MockRuntimeAdapter()
    synthesizer = DynamicDatasetSynthesizer(runtime=runtime)

    for requested in [0, 1, 6, 12, 30, 100]:
        dataset = synthesizer.synthesize("query", "demo", requested)
        assert 6 <= len(dataset.cases) <= 30
        assert (
            len(dataset.train_cases) + len(dataset.val_cases) + len(dataset.test_cases)
            == len(dataset.cases)
        )


def test_metamorphic_task_desc_noise_keeps_intent_profile_stable() -> None:
    runtime = MockRuntimeAdapter()
    synthesizer = DynamicDatasetSynthesizer(runtime=runtime, random_seed=42)

    base = synthesizer.synthesize("graph query and analytics", "base", 10)
    noisy = synthesizer.synthesize("  GRAPH   query  and  ANALYTICS  ", "noisy", 10)

    assert base.synthesis_report["intents"] == noisy.synthesis_report["intents"]


def test_adversarial_hard_negative_case_reduces_runtime_score() -> None:
    runtime = MockRuntimeAdapter()
    blueprint = _blueprint()

    easy_case = SyntheticCase(
        case_id="c1",
        question="Find Person by OWNS",
        verifier="UNKNOWN",
        intent=TaskIntent.QUERY,
        difficulty=Difficulty.L1,
        metadata={"lineage": {"is_hard_negative": False}},
    )
    hard_case = SyntheticCase(
        case_id="c2",
        question="Find Person by OWNS",
        verifier="UNKNOWN",
        intent=TaskIntent.QUERY,
        difficulty=Difficulty.L1,
        metadata={"lineage": {"is_hard_negative": True}},
    )

    easy_exec = runtime.execute_case(blueprint, easy_case)
    hard_exec = runtime.execute_case(blueprint, hard_case)

    assert hard_exec.score < easy_exec.score
    assert hard_exec.confidence < easy_exec.confidence
