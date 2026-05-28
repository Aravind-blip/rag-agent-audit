"""Tests for the diagnostics helper functions."""

from __future__ import annotations

from rag_agent_audit.checks.diagnostics import format_list, preview_text

# ---------------------------------------------------------------------------
# preview_text
# ---------------------------------------------------------------------------


def test_preview_text_returns_short_text_unchanged() -> None:
    assert preview_text("hello world") == "hello world"


def test_preview_text_empty_string_returns_placeholder() -> None:
    assert preview_text("") == "<empty>"


def test_preview_text_whitespace_only_returns_placeholder() -> None:
    assert preview_text("   \n\t  ") == "<empty>"


def test_preview_text_normalizes_internal_whitespace() -> None:
    result = preview_text("hello   \n\n   world")
    assert result == "hello world"


def test_preview_text_truncates_at_limit() -> None:
    long = "a" * 400
    result = preview_text(long, limit=300)
    assert len(result) == 303  # 300 chars + "..."
    assert result.endswith("...")


def test_preview_text_does_not_truncate_at_exact_limit() -> None:
    exact = "a" * 300
    result = preview_text(exact, limit=300)
    assert result == exact
    assert not result.endswith("...")


def test_preview_text_custom_limit() -> None:
    result = preview_text("abcdefgh", limit=5)
    assert result == "abcde..."


def test_preview_text_default_limit_is_300() -> None:
    just_under = "x" * 300
    result = preview_text(just_under)
    assert "..." not in result


# ---------------------------------------------------------------------------
# format_list
# ---------------------------------------------------------------------------


def test_format_list_single_item() -> None:
    result = format_list(["foo.pdf"])
    assert result == "  - foo.pdf"


def test_format_list_multiple_items() -> None:
    result = format_list(["a.pdf", "b.pdf"])
    assert "  - a.pdf" in result
    assert "  - b.pdf" in result


def test_format_list_empty_returns_none_placeholder() -> None:
    result = format_list([])
    assert "(none)" in result


def test_format_list_preserves_order() -> None:
    items = ["first", "second", "third"]
    lines = format_list(items).splitlines()
    assert lines[0].endswith("first")
    assert lines[1].endswith("second")
    assert lines[2].endswith("third")
