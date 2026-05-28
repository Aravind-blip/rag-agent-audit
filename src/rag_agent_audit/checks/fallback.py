"""
Fallback check.

should_fallback=true: Fails if none of the fallback patterns appear in the answer.
should_fallback=false: Fails if any fallback pattern appears in the answer.

Fallback patterns are defined at the suite level so they are consistent
across all tests.
"""

from __future__ import annotations

from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult
from rag_agent_audit.utils.matching import contains_any


def check_fallback(
    response: NormalizedResponse,
    should_fallback: bool | None,
    fallback_patterns: list[str],
) -> CheckResult:
    if should_fallback is None:
        return CheckResult("fallback", True, "should_fallback not set; skipped.")

    if not fallback_patterns:
        return CheckResult(
            "fallback",
            True,
            "No fallback_patterns defined in suite; fallback check skipped.",
        )

    hits = contains_any(response.answer, fallback_patterns)
    did_fallback = len(hits) > 0

    if should_fallback and not did_fallback:
        return CheckResult(
            "fallback",
            False,
            "Expected a fallback response but the system answered confidently. "
            f"Fallback patterns checked: {fallback_patterns}",
        )

    if not should_fallback and did_fallback:
        return CheckResult(
            "fallback",
            False,
            f"Expected a confident answer but got a fallback response. "
            f"Matched patterns: {hits}",
        )

    status = "fell back" if did_fallback else "answered confidently"
    return CheckResult("fallback", True, f"Fallback behavior correct: system {status}.")
