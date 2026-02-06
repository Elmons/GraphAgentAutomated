from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HypothesisCriteria:
    min_pairs: int
    min_mean_score_delta: float
    min_ci95_lower_bound: float
    min_p10_score_delta: float
    max_score_delta_std: float
    min_win_rate: float
    require_wilcoxon_significance: bool
    wilcoxon_alpha: float
    min_cliffs_delta: float


@dataclass(frozen=True)
class HypothesisSpec:
    hypothesis_id: str
    version: str
    baseline_arm: str
    target_arm: str
    criteria: HypothesisCriteria


def load_hypothesis_spec(path: str | Path) -> HypothesisSpec:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"hypothesis spec file not found: {file_path}")
    if file_path.suffix.lower() != ".json":
        raise ValueError("hypothesis spec file must be .json")

    with open(file_path, encoding="utf-8") as f:
        payload: Any = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("hypothesis spec payload must be a JSON object")

    hypothesis_id = str(payload.get("hypothesis_id") or "").strip()
    version = str(payload.get("version") or "").strip()
    baseline_arm = str(payload.get("baseline_arm") or "").strip()
    target_arm = str(payload.get("target_arm") or "").strip()
    criteria_row = payload.get("criteria")

    if not hypothesis_id:
        raise ValueError("hypothesis spec requires hypothesis_id")
    if not version:
        raise ValueError("hypothesis spec requires version")
    if not baseline_arm:
        raise ValueError("hypothesis spec requires baseline_arm")
    if not target_arm:
        raise ValueError("hypothesis spec requires target_arm")
    if not isinstance(criteria_row, dict):
        raise ValueError("hypothesis spec requires criteria object")

    criteria = HypothesisCriteria(
        min_pairs=_as_int(criteria_row.get("min_pairs"), "criteria.min_pairs", minimum=1),
        min_mean_score_delta=_as_float(
            criteria_row.get("min_mean_score_delta"),
            "criteria.min_mean_score_delta",
            -1.0,
            1.0,
        ),
        min_ci95_lower_bound=_as_float(
            criteria_row.get("min_ci95_lower_bound"),
            "criteria.min_ci95_lower_bound",
            -1.0,
            1.0,
        ),
        min_p10_score_delta=_as_float(
            criteria_row.get("min_p10_score_delta"),
            "criteria.min_p10_score_delta",
            -1.0,
            1.0,
        ),
        max_score_delta_std=_as_float(
            criteria_row.get("max_score_delta_std"),
            "criteria.max_score_delta_std",
            0.0,
            1.0,
        ),
        min_win_rate=_as_float(criteria_row.get("min_win_rate"), "criteria.min_win_rate", 0.0, 1.0),
        require_wilcoxon_significance=_as_bool(
            criteria_row.get("require_wilcoxon_significance"),
            "criteria.require_wilcoxon_significance",
        ),
        wilcoxon_alpha=_as_float(
            criteria_row.get("wilcoxon_alpha"),
            "criteria.wilcoxon_alpha",
            0.0,
            1.0,
        ),
        min_cliffs_delta=_as_float(
            criteria_row.get("min_cliffs_delta"),
            "criteria.min_cliffs_delta",
            -1.0,
            1.0,
        ),
    )
    return HypothesisSpec(
        hypothesis_id=hypothesis_id,
        version=version,
        baseline_arm=baseline_arm,
        target_arm=target_arm,
        criteria=criteria,
    )


def evaluate_hypothesis(
    *,
    arm_comparison_report: dict[str, Any],
    spec: HypothesisSpec,
) -> dict[str, Any]:
    baseline_arm = str(arm_comparison_report.get("baseline_arm") or "").strip()
    if baseline_arm != spec.baseline_arm:
        raise ValueError(
            f"baseline arm mismatch: report={baseline_arm} spec={spec.baseline_arm}",
        )

    targets_row = arm_comparison_report.get("targets")
    if not isinstance(targets_row, list):
        raise ValueError("arm comparison report requires targets list")

    target_row = next(
        (
            row
            for row in targets_row
            if isinstance(row, dict) and str(row.get("target_arm") or "").strip() == spec.target_arm
        ),
        None,
    )
    if target_row is None:
        raise ValueError(f"target arm not found in comparison report: {spec.target_arm}")

    summary = target_row.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("target summary must be object")

    observed = {
        "n_pairs": _to_float(summary.get("n_pairs"), "summary.n_pairs"),
        "mean_score_delta": _to_float(summary.get("mean_score_delta"), "summary.mean_score_delta"),
        "ci95_lower_bound": _extract_ci_lower_bound(summary.get("score_delta_ci95")),
        "p10_score_delta": _to_float(summary.get("p10_score_delta"), "summary.p10_score_delta"),
        "score_delta_std": _to_float(summary.get("score_delta_std"), "summary.score_delta_std"),
        "win_rate": _to_float(summary.get("win_rate"), "summary.win_rate"),
        "wilcoxon_p_value": _extract_wilcoxon_p(summary.get("wilcoxon")),
        "cliffs_delta": _extract_cliffs_delta(summary.get("cliffs_delta")),
    }

    criteria = spec.criteria
    checks = [
        _check("min_pairs", observed["n_pairs"], float(criteria.min_pairs), ">="),
        _check(
            "min_mean_score_delta",
            observed["mean_score_delta"],
            criteria.min_mean_score_delta,
            ">=",
        ),
        _check(
            "min_ci95_lower_bound",
            observed["ci95_lower_bound"],
            criteria.min_ci95_lower_bound,
            ">=",
        ),
        _check(
            "min_p10_score_delta",
            observed["p10_score_delta"],
            criteria.min_p10_score_delta,
            ">=",
        ),
        _check(
            "max_score_delta_std",
            observed["score_delta_std"],
            criteria.max_score_delta_std,
            "<=",
        ),
        _check(
            "min_win_rate",
            observed["win_rate"],
            criteria.min_win_rate,
            ">=",
        ),
        _check(
            "min_cliffs_delta",
            observed["cliffs_delta"],
            criteria.min_cliffs_delta,
            ">=",
        ),
    ]
    if criteria.require_wilcoxon_significance:
        checks.append(
            _check(
                "wilcoxon_significance",
                observed["wilcoxon_p_value"],
                criteria.wilcoxon_alpha,
                "<=",
            )
        )

    supported = all(bool(check["passed"]) for check in checks)
    return {
        "hypothesis_id": spec.hypothesis_id,
        "version": spec.version,
        "baseline_arm": spec.baseline_arm,
        "target_arm": spec.target_arm,
        "supported": supported,
        "checks": checks,
        "observed": observed,
        "summary": summary,
    }


def _extract_ci_lower_bound(value: Any) -> float:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("summary.score_delta_ci95 must be [lo, hi]")
    return _to_float(value[0], "summary.score_delta_ci95[0]")


def _extract_wilcoxon_p(value: Any) -> float:
    if not isinstance(value, dict):
        raise ValueError("summary.wilcoxon must be object")
    return _to_float(value.get("p_value"), "summary.wilcoxon.p_value")


def _extract_cliffs_delta(value: Any) -> float:
    if not isinstance(value, dict):
        raise ValueError("summary.cliffs_delta must be object")
    return _to_float(value.get("value"), "summary.cliffs_delta.value")


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


def _as_int(value: Any, field: str, *, minimum: int) -> int:
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
