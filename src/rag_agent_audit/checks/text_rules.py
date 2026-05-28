"""
Text rule checks.

must_contain: Fails if any required string is absent from the answer.
must_not_contain: Fails if any prohibited string appears in the answer.
Used for prompt injection detection and expected content verification.
"""

from __future__ import annotations

from rag_agent_audit.checks.diagnostics import format_list, preview_text
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult
from rag_agent_audit.utils.matching import contains_any


def check_must_contain(response: NormalizedResponse, patterns: list[str]) -> CheckResult:
    if not patterns:
        return CheckResult("must_contain", True, "No must_contain patterns defined; skipped.")

    missing = [p for p in patterns if p.lower() not in response.answer.lower()]
    if missing:
        msg = (
            "Check failed: must_contain\n"
            "Missing required strings:\n"
            f"{format_list(missing)}\n\n"
            "Answer preview:\n"
            f'  "{preview_text(response.answer)}"\n\n'
            "Suggestion:\n"
            "  Confirm whether this exact phrase is expected, or avoid brittle\n"
            "  exact-string checks for small local models."
        )
        return CheckResult("must_contain", False, msg)
    return CheckResult("must_contain", True, f"All required strings found: {patterns}")


def check_must_not_contain(response: NormalizedResponse, patterns: list[str]) -> CheckResult:
    if not patterns:
        return CheckResult(
            "must_not_contain", True, "No must_not_contain patterns defined; skipped."
        )

    hits = contains_any(response.answer, patterns)
    if hits:
        msg = (
            "Check failed: must_not_contain\n"
            "Prohibited strings found:\n"
            f"{format_list(hits)}\n\n"
            "Answer preview:\n"
            f'  "{preview_text(response.answer)}"\n\n'
            "Suggestion:\n"
            "  Remove sensitive output from the response or tighten the\n"
            "  application guardrail."
        )
        return CheckResult("must_not_contain", False, msg)
    return CheckResult("must_not_contain", True, "No prohibited strings found in answer.")
