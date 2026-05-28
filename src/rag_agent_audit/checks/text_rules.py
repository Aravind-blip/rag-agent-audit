"""
Text rule checks.

must_contain: Fails if any required string is absent from the answer.
must_not_contain: Fails if any prohibited string appears in the answer.
Used for prompt injection detection and expected content verification.
"""

from __future__ import annotations

from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult
from rag_agent_audit.utils.matching import contains_any


def check_must_contain(response: NormalizedResponse, patterns: list[str]) -> CheckResult:
    if not patterns:
        return CheckResult("must_contain", True, "No must_contain patterns defined; skipped.")

    missing = [p for p in patterns if p.lower() not in response.answer.lower()]
    if missing:
        return CheckResult(
            "must_contain",
            False,
            f"Answer missing required strings: {missing}",
        )
    return CheckResult("must_contain", True, f"All required strings found: {patterns}")


def check_must_not_contain(response: NormalizedResponse, patterns: list[str]) -> CheckResult:
    if not patterns:
        return CheckResult(
            "must_not_contain", True, "No must_not_contain patterns defined; skipped."
        )

    hits = contains_any(response.answer, patterns)
    if hits:
        return CheckResult(
            "must_not_contain",
            False,
            f"Answer contains prohibited strings: {hits}",
        )
    return CheckResult("must_not_contain", True, "No prohibited strings found in answer.")
