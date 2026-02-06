from __future__ import annotations

from graph_agent_automated.infrastructure.runtime.mock_runtime import MockRuntimeAdapter
from graph_agent_automated.infrastructure.synthesis.dynamic_synthesizer import (
    DynamicDatasetSynthesizer,
)


def test_dynamic_synthesizer_generates_bounded_dataset() -> None:
    runtime = MockRuntimeAdapter()
    synthesizer = DynamicDatasetSynthesizer(runtime=runtime, answer_resolver=lambda _: "OK")

    dataset = synthesizer.synthesize(
        task_desc="请执行图查询和图算法分析任务",
        dataset_name="demo",
        size=10,
    )

    assert dataset.name == "demo"
    assert len(dataset.cases) == 10
    assert {case.verifier for case in dataset.cases} == {"OK"}
    assert all(case.question for case in dataset.cases)
    assert len(dataset.train_cases) + len(dataset.val_cases) + len(dataset.test_cases) == 10
    assert dataset.synthesis_report["final_size"] == 10
    assert "split_sizes" in dataset.synthesis_report


def test_dynamic_synthesizer_fallback_size() -> None:
    runtime = MockRuntimeAdapter()
    synthesizer = DynamicDatasetSynthesizer(runtime=runtime)

    dataset = synthesizer.synthesize("query", "demo", 1)
    assert len(dataset.cases) >= 6
    assert len(dataset.train_cases) >= 1
    assert len(dataset.val_cases) >= 1
    assert len(dataset.test_cases) >= 1
