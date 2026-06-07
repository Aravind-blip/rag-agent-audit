"""Tests for check_tool_policy (v0.6 MCP-style agent tool policy checks)."""

from __future__ import annotations

from rag_agent_audit.checks.tool_policy import check_tool_policy
from rag_agent_audit.normalizer import NormalizedResponse

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def resp(
    tool_calls: list[str] | None = None,
    approved: list[str] | None = None,
) -> NormalizedResponse:
    """Build a NormalizedResponse with only tool-relevant fields set.

    approved=None  → approved_tools mapping not configured (sentinel)
    approved=[]    → mapping configured, no approvals in this response
    approved=[...] → mapping configured with explicit approvals
    """
    return NormalizedResponse(
        tool_calls=tool_calls or [],
        approved_tools=approved,
    )


# ===========================================================================
# Skip / trivial
# ===========================================================================


def test_skip_when_all_lists_empty() -> None:
    result = check_tool_policy(resp(["search_docs"]), [], [], [])
    assert result.passed
    assert "skipped" in result.message.lower()


def test_skip_check_name() -> None:
    result = check_tool_policy(resp(), [], [], [])
    assert result.check_name == "tool_policy"


def test_pass_check_name() -> None:
    result = check_tool_policy(resp(["search_docs"]), ["search_docs"], [], [])
    assert result.check_name == "tool_policy"


def test_fail_check_name() -> None:
    result = check_tool_policy(resp(["exec_shell"]), ["search_docs"], [], [])
    assert result.check_name == "tool_policy"


# ===========================================================================
# Sub-rule 1: allowed_tools
# ===========================================================================


def test_allowed_pass_all_calls_in_list() -> None:
    result = check_tool_policy(
        resp(["search_docs", "get_user_info"]),
        ["search_docs", "get_user_info", "summarize"],
        [],
        [],
    )
    assert result.passed


def test_allowed_pass_no_calls() -> None:
    result = check_tool_policy(resp([]), ["search_docs", "get_user_info"], [], [])
    assert result.passed


def test_allowed_fail_one_disallowed_call() -> None:
    result = check_tool_policy(resp(["exec_shell"]), ["search_docs"], [], [])
    assert not result.passed


def test_allowed_fail_multiple_disallowed_calls() -> None:
    result = check_tool_policy(
        resp(["exec_shell", "drop_table"]), ["search_docs"], [], []
    )
    assert not result.passed


def test_allowed_fail_includes_disallowed_in_msg() -> None:
    result = check_tool_policy(resp(["exec_shell"]), ["search_docs"], [], [])
    assert "exec_shell" in result.message


def test_allowed_fail_includes_allowed_list_in_msg() -> None:
    result = check_tool_policy(resp(["exec_shell"]), ["search_docs"], [], [])
    assert "search_docs" in result.message


def test_allowed_fail_includes_actual_calls_in_msg() -> None:
    result = check_tool_policy(
        resp(["exec_shell", "search_docs"]), ["search_docs"], [], []
    )
    assert "  - exec_shell" in result.message
    assert "  - search_docs" in result.message


def test_allowed_fail_has_check_header() -> None:
    result = check_tool_policy(resp(["exec_shell"]), ["search_docs"], [], [])
    assert "Check failed: tool_policy" in result.message


def test_allowed_only_configured_no_calls_passes() -> None:
    result = check_tool_policy(resp([]), ["search_docs"], [], [])
    assert result.passed


def test_allowed_partial_overlap_fails() -> None:
    result = check_tool_policy(
        resp(["search_docs", "delete_user"]), ["search_docs"], [], []
    )
    assert not result.passed
    assert "delete_user" in result.message


def test_allowed_empty_list_with_other_rules_skips_subcheck() -> None:
    """allowed_tools=[] with patterns configured — allowed sub-rule inactive."""
    result = check_tool_policy(resp(["search_docs"]), [], [], ["exec_*"])
    # No exec_* match → passes
    assert result.passed


def test_allowed_fail_msg_has_suggestion() -> None:
    result = check_tool_policy(resp(["exec_shell"]), ["search_docs"], [], [])
    assert "Suggestion" in result.message


# ===========================================================================
# Sub-rule 2: forbidden_tool_patterns
# ===========================================================================


