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


# ---------------------------------------------------------------------------
# Improved diagnostic message structure
# ---------------------------------------------------------------------------


def test_fallback_expected_but_missing_has_check_header() -> None:
    r = make_response("Here is the full compensation data.")
    result = check_fallback(r, True, FALLBACK_PATTERNS)
    assert "Check failed: fallback" in result.message


def test_fallback_expected_but_missing_lists_patterns_checked() -> None:
    r = make_response("Here is the full compensation data.")
    result = check_fallback(r, True, FALLBACK_PATTERNS)
    assert "  - I could not find" in result.message
    assert "Fallback patterns checked" in result.message


def test_fallback_expected_but_missing_includes_answer_preview() -> None:
    r = make_response("Here is the full compensation data.")
    result = check_fallback(r, True, FALLBACK_PATTERNS)
    assert "Answer preview" in result.message
    assert "Here is the full compensation data." in result.message


def test_fallback_expected_but_missing_includes_suggestion() -> None:
    r = make_response("confident answer with no fallback")
    result = check_fallback(r, True, FALLBACK_PATTERNS)
    assert "Suggestion" in result.message


def test_fallback_not_expected_but_matched_has_check_header() -> None:
    r = make_response("I could not find that information.")
    result = check_fallback(r, False, FALLBACK_PATTERNS)
    assert "Check failed: fallback" in result.message


def test_fallback_not_expected_but_matched_lists_matched_patterns() -> None:
    r = make_response("I could not find that information.")
    result = check_fallback(r, False, FALLBACK_PATTERNS)
    assert "  - I could not find" in result.message


def test_fallback_not_expected_but_matched_includes_answer_preview() -> None:
    r = make_response("I could not find that information.")
    result = check_fallback(r, False, FALLBACK_PATTERNS)
    assert "Answer preview" in result.message
    assert "I could not find that information." in result.message


def test_fallback_not_expected_but_matched_includes_suggestion() -> None:
    r = make_response("I don't have enough information.")
    result = check_fallback(r, False, FALLBACK_PATTERNS)
    assert "Suggestion" in result.message
