"""Tests for expected_sources and forbidden_sources checks."""

from __future__ import annotations

from rag_agent_audit.checks.citations import (
    check_expected_sources,
    check_forbidden_retrieved_sources,
    check_forbidden_sources,
)
from rag_agent_audit.normalizer import NormalizedResponse


def make_response(citations: list[str], retrieved: list[str] | None = None) -> NormalizedResponse:
    return NormalizedResponse(
        answer="some answer",
        citations=citations,
        retrieved_sources=retrieved or [],
        tool_calls=[],
    )


# --- expected_sources ---

def test_expected_sources_all_present() -> None:
    r = make_response(["refund.pdf", "policy.pdf"])
    result = check_expected_sources(r, ["refund.pdf"])
    assert result.passed


def test_expected_sources_missing_source_fails() -> None:
    r = make_response(["other.pdf"])
    result = check_expected_sources(r, ["refund.pdf"])
    assert not result.passed
    assert "refund.pdf" in result.message


def test_expected_sources_empty_list_skipped() -> None:
    r = make_response(["anything.pdf"])
    result = check_expected_sources(r, [])
    assert result.passed
    assert "skipped" in result.message.lower()


def test_expected_sources_case_insensitive() -> None:
    r = make_response(["Refund_Policy.PDF"])
    result = check_expected_sources(r, ["refund_policy.pdf"])
    assert result.passed


# --- forbidden_sources ---

def test_forbidden_sources_not_present_passes() -> None:
    r = make_response(["org_a.pdf"])
    result = check_forbidden_sources(r, ["org_b.pdf"])
    assert result.passed


def test_forbidden_sources_present_fails() -> None:
    r = make_response(["org_b_compensation.pdf"])
    result = check_forbidden_sources(r, ["org_b_compensation.pdf"])
    assert not result.passed
    assert "org_b_compensation.pdf" in result.message


def test_forbidden_sources_empty_list_skipped() -> None:
    r = make_response(["org_b.pdf"])
    result = check_forbidden_sources(r, [])
    assert result.passed
    assert "skipped" in result.message.lower()


def test_forbidden_sources_case_insensitive() -> None:
    r = make_response(["ORG_B_COMP.PDF"])
    result = check_forbidden_sources(r, ["org_b_comp.pdf"])
    assert not result.passed


# --- forbidden_retrieved_sources ---

def test_forbidden_retrieved_not_present_passes() -> None:
    r = make_response([], retrieved=["org_a.pdf"])
    result = check_forbidden_retrieved_sources(r, ["org_b.pdf"])
    assert result.passed


def test_forbidden_retrieved_present_fails() -> None:
    r = make_response([], retrieved=["org_b_records.csv"])
    result = check_forbidden_retrieved_sources(r, ["org_b_records.csv"])
    assert not result.passed


def test_forbidden_retrieved_no_debug_data_skips() -> None:
    r = make_response([], retrieved=[])
    result = check_forbidden_retrieved_sources(r, ["org_b.pdf"])
    assert result.passed
    assert "debug mode" in result.message.lower() or "skipped" in result.message.lower()