def test_patterns_pass_no_match() -> None:
    result = check_tool_policy(resp(["search_docs"]), [], [], ["exec_*", "drop_*"])
    assert result.passed


def test_patterns_pass_no_calls() -> None:
    result = check_tool_policy(resp([]), [], [], ["exec_*"])
    assert result.passed


def test_patterns_fail_exact_match() -> None:
    result = check_tool_policy(resp(["exec_shell"]), [], [], ["exec_shell"])
    assert not result.passed


def test_patterns_fail_wildcard_prefix() -> None:
    result = check_tool_policy(resp(["delete_user"]), [], [], ["delete_*"])
    assert not result.passed
    assert "delete_user" in result.message


def test_patterns_fail_wildcard_suffix() -> None:
    result = check_tool_policy(resp(["query_internal"]), [], [], ["*_internal"])
    assert not result.passed
    assert "query_internal" in result.message


def test_patterns_fail_star_matches_anything() -> None:
    result = check_tool_policy(resp(["search_docs"]), [], [], ["*"])
    assert not result.passed


def test_patterns_fail_deduplication() -> None:
    """Tool matching two different patterns appears once in the 'matched' section."""
    result = check_tool_policy(resp(["exec_shell"]), [], [], ["exec_*", "*_shell"])
    assert not result.passed
    assert "exec_shell" in result.message
    # The matched section ends just before "Forbidden patterns:"; exec_shell
    # should appear there exactly once (deduplication), even though it also
    # appears in the "Actual tool calls:" section further down.
    matched_section = result.message.split("Forbidden patterns:")[0]
    assert matched_section.count("  - exec_shell") == 1


def test_patterns_fail_includes_matched_tool_name() -> None:
    result = check_tool_policy(resp(["exec_shell"]), [], [], ["exec_*"])
    assert "exec_shell" in result.message


def test_patterns_fail_includes_pattern_in_msg() -> None:
    result = check_tool_policy(resp(["exec_shell"]), [], [], ["exec_*"])
    assert "exec_*" in result.message


def test_patterns_fail_includes_actual_calls_in_msg() -> None:
    result = check_tool_policy(
        resp(["exec_shell", "search_docs"]), [], [], ["exec_*"]
    )
    assert "  - exec_shell" in result.message
    assert "  - search_docs" in result.message


def test_patterns_only_configured_no_calls_passes() -> None:
    result = check_tool_policy(resp([]), [], [], ["exec_*"])
    assert result.passed


def test_patterns_multiple_patterns_first_match_wins() -> None:
    """Tool matching the first pattern is flagged; later patterns don't re-add it."""
    result = check_tool_policy(resp(["exec_shell"]), [], [], ["exec_*", "exec_shell"])
    assert not result.passed
    # Same deduplication check as above: count only within the matched section.
    matched_section = result.message.split("Forbidden patterns:")[0]
    assert matched_section.count("  - exec_shell") == 1


# ===========================================================================
# Sub-rule 3: required_approval_tools
# ===========================================================================


def test_approval_pass_tool_not_called() -> None:
    result = check_tool_policy(
        resp(["search_docs"], approved=["search_docs"]),
        [],
        ["send_email"],
        [],
    )
    assert result.passed


def test_approval_pass_tool_called_and_approved() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=["send_email"]),
        [],
        ["send_email"],
        [],
    )
    assert result.passed


def test_approval_fail_called_without_approval() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=[]),
        [],
        ["send_email"],
        [],
    )
    assert not result.passed


def test_approval_fail_mapping_not_configured() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=None),
        [],
        ["send_email"],
        [],
    )
    assert not result.passed


def test_approval_fail_mapping_not_configured_msg_mentions_response_mapping() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=None),
        [],
        ["send_email"],
        [],
    )
    assert "response_mapping" in result.message


def test_approval_fail_called_without_approval_includes_tool_name() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=[]),
        [],
        ["send_email"],
        [],
    )
    assert "send_email" in result.message


def test_approval_fail_includes_actual_calls() -> None:
    result = check_tool_policy(
        resp(["send_email", "search_docs"], approved=[]),
        [],
        ["send_email"],
        [],
    )
    assert "  - send_email" in result.message
    assert "  - search_docs" in result.message


