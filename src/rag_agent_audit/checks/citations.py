"""
Citation checks.

expected_sources: Fails if any required source is absent from citations.
forbidden_sources: Fails if any prohibited source appears in citations.
forbidden_retrieved_sources: Same check against the retriever's raw output.
"""

from __future__ import annotations

from rag_agent_audit.checks.diagnostics import format_list
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult
from rag_agent_audit.utils.matching import sources_missing, sources_overlap


def check_expected_sources(response: NormalizedResponse, expected: list[str]) -> CheckResult:
    if not expected:
        return CheckResult("expected_sources", True, "No expected sources defined; skipped.")

    missing = sources_missing(response.citations, expected)
    if missing:
        msg = (
            "Check failed: expected_sources\n"
            "Missing expected sources:\n"
            f"{format_list(missing)}\n\n"
            "Actual citations:\n"
            f"{format_list(response.citations)}\n\n"
            "Suggestion:\n"
            "  Check retrieval, citation mapping, or expected source names."
        )
        return CheckResult("expected_sources", False, msg)
    return CheckResult("expected_sources", True, f"All required sources cited: {expected}")


def check_forbidden_sources(response: NormalizedResponse, forbidden: list[str]) -> CheckResult:
    if not forbidden:
        return CheckResult("forbidden_sources", True, "No forbidden sources defined; skipped.")

    hits = sources_overlap(response.citations, forbidden)
    if hits:
        msg = (
            "Check failed: forbidden_sources\n"
            "Forbidden sources found:\n"
            f"{format_list(hits)}\n\n"
            "Actual citations:\n"
            f"{format_list(response.citations)}\n\n"
            "Suggestion:\n"
            "  Check tenant filtering, document authorization, or citation rendering."
        )
        return CheckResult("forbidden_sources", False, msg)
    return CheckResult("forbidden_sources", True, "No forbidden sources in citations.")


def check_forbidden_retrieved_sources(
    response: NormalizedResponse, forbidden: list[str]
) -> CheckResult:
    if not forbidden:
        return CheckResult(
            "forbidden_retrieved_sources",
            True,
            "No forbidden retrieved sources defined; skipped.",
        )

    if not response.retrieved_sources:
        return CheckResult(
            "forbidden_retrieved_sources",
            True,
            "No retrieved_sources in response (debug mode may be off); check skipped.",
        )

    hits = sources_overlap(response.retrieved_sources, forbidden)
    if hits:
        msg = (
            "Check failed: forbidden_retrieved_sources\n"
            "Forbidden retrieved sources found:\n"
            f"{format_list(hits)}\n\n"
            "Actual retrieved sources:\n"
            f"{format_list(response.retrieved_sources)}\n\n"
            "Suggestion:\n"
            "  Check retriever metadata filters and tenant isolation before generation."
        )
        return CheckResult("forbidden_retrieved_sources", False, msg)
    return CheckResult(
        "forbidden_retrieved_sources", True, "No forbidden sources in retriever output."
    )
