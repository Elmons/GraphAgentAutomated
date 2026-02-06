from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from graph_agent_automated.domain.models import CaseExecution, EvaluationSummary

FAILURE_CATEGORIES: Final[tuple[str, ...]] = (
    "tool_selection",
    "decomposition",
    "execution_grounding",
    "verifier_mismatch",
    "other",
)
FAILURE_SEVERITIES: Final[tuple[str, ...]] = ("mild", "moderate", "severe")


@dataclass(frozen=True)
class FailureTaxonomyRules:
    rules_id: str
    version: str
    execution_keywords: tuple[str, ...]
    tool_keywords: tuple[str, ...]
    decomposition_keywords: tuple[str, ...]
    verifier_mismatch_keywords: tuple[str, ...]
    severe_gap_threshold: float
    moderate_gap_threshold: float
    fallback_decomposition_gap_threshold: float


DEFAULT_FAILURE_TAXONOMY_RULES = FailureTaxonomyRules(
    rules_id="failure_taxonomy_rules_v1",
    version="1.0.0",
    execution_keywords=(
        "runtime_error",
        "timeout",
        "circuit open",
        "execution error",
        "exception",
        "traceback",
        "query failed",
        "cypher syntax",
    ),
    tool_keywords=(
        "tool",
        "action",
        "executor",
        "schemagetter",
        "cypherexecutor",
        "pagerankexecutor",
        "knowledgebaseretriever",
        "missing tool",
        "wrong tool",
    ),
    decomposition_keywords=(
        "decompose",
        "decomposition",
        "subtask",
        "multi-step",
        "missing step",
        "planning",
        "workflow order",
        "reasoning chain",
    ),
    verifier_mismatch_keywords=(
        "verifier",
        "expected",
        "mismatch",
        "not aligned",
        "format",
        "answer differs",
        "incorrect final answer",
    ),
    severe_gap_threshold=0.4,
    moderate_gap_threshold=0.2,
    fallback_decomposition_gap_threshold=0.2,
)


def get_default_failure_taxonomy_rules() -> FailureTaxonomyRules:
    return DEFAULT_FAILURE_TAXONOMY_RULES


def load_failure_taxonomy_rules(path: str | Path) -> FailureTaxonomyRules:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"failure taxonomy rules file not found: {file_path}")
    if file_path.suffix.lower() != ".json":
        raise ValueError("failure taxonomy rules file must be .json")

    with open(file_path, encoding="utf-8") as f:
        payload: Any = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("failure taxonomy rules payload must be a JSON object")

    rules_id = str(payload.get("rules_id") or "").strip()
    version = str(payload.get("version") or "").strip()
    keyword_row = payload.get("keywords")
    threshold_row = payload.get("thresholds")
    if not rules_id:
        raise ValueError("failure taxonomy rules requires rules_id")
    if not version:
        raise ValueError("failure taxonomy rules requires version")
    if not isinstance(keyword_row, dict):
        raise ValueError("failure taxonomy rules requires keywords object")
    if not isinstance(threshold_row, dict):
        raise ValueError("failure taxonomy rules requires thresholds object")

    execution_keywords = _as_keyword_tuple(keyword_row.get("execution_grounding"), "execution_grounding")
    tool_keywords = _as_keyword_tuple(keyword_row.get("tool_selection"), "tool_selection")
    decomposition_keywords = _as_keyword_tuple(keyword_row.get("decomposition"), "decomposition")
    verifier_mismatch_keywords = _as_keyword_tuple(
        keyword_row.get("verifier_mismatch"),
        "verifier_mismatch",
    )

    severe_gap_threshold = _as_float(
        threshold_row.get("severe_gap"),
        "thresholds.severe_gap",
        minimum=0.0,
        maximum=1.0,
    )
    moderate_gap_threshold = _as_float(
        threshold_row.get("moderate_gap"),
        "thresholds.moderate_gap",
        minimum=0.0,
        maximum=1.0,
    )
    fallback_gap_threshold = _as_float(
        threshold_row.get("fallback_decomposition_gap"),
        "thresholds.fallback_decomposition_gap",
        minimum=0.0,
        maximum=1.0,
    )
    if moderate_gap_threshold > severe_gap_threshold:
        raise ValueError("thresholds.moderate_gap must be <= thresholds.severe_gap")

    return FailureTaxonomyRules(
        rules_id=rules_id,
        version=version,
        execution_keywords=execution_keywords,
        tool_keywords=tool_keywords,
        decomposition_keywords=decomposition_keywords,
        verifier_mismatch_keywords=verifier_mismatch_keywords,
        severe_gap_threshold=severe_gap_threshold,
        moderate_gap_threshold=moderate_gap_threshold,
        fallback_decomposition_gap_threshold=fallback_gap_threshold,
    )


