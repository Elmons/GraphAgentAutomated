from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


@dataclass(frozen=True)
class ResearchGateCriteria:
    min_runs: int
    min_parity_rate: float
    min_mean_score_delta: float
    min_ci95_lower_bound: float
    max_delta_std: float
    min_p10_score_delta: float
    max_mean_auto_latency_ms: float
    max_mean_auto_token_cost: float
    max_failure_severe_ratio: float
    require_wilcoxon_significance: bool
    wilcoxon_alpha: float


@dataclass(frozen=True)
class ResearchGateSpec:
    gate_id: str
    version: str
    criteria: ResearchGateCriteria


def load_research_gate(path: str | Path) -> ResearchGateSpec:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"research gate file not found: {file_path}")
    if file_path.suffix.lower() != ".json":
        raise ValueError("research gate file must be .json")

    with open(file_path, encoding="utf-8") as f:
        payload: Any = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("research gate payload must be a JSON object")

    gate_id = str(payload.get("gate_id") or "").strip()
    version = str(payload.get("version") or "").strip()
    criteria_row = payload.get("criteria")

    if not gate_id:
        raise ValueError("research gate requires gate_id")
    if not version:
        raise ValueError("research gate requires version")
    if not isinstance(criteria_row, dict):
        raise ValueError("research gate requires criteria object")

    criteria = ResearchGateCriteria(
        min_runs=_as_int(criteria_row.get("min_runs"), "min_runs", minimum=1),
        min_parity_rate=_as_float(criteria_row.get("min_parity_rate"), "min_parity_rate", 0.0, 1.0),
        min_mean_score_delta=_as_float(
            criteria_row.get("min_mean_score_delta"),
            "min_mean_score_delta",
            -1.0,
            1.0,
        ),
        min_ci95_lower_bound=_as_float(
            criteria_row.get("min_ci95_lower_bound"),
            "min_ci95_lower_bound",
            -1.0,
            1.0,
        ),
        max_delta_std=_as_float(criteria_row.get("max_delta_std"), "max_delta_std", 0.0, 1.0),
        min_p10_score_delta=_as_float(
            criteria_row.get("min_p10_score_delta"),
            "min_p10_score_delta",
            -1.0,
            1.0,
        ),
        max_mean_auto_latency_ms=_as_float(
            criteria_row.get("max_mean_auto_latency_ms"),
            "max_mean_auto_latency_ms",
            0.0,
            10_000_000.0,
        ),
        max_mean_auto_token_cost=_as_float(
            criteria_row.get("max_mean_auto_token_cost"),
            "max_mean_auto_token_cost",
            0.0,
            1_000.0,
        ),
        max_failure_severe_ratio=_as_float(
            criteria_row.get("max_failure_severe_ratio"),
            "max_failure_severe_ratio",
            0.0,
            1.0,
        ),
        require_wilcoxon_significance=_as_bool(
            criteria_row.get("require_wilcoxon_significance"),
            "require_wilcoxon_significance",
        ),
        wilcoxon_alpha=_as_float(criteria_row.get("wilcoxon_alpha"), "wilcoxon_alpha", 0.0, 1.0),
    )
    return ResearchGateSpec(gate_id=gate_id, version=version, criteria=criteria)


