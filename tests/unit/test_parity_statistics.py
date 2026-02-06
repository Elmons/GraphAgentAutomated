from __future__ import annotations

from statistics import mean

from graph_agent_automated.infrastructure.evaluation.parity_statistics import (
    cliffs_delta,
    paired_bootstrap_mean_ci,
    wilcoxon_signed_rank,
)


def test_paired_bootstrap_mean_ci_contains_sample_mean() -> None:
    values = [-0.12, -0.08, -0.05, 0.01, 0.03]
    lo, hi = paired_bootstrap_mean_ci(values, n_resample=1500, random_seed=11)
    assert lo <= hi
    assert lo <= mean(values) <= hi


def test_wilcoxon_signed_rank_detects_directional_gain() -> None:
    auto_scores = [0.81, 0.83, 0.8, 0.84, 0.82, 0.85]
    manual_scores = [0.72, 0.73, 0.74, 0.75, 0.76, 0.77]

    result = wilcoxon_signed_rank(auto_scores, manual_scores)

    assert result["n_pairs"] == 6.0
    assert result["n_non_zero"] == 6.0
    assert result["w_plus"] > result["w_minus"]
    assert result["p_value"] < 0.1


def test_cliffs_delta_reports_large_effect() -> None:
    auto_scores = [0.9, 0.88, 0.91, 0.87]
    manual_scores = [0.62, 0.64, 0.66, 0.68]

    delta, magnitude = cliffs_delta(auto_scores, manual_scores)

    assert delta > 0.5
    assert magnitude == "large"
