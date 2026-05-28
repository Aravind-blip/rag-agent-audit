"""Tests for fallback check."""

from __future__ import annotations

from rag_agent_audit.checks.fallback import check_fallback
from rag_agent_audit.normalizer import NormalizedResponse

FALLBACK_PATTERNS = [
    "I could not find",
    "not available in the provided sources",
    "I don't have enough information",
]


def make_response(answer: str) -> NormalizedResponse:
    return NormalizedResponse(answer=answer, citations=[], retrieved_sources=[], tool_calls=[])


def test_should_fallback_true_and_did_fallback_passes() -> None:
    r = make_response("I could not find that information in the available sources.")
    result = check_fallback(r, True, FALLBACK_PATTERNS)
    assert result.passed


def test_should_fallback_true_but_answered_fails() -> None:
    r = make_response("Here is the compensation policy details.")
    result = check_fallback(r, True, FALLBACK_PATTERNS)
    assert not result.passed
    assert "fallback" in result.message.lower()


def test_should_fallback_false_and_answered_passes() -> None:
    r = make_response("Refunds are available within 30 days.")
    result = check_fallback(r, False, FALLBACK_PATTERNS)
    assert result.passed


def test_should_fallback_false_but_fell_back_fails() -> None:
    r = make_response("I could not find that.")
    result = check_fallback(r, False, FALLBACK_PATTERNS)
    assert not result.passed


def test_should_fallback_none_skipped() -> None:
    r = make_response("whatever")
    result = check_fallback(r, None, FALLBACK_PATTERNS)
    assert result.passed
    assert "skipped" in result.message.lower()


def test_no_fallback_patterns_defined_skips() -> None:
    r = make_response("whatever")
    result = check_fallback(r, True, [])
    assert result.passed
    assert "skipped" in result.message.lower()