def build_failure_taxonomy(
    auto_eval: EvaluationSummary,
    manual_eval: EvaluationSummary,
    *,
    failure_margin: float = 0.0,
    rules: FailureTaxonomyRules | None = None,
) -> dict[str, object]:
    """Build failure taxonomy on cases where auto score trails manual score."""
    active_rules = rules or DEFAULT_FAILURE_TAXONOMY_RULES
    manual_by_case_id = {case.case_id: case for case in manual_eval.case_results}
    by_category: Counter[str] = Counter({category: 0 for category in FAILURE_CATEGORIES})
    by_severity: Counter[str] = Counter({severity: 0 for severity in FAILURE_SEVERITIES})
    case_items: list[dict[str, object]] = []

    for auto_case in auto_eval.case_results:
        manual_case = manual_by_case_id.get(auto_case.case_id)
        if manual_case is None:
            continue
        if auto_case.score + failure_margin >= manual_case.score:
            continue

        category, signal = classify_failure_case(auto_case, manual_case, rules=active_rules)
        severity = classify_failure_severity(auto_case.score, manual_case.score, rules=active_rules)
        gap = float(manual_case.score - auto_case.score)

        by_category[category] += 1
        by_severity[severity] += 1
        case_items.append(
            {
                "case_id": auto_case.case_id,
                "category": category,
                "severity": severity,
                "signal": signal,
                "auto_score": float(auto_case.score),
                "manual_score": float(manual_case.score),
                "score_gap": gap,
            }
        )

    case_items.sort(key=lambda row: float(row["score_gap"]), reverse=True)
    total_failures = len(case_items)
    if total_failures > 0:
        by_category_ratio = {
            category: by_category[category] / total_failures for category in FAILURE_CATEGORIES
        }
        by_severity_ratio = {
            severity: by_severity[severity] / total_failures for severity in FAILURE_SEVERITIES
        }
    else:
        by_category_ratio = {category: 0.0 for category in FAILURE_CATEGORIES}
        by_severity_ratio = {severity: 0.0 for severity in FAILURE_SEVERITIES}

    return {
        "rules_id": active_rules.rules_id,
        "rules_version": active_rules.version,
        "total_failures": total_failures,
        "failure_margin": float(failure_margin),
        "by_category": {category: int(by_category[category]) for category in FAILURE_CATEGORIES},
        "by_category_ratio": by_category_ratio,
        "by_severity": {severity: int(by_severity[severity]) for severity in FAILURE_SEVERITIES},
        "by_severity_ratio": by_severity_ratio,
        "case_items": case_items,
    }


def classify_failure_case(
    auto_case: CaseExecution,
    manual_case: CaseExecution | None = None,
    *,
    rules: FailureTaxonomyRules | None = None,
) -> tuple[str, str]:
    active_rules = rules or DEFAULT_FAILURE_TAXONOMY_RULES
    combined = f"{auto_case.output}\n{auto_case.rationale}".lower()
    manual_hint = (
        f"{manual_case.output}\n{manual_case.rationale}".lower()
        if manual_case is not None
        else ""
    )

    matched = _find_first_keyword(combined, active_rules.execution_keywords)
    if matched is not None:
        return ("execution_grounding", matched)

    matched = _find_first_keyword(combined, active_rules.tool_keywords)
    if matched is not None:
        return ("tool_selection", matched)

    matched = _find_first_keyword(combined, active_rules.decomposition_keywords)
    if matched is not None:
        return ("decomposition", matched)

    matched = _find_first_keyword(combined, active_rules.verifier_mismatch_keywords)
    if matched is not None:
        return ("verifier_mismatch", matched)

    if manual_hint and auto_case.score + active_rules.fallback_decomposition_gap_threshold < (
        manual_case.score if manual_case is not None else 0.0
    ):
        return (
            "decomposition",
            f"manual_gap>={active_rules.fallback_decomposition_gap_threshold:.3f}",
        )
    return ("other", "no_keyword_match")


def classify_failure_severity(
    auto_score: float,
    manual_score: float,
    *,
    rules: FailureTaxonomyRules | None = None,
) -> str:
    active_rules = rules or DEFAULT_FAILURE_TAXONOMY_RULES
    gap = max(0.0, float(manual_score) - float(auto_score))
    if gap + 1e-9 >= active_rules.severe_gap_threshold:
        return "severe"
    if gap + 1e-9 >= active_rules.moderate_gap_threshold:
        return "moderate"
    return "mild"


def _find_first_keyword(text: str, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        if keyword in text:
            return keyword
    return None


def _as_keyword_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"keywords.{field} must be a list")
    output: list[str] = []
    for row in value:
        keyword = str(row or "").strip().lower()
        if not keyword:
            continue
        output.append(keyword)
    if not output:
        raise ValueError(f"keywords.{field} must not be empty")
    return tuple(output)


def _as_float(value: Any, field: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be number")
    parsed = float(value)
    if not (minimum <= parsed <= maximum):
        raise ValueError(f"{field} must be in [{minimum}, {maximum}]")
    return parsed
