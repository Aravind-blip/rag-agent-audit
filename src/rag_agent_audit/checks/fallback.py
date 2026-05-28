"""
Fallback check.

should_fallback=true: Fails if none of the fallback patterns appear in the answer.
should_fallback=false: Fails if any fallback pattern appears in the answer.

Fallback patterns are defined at the suite level so they are consistent
across all tests.
"""

from __future__ import annotations

from rag_agent_audit.checks.diagnostics import format_list, preview_text
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
        msg = (
            "Check failed: fallback\n"
            "Expected fallback/refusal response, but none of the configured\n"
            "fallback patterns matched.\n\n"
            "Fallback patterns checked:\n"
            f"{format_list(fallback_patterns)}\n\n"
            "Answer preview:\n"
            f'  "{preview_text(response.answer)}"\n\n'
            "Suggestion:\n"
            "  Add a clear fallback policy to the app or update fallback_patterns\n"
            "  if the app already refused safely with different wording."
        )
        return CheckResult("fallback", False, msg)

    if not should_fallback and did_fallback:
        msg = (
            "Check failed: fallback\n"
            "Expected a non-fallback answer, but matched fallback patterns:\n"
            f"{format_list(hits)}\n\n"
            "Answer preview:\n"
            f'  "{preview_text(response.answer)}"\n\n'
            "Suggestion:\n"
            "  Confirm whether this test should expect fallback. For secret or\n"
            "  dangerous-action prompts, should_fallback may need to be true or omitted."
        )
        return CheckResult("fallback", False, msg)

    status = "fell back" if did_fallback else "answered confidently"
    return CheckResult("fallback", True, f"Fallback behavior correct: system {status}.")