def test_approval_pass_empty_approved_list_tool_not_called() -> None:
    result = check_tool_policy(
        resp(["search_docs"], approved=[]),
        [],
        ["send_email"],
        [],
    )
    assert result.passed


def test_approval_fail_empty_approved_list_tool_called() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=[]),
        [],
        ["send_email"],
        [],
    )
    assert not result.passed


def test_approval_pass_multiple_required_all_approved() -> None:
    result = check_tool_policy(
        resp(["send_email", "write_db"], approved=["send_email", "write_db"]),
        [],
        ["send_email", "write_db"],
        [],
    )
    assert result.passed


def test_approval_fail_one_of_multiple_unapproved() -> None:
    result = check_tool_policy(
        resp(["send_email", "write_db"], approved=["send_email"]),
        [],
        ["send_email", "write_db"],
        [],
    )
    assert not result.passed
    assert "write_db" in result.message


def test_approval_only_configured_tool_not_called_passes() -> None:
    result = check_tool_policy(
        resp(["search_docs"], approved=[]),
        [],
        ["send_email"],
        [],
    )
    assert result.passed


def test_approval_pass_approved_tools_has_extra_entries() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=["send_email", "write_db", "delete_record"]),
        [],
        ["send_email"],
        [],
    )
    assert result.passed


def test_approval_fail_includes_approved_tools_section() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=["write_db"]),
        [],
        ["send_email"],
        [],
    )
    assert "Approved tools:" in result.message
    assert "  - write_db" in result.message


# ===========================================================================
# Combined / interaction
# ===========================================================================


def test_combined_all_pass_all_three_configured() -> None:
    result = check_tool_policy(
        resp(["search_docs"], approved=["search_docs"]),
        ["search_docs", "summarize"],
        ["search_docs"],
        ["exec_*"],
    )
    assert result.passed


def test_combined_allowed_and_patterns_both_fail() -> None:
    result = check_tool_policy(
        resp(["exec_shell"]),
        ["search_docs"],
        [],
        ["exec_*"],
    )
    assert not result.passed
    assert "outside allowed list" in result.message
    assert "forbidden patterns" in result.message.lower()


def test_combined_allowed_and_approval_both_fail() -> None:
    result = check_tool_policy(
        resp(["exec_shell", "send_email"], approved=[]),
        ["search_docs"],
        ["send_email"],
        [],
    )
    assert not result.passed
    assert "outside allowed list" in result.message
    assert "without approval" in result.message


def test_combined_only_allowed_fails_patterns_pass() -> None:
    result = check_tool_policy(
        resp(["exec_shell"]),
        ["search_docs"],
        [],
        ["drop_*"],
    )
    assert not result.passed
    assert "outside allowed list" in result.message
    assert "drop_" not in result.message


def test_combined_mapping_missing_specific_suggestion() -> None:
    """When the only failure is a missing mapping, suggestion is specific."""
    result = check_tool_policy(
        resp(["send_email"], approved=None),
        [],
        ["send_email"],
        [],
    )
    assert not result.passed
    assert "approved_tools:" in result.message


def test_combined_other_failures_general_suggestion() -> None:
    """When allowed_tools also fails, suggestion is the general one."""
    result = check_tool_policy(
        resp(["exec_shell", "send_email"], approved=None),
        ["search_docs"],
        ["send_email"],
        [],
    )
    assert not result.passed
    assert "approval gates" in result.message


def test_fail_msg_starts_with_check_failed_header() -> None:
    result = check_tool_policy(resp(["exec_shell"]), ["search_docs"], [], [])
    assert result.message.startswith("Check failed: tool_policy")


def test_pass_msg_contains_passed() -> None:
    result = check_tool_policy(
        resp(["search_docs"]), ["search_docs", "summarize"], [], []
    )
    assert result.passed
    assert "passed" in result.message.lower()


def test_approved_tools_section_appears_when_configured() -> None:
    result = check_tool_policy(
        resp(["send_email"], approved=[]),
        [],
        ["send_email"],
        [],
    )
    assert "Approved tools:" in result.message


def test_approved_tools_section_absent_when_not_configured() -> None:
    """When approved_tools is None the diagnostic must not show an empty section."""
    result = check_tool_policy(
        resp(["send_email"], approved=None),
        [],
        ["send_email"],
        [],
    )
    assert "Approved tools:" not in result.message
