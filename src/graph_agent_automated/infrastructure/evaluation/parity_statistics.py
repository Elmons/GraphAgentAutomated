from __future__ import annotations

import math
import random
from statistics import mean
from typing import Sequence


def paired_bootstrap_mean_ci(
    values: Sequence[float],
    *,
    n_resample: int = 2000,
    alpha: float = 0.05,
    random_seed: int = 7,
) -> tuple[float, float]:
    """Return bootstrap CI for mean of a paired-difference sample."""
    if not values:
        return (0.0, 0.0)
    if n_resample <= 0:
        raise ValueError("n_resample must be positive")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1)")

    rng = random.Random(random_seed)
    n = len(values)
    samples: list[float] = []
    for _ in range(n_resample):
        resample = [float(rng.choice(values)) for _ in range(n)]
        samples.append(mean(resample))
    samples.sort()

    lo_idx = max(0, min(len(samples) - 1, int((alpha / 2) * (len(samples) - 1))))
    hi_idx = max(0, min(len(samples) - 1, int((1 - alpha / 2) * (len(samples) - 1))))
    return (samples[lo_idx], samples[hi_idx])


def wilcoxon_signed_rank(
    auto_scores: Sequence[float],
    manual_scores: Sequence[float],
    *,
    zero_tolerance: float = 1e-12,
) -> dict[str, float]:
    """Approximate two-sided Wilcoxon signed-rank test (normal approximation)."""
    if len(auto_scores) != len(manual_scores):
        raise ValueError("auto_scores and manual_scores must have the same length")

    diffs = [float(a) - float(b) for a, b in zip(auto_scores, manual_scores, strict=True)]
    non_zero_diffs = [diff for diff in diffs if abs(diff) > zero_tolerance]
    n = len(non_zero_diffs)
    if n == 0:
        return {
            "n_pairs": float(len(diffs)),
            "n_non_zero": 0.0,
            "w_plus": 0.0,
            "w_minus": 0.0,
            "z_score": 0.0,
            "p_value": 1.0,
        }

    abs_values = [abs(diff) for diff in non_zero_diffs]
    ranks = _average_ranks(abs_values)

    w_plus = 0.0
    w_minus = 0.0
    for diff, rank in zip(non_zero_diffs, ranks, strict=True):
        if diff > 0:
            w_plus += rank
        else:
            w_minus += rank

    mean_w = n * (n + 1) / 4.0
    tie_sizes = _tie_group_sizes(abs_values)
    variance_numerator = n * (n + 1) * (2 * n + 1)
    tie_correction = sum(size * (size + 1) * (2 * size + 1) for size in tie_sizes)
    variance = (variance_numerator - tie_correction) / 24.0
    if variance <= 0:
        z_score = 0.0
        p_value = 1.0
    else:
        continuity = 0.5 if w_plus > mean_w else (-0.5 if w_plus < mean_w else 0.0)
        z_score = (w_plus - mean_w - continuity) / math.sqrt(variance)
        p_value = min(1.0, math.erfc(abs(z_score) / math.sqrt(2.0)))

    return {
        "n_pairs": float(len(diffs)),
        "n_non_zero": float(n),
        "w_plus": w_plus,
        "w_minus": w_minus,
        "z_score": z_score,
        "p_value": p_value,
    }


def cliffs_delta(
    auto_scores: Sequence[float],
    manual_scores: Sequence[float],
) -> tuple[float, str]:
    """Return Cliff's delta effect size and qualitative magnitude."""
    if not auto_scores or not manual_scores:
        return (0.0, "negligible")

    greater = 0
    lower = 0
    total = len(auto_scores) * len(manual_scores)
    for auto_score in auto_scores:
        for manual_score in manual_scores:
            if auto_score > manual_score:
                greater += 1
            elif auto_score < manual_score:
                lower += 1

    delta = (greater - lower) / total
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        magnitude = "negligible"
    elif abs_delta < 0.33:
        magnitude = "small"
    elif abs_delta < 0.474:
        magnitude = "medium"
    else:
        magnitude = "large"
    return (delta, magnitude)


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda row: row[1])
    ranks = [0.0] * len(values)
    idx = 0
    while idx < len(indexed):
        end = idx + 1
        while end < len(indexed) and indexed[end][1] == indexed[idx][1]:
            end += 1
        # Wilcoxon uses 1-based ranks.
        avg_rank = (idx + 1 + end) / 2.0
        for cursor in range(idx, end):
            original_index, _ = indexed[cursor]
            ranks[original_index] = avg_rank
        idx = end
    return ranks


def _tie_group_sizes(values: Sequence[float]) -> list[int]:
    if not values:
        return []
    sorted_values = sorted(values)
    output: list[int] = []
    cursor = 0
    while cursor < len(sorted_values):
        end = cursor + 1
        while end < len(sorted_values) and sorted_values[end] == sorted_values[cursor]:
            end += 1
        size = end - cursor
        if size > 1:
            output.append(size)
        cursor = end
    return output
