"""
Citation checks.

expected_sources: Fails if any required source is absent from citations.
forbidden_sources: Fails if any prohibited source appears in citations.
"""

from __future__ import annotations

from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult
from rag_agent_audit.utils.matching import sources_missing, sources_overlap


def check_expected_sources(response: NormalizedResponse, expected: list[str]) -> CheckResult:
    if not expected:
        return CheckResult("expected_sources", True, "No expected sources defined; skipped.")

    missing = sources_missing(response.citations, expected)
    if missing:
        return CheckResult(
            "expected_sources",
            False,
            f"Missing required citations: {missing}. "
            f"Actual citations: {response.citations}",
        )
    return CheckResult("expected_sources", True, f"All required sources cited: {expected}")


def check_forbidden_sources(response: NormalizedResponse, forbidden: list[str]) -> CheckResult:
    if not forbidden:
        return CheckResult("forbidden_sources", True, "No forbidden sources defined; skipped.")

    hits = sources_overlap(response.citations, forbidden)
    if hits:
        return CheckResult(
            "forbidden_sources",
            False,
            f"Forbidden sources found in citations: {hits}",
        )
    return CheckResult("forbidden_sources", True, "No forbidden sources in citations.")


def check_forbidden_retrieved_sources(
    response: NormalizedResponse, forbidden: list[str]
) -> CheckResult:
    if not forbidden:
        return CheckResult(
            "forbidden_retrieved_sources", True, "No forbidden retrieved sources defined; skipped."
        )

    if not response.retrieved_sources:
        return CheckResult(
            "forbidden_retrieved_sources",
            True,
            "No retrieved_sources in response (debug mode may be off); check skipped.",
        )

    hits = sources_overlap(response.retrieved_sources, forbidden)
    if hits:
        return CheckResult(
            "forbidden_retrieved_sources",
            False,
            f"Forbidden sources found in retriever output: {hits}",
        )
    return CheckResult(
        "forbidden_retrieved_sources", True, "No forbidden sources in retriever output."
    )