def evaluate_research_gate(
    *,
    records: list[dict[str, Any]],
    parity_stats: dict[str, Any],
    failure_taxonomy_summary: dict[str, Any],
    gate: ResearchGateSpec,
) -> dict[str, Any]:
    if not records:
        raise ValueError("records must not be empty")

    deltas = [_to_float(row.get("score_delta"), "score_delta") for row in records]
    parity_rate_observed = mean([1.0 if bool(row.get("parity_achieved")) else 0.0 for row in records])
    mean_delta_observed = mean(deltas)
    ci_row = parity_stats.get("mean_score_delta_ci95")
    if not isinstance(ci_row, list) or len(ci_row) != 2:
        raise ValueError("parity_stats.mean_score_delta_ci95 must be a list with two numbers")
    ci_lo = _to_float(ci_row[0], "mean_score_delta_ci95[0]")
    delta_std_observed = pstdev(deltas) if len(deltas) > 1 else 0.0
    p10_delta_observed = percentile(deltas, 0.10)
    mean_auto_latency_ms_observed = _to_float(
        parity_stats.get("mean_auto_latency_ms"),
        "parity_stats.mean_auto_latency_ms",
    )
    mean_auto_token_cost_observed = _to_float(
        parity_stats.get("mean_auto_token_cost"),
        "parity_stats.mean_auto_token_cost",
    )

    by_severity_ratio = failure_taxonomy_summary.get("by_severity_ratio")
    if not isinstance(by_severity_ratio, dict):
        raise ValueError("failure_taxonomy_summary.by_severity_ratio must be an object")
    severe_ratio_observed = _to_float(by_severity_ratio.get("severe", 0.0), "by_severity_ratio.severe")

    wilcoxon_row = parity_stats.get("wilcoxon")
    if not isinstance(wilcoxon_row, dict):
        raise ValueError("parity_stats.wilcoxon must be an object")
    wilcoxon_p_value_observed = _to_float(wilcoxon_row.get("p_value"), "wilcoxon.p_value")

    criteria = gate.criteria
    checks = [
        _check("min_runs", len(records), criteria.min_runs, ">="),
        _check("min_parity_rate", parity_rate_observed, criteria.min_parity_rate, ">="),
        _check("min_mean_score_delta", mean_delta_observed, criteria.min_mean_score_delta, ">="),
        _check("min_ci95_lower_bound", ci_lo, criteria.min_ci95_lower_bound, ">="),
        _check("max_delta_std", delta_std_observed, criteria.max_delta_std, "<="),
        _check("min_p10_score_delta", p10_delta_observed, criteria.min_p10_score_delta, ">="),
        _check(
            "max_mean_auto_latency_ms",
            mean_auto_latency_ms_observed,
            criteria.max_mean_auto_latency_ms,
            "<=",
        ),
        _check(
            "max_mean_auto_token_cost",
            mean_auto_token_cost_observed,
            criteria.max_mean_auto_token_cost,
            "<=",
        ),
        _check(
            "max_failure_severe_ratio",
            severe_ratio_observed,
            criteria.max_failure_severe_ratio,
            "<=",
        ),
    ]

    if criteria.require_wilcoxon_significance:
        checks.append(
            _check(
                "wilcoxon_significance",
                wilcoxon_p_value_observed,
                criteria.wilcoxon_alpha,
                "<=",
            )
        )

    gate_passed = all(bool(check["passed"]) for check in checks)
    return {
        "gate_id": gate.gate_id,
        "version": gate.version,
        "gate_passed": gate_passed,
        "checks": checks,
        "observed": {
            "n_runs": len(records),
            "parity_rate": parity_rate_observed,
            "mean_score_delta": mean_delta_observed,
            "ci95_lower_bound": ci_lo,
            "delta_std": delta_std_observed,
            "p10_score_delta": p10_delta_observed,
            "mean_auto_latency_ms": mean_auto_latency_ms_observed,
            "mean_auto_token_cost": mean_auto_token_cost_observed,
            "failure_severe_ratio": severe_ratio_observed,
            "wilcoxon_p_value": wilcoxon_p_value_observed,
        },
    }


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    if not (0.0 <= ratio <= 1.0):
        raise ValueError("ratio must be in [0, 1]")

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = ratio * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    weight = position - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def _check(name: str, observed: float, threshold: float, operator: str) -> dict[str, Any]:
    if operator == ">=":
        passed = observed >= threshold
    elif operator == "<=":
        passed = observed <= threshold
    else:
        raise ValueError(f"unsupported operator: {operator}")
    return {
        "name": name,
        "passed": passed,
        "observed": observed,
        "threshold": threshold,
        "operator": operator,
    }


def _as_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _as_int(value: Any, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be integer")
    if value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return value


def _as_float(value: Any, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be number")
    parsed = float(value)
    if not (minimum <= parsed <= maximum):
        raise ValueError(f"{field} must be in [{minimum}, {maximum}]")
    return parsed


def _to_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be number")
    return float(value)
