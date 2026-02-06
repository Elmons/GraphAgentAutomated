from __future__ import annotations

from graph_agent_automated.domain.enums import ExperimentProfile
from graph_agent_automated.domain.models import OptimizationKnobs


def resolve_optimization_knobs(profile: ExperimentProfile) -> OptimizationKnobs:
    if profile == ExperimentProfile.BASELINE_STATIC_PROMPT_ONLY:
        return OptimizationKnobs(
            profile=profile,
            dynamic_dataset=False,
            enable_paraphrase=False,
            enable_hard_negatives=False,
            use_ensemble_judge=False,
            enable_prompt_mutation=True,
            enable_tool_mutation=False,
            enable_topology_mutation=False,
            use_holdout=True,
            enable_tool_historical_gain=False,
            uncertainty_penalty=0.0,
            generalization_penalty=0.0,
        )

    if profile == ExperimentProfile.DYNAMIC_PROMPT_ONLY:
        return OptimizationKnobs(
            profile=profile,
            dynamic_dataset=True,
            enable_paraphrase=True,
            enable_hard_negatives=True,
            use_ensemble_judge=False,
            enable_prompt_mutation=True,
            enable_tool_mutation=False,
            enable_topology_mutation=False,
            use_holdout=True,
            enable_tool_historical_gain=False,
            uncertainty_penalty=0.0,
            generalization_penalty=0.0,
        )

    if profile == ExperimentProfile.DYNAMIC_PROMPT_TOOL:
        return OptimizationKnobs(
            profile=profile,
            dynamic_dataset=True,
            enable_paraphrase=True,
            enable_hard_negatives=True,
            use_ensemble_judge=False,
            enable_prompt_mutation=True,
            enable_tool_mutation=True,
            enable_topology_mutation=False,
            use_holdout=True,
            enable_tool_historical_gain=True,
            uncertainty_penalty=0.0,
            generalization_penalty=0.0,
        )

    if profile == ExperimentProfile.ABLATION_NO_HOLDOUT:
        return OptimizationKnobs(
            profile=profile,
            use_holdout=False,
            uncertainty_penalty=0.12,
            generalization_penalty=0.0,
        )

    if profile == ExperimentProfile.ABLATION_SINGLE_JUDGE:
        return OptimizationKnobs(
            profile=profile,
            use_ensemble_judge=False,
        )

    if profile == ExperimentProfile.ABLATION_NO_HARD_NEGATIVE:
        return OptimizationKnobs(
            profile=profile,
            enable_hard_negatives=False,
        )

    if profile == ExperimentProfile.ABLATION_NO_TOOL_GAIN:
        return OptimizationKnobs(
            profile=profile,
            enable_tool_historical_gain=False,
        )

    if profile == ExperimentProfile.ABLATION_NO_TOPOLOGY_MUTATION:
        return OptimizationKnobs(
            profile=profile,
            enable_topology_mutation=False,
        )

    return OptimizationKnobs(profile=ExperimentProfile.FULL_SYSTEM)
