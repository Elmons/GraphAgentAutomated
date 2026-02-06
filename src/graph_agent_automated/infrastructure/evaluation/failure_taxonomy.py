from __future__ import annotations

from collections import Counter
from typing import Final

from graph_agent_automated.domain.models import CaseExecution, EvaluationSummary

FAILURE_CATEGORIES: Final[tuple[str, ...]] = (
    "tool_selection",
    "decomposition",
    "execution_grounding",
    "verifier_mismatch",
    "other",
)
FAILURE_SEVERITIES: Final[tuple[str, ...]] = ("mild", "moderate", "severe")

_EXECUTION_KEYWORDS: Final[tuple[str, ...]] = (
    "runtime_error",
    "timeout",
    "circuit open",
    "execution error",
    "exception",
    "traceback",
    "query failed",
    "cypher syntax",
)
_TOOL_KEYWORDS: Final[tuple[str, ...]] = (
    "tool",
    "action",
    "executor",
    "schemagetter",
    "cypherexecutor",
    "pagerankexecutor",
    "knowledgebaseretriever",
    "missing tool",
    "wrong tool",
)
_DECOMPOSITION_KEYWORDS: Final[tuple[str, ...]] = (
    "decompose",
    "decomposition",
    "subtask",
    "multi-step",
    "missing step",
    "planning",
    "workflow order",
    "reasoning chain",
)
_VERIFIER_MISMATCH_KEYWORDS: Final[tuple[str, ...]] = (
    "verifier",
    "expected",
    "mismatch",
    "not aligned",
    "format",
    "answer differs",
    "incorrect final answer",
)


def build_failure_taxonomy(
    auto_eval: EvaluationSummary,
    manual_eval: EvaluationSummary,
    *,
    failure_margin: float = 0.0,
) -> dict[str, object]:
    """Build failure taxonomy on cases where auto score trails manual score."""
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

        category, signal = classify_failure_case(auto_case, manual_case)
        severity = classify_failure_severity(auto_case.score, manual_case.score)
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
) -> tuple[str, str]:
    combined = f"{auto_case.output}\n{auto_case.rationale}".lower()
    manual_hint = (
        f"{manual_case.output}\n{manual_case.rationale}".lower()
        if manual_case is not None
        else ""
    )

    matched = _find_first_keyword(combined, _EXECUTION_KEYWORDS)
    if matched is not None:
        return ("execution_grounding", matched)

    matched = _find_first_keyword(combined, _TOOL_KEYWORDS)
    if matched is not None:
        return ("tool_selection", matched)

    matched = _find_first_keyword(combined, _DECOMPOSITION_KEYWORDS)
    if matched is not None:
        return ("decomposition", matched)

    matched = _find_first_keyword(combined, _VERIFIER_MISMATCH_KEYWORDS)
    if matched is not None:
        return ("verifier_mismatch", matched)

    if manual_hint and auto_case.score + 0.2 < (manual_case.score if manual_case is not None else 0.0):
        return ("decomposition", "manual_gap>=0.2")
    return ("other", "no_keyword_match")


def classify_failure_severity(auto_score: float, manual_score: float) -> str:
    gap = max(0.0, float(manual_score) - float(auto_score))
    if gap + 1e-9 >= 0.4:
        return "severe"
    if gap + 1e-9 >= 0.2:
        return "moderate"
    return "mild"


def _find_first_keyword(text: str, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        if keyword in text:
            return keyword
    return None
