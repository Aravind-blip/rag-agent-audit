"""
MCP-style agent tool policy check.

check_tool_policy: Enforces three complementary sub-rules in a single check:

  1. allowed_tools       — fails if any called tool is not in the allowlist.
  2. forbidden_tool_patterns — fails if any called tool matches an fnmatch glob.
  3. required_approval_tools — fails if a tool requiring approval was called
                               without appearing in the response's approved_tools
                               list; also fails if the approved_tools mapping is
                               not configured on the suite.

All three sub-rules are independent.  A single check result is returned; its
message consolidates all failing sub-rules so the developer sees every problem
in one place.

Does not interact with live MCP servers, MCP protocol clients, or any network
resources.
"""

from __future__ import annotations

import fnmatch

from rag_agent_audit.checks.diagnostics import format_list
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult

_CHECK_NAME = "tool_policy"


def check_tool_policy(
    response: NormalizedResponse,
    allowed_tools: list[str],
    required_approval_tools: list[str],
    forbidden_tool_patterns: list[str],
) -> CheckResult:
    """Enforce agent tool policy across three independent sub-rules.

    Parameters
    ----------
    response:
        Normalized response from the adapter.
    allowed_tools:
        Explicit allowlist of permitted tool names.  When non-empty, any
        ``tool_call`` not in this list causes a failure.  Empty list means
        the sub-rule is inactive (all tools implicitly allowed).
    required_approval_tools:
        Tools that must be explicitly approved before use.  When non-empty,
        any tool in this list that appears in ``tool_calls`` must also appear
        in ``response.approved_tools``.  Requires ``response_mapping.approved_tools``
        to be configured; fails with a configuration error otherwise.
    forbidden_tool_patterns:
        fnmatch-style glob patterns.  Any ``tool_call`` matching at least one
        pattern causes a failure.  Empty list means the sub-rule is inactive.
    """
    if not allowed_tools and not required_approval_tools and not forbidden_tool_patterns:
        return CheckResult(_CHECK_NAME, True, "No tool policy defined; skipped.")

    failure_sections: list[str] = []
    mapping_missing = False

    # ── Sub-rule 1: allowed_tools ───────────────────────────────────────────
    if allowed_tools:
        disallowed = [t for t in response.tool_calls if t not in allowed_tools]
        if disallowed:
            failure_sections.append(
                "Tools called outside allowed list:\n"
                + format_list(disallowed)
                + "\n\nAllowed tools:\n"
                + format_list(allowed_tools)
            )

    # ── Sub-rule 2: forbidden_tool_patterns ─────────────────────────────────
    if forbidden_tool_patterns:
        seen_matched: dict[str, None] = {}
        for tool in response.tool_calls:
            for pattern in forbidden_tool_patterns:
                if fnmatch.fnmatch(tool, pattern):
                    seen_matched[tool] = None
                    break
        matched = list(seen_matched)
        if matched:
            failure_sections.append(
                "Tools matched forbidden patterns:\n"
                + format_list(matched)
                + "\n\nForbidden patterns:\n"
                + format_list(forbidden_tool_patterns)
            )

    # ── Sub-rule 3: required_approval_tools ─────────────────────────────────
    if required_approval_tools:
        if response.approved_tools is None:
            mapping_missing = True
            failure_sections.append(
                "required_approval_tools is set but approved_tools is not mapped "
                "in response_mapping."
            )
        else:
            unapproved = [
                t
                for t in required_approval_tools
                if t in response.tool_calls and t not in response.approved_tools
            ]
            if unapproved:
                failure_sections.append(
                    "Tools requiring approval were called without approval:\n"
                    + format_list(unapproved)
                    + "\n\nRequired approval tools:\n"
                    + format_list(required_approval_tools)
                )

    if not failure_sections:
        return CheckResult(_CHECK_NAME, True, "Tool policy check passed.")

    # ── Build diagnostic ────────────────────────────────────────────────────
    parts: list[str] = [f"Check failed: {_CHECK_NAME}"]

    for section in failure_sections:
        parts.append("")
        parts.append(section)

    parts.append("")
    parts.append("Actual tool calls:")
    parts.append(format_list(response.tool_calls))

    if response.approved_tools is not None:
        parts.append("")
        parts.append("Approved tools:")
        parts.append(format_list(response.approved_tools))

    parts.append("")
    if mapping_missing and len(failure_sections) == 1:
        parts.append(
            "Suggestion:\n"
            "  Add approved_tools: <jsonpath> to response_mapping in your suite config."
        )
    else:
        parts.append(
            "Suggestion:\n"
            "  Check agent tool policy, approval gates, or tool permissions."
        )

    return CheckResult(_CHECK_NAME, False, "\n".join(parts))
