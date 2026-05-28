"""Tests for forbidden tool call check."""

from __future__ import annotations

from rag_agent_audit.checks.tool_calls import check_forbidden_tools
from rag_agent_audit.normalizer import NormalizedResponse


def make_response(tool_calls: list[str]) -> NormalizedResponse:
    return NormalizedResponse(
        answer="Done.", citations=[], retrieved_sources=[], tool_calls=tool_calls
    )


def test_no_forbidden_tools_called_passes() -> None:
    r = make_response(["search_docs", "fetch_policy"])
    result = check_forbidden_tools(r, ["delete_user", "drop_table"])
    assert result.passed


def test_forbidden_tool_called_fails() -> None:
    r = make_response(["delete_user"])
    result = check_forbidden_tools(r, ["delete_user", "drop_table"])
    assert not result.passed
    assert "delete_user" in result.message


def test_empty_tool_calls_and_no_forbidden_passes() -> None:
    r = make_response([])
    result = check_forbidden_tools(r, ["delete_user"])
    assert result.passed


def test_no_forbidden_list_skipped() -> None:
    r = make_response(["delete_user"])
    result = check_forbidden_tools(r, [])
    assert result.passed
    assert "skipped" in result.message.lower()


def test_case_insensitive_tool_matching() -> None:
    r = make_response(["DELETE_USER"])
    result = check_forbidden_tools(r, ["delete_user"])
    assert not result.passed
