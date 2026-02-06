from __future__ import annotations

from graph_agent_automated.application.profiles import resolve_optimization_knobs
from graph_agent_automated.domain.enums import ExperimentProfile


def test_baseline_static_prompt_only_knobs() -> None:
    knobs = resolve_optimization_knobs(ExperimentProfile.BASELINE_STATIC_PROMPT_ONLY)

    assert knobs.profile == ExperimentProfile.BASELINE_STATIC_PROMPT_ONLY
    assert knobs.dynamic_dataset is False
    assert knobs.enable_tool_mutation is False
    assert knobs.enable_topology_mutation is False
    assert knobs.use_ensemble_judge is False
    assert knobs.enable_hard_negatives is False


def test_ablation_no_holdout_knobs() -> None:
    knobs = resolve_optimization_knobs(ExperimentProfile.ABLATION_NO_HOLDOUT)

    assert knobs.profile == ExperimentProfile.ABLATION_NO_HOLDOUT
    assert knobs.use_holdout is False
    assert knobs.generalization_penalty == 0.0


def test_idea_failure_aware_mutation_knobs() -> None:
    knobs = resolve_optimization_knobs(ExperimentProfile.IDEA_FAILURE_AWARE_MUTATION)

    assert knobs.profile == ExperimentProfile.IDEA_FAILURE_AWARE_MUTATION
    assert knobs.enable_failure_aware_mutation is True
    assert knobs.enable_prompt_mutation is True
    assert knobs.enable_tool_mutation is True
