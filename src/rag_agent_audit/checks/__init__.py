"""
Check engine entry point.

Runs all applicable checks for a test case against a normalized response
and returns a list of CheckResult objects.
"""

from __future__ import annotations

from rag_agent_audit.checks.citations import (
    check_expected_sources,
    check_forbidden_retrieved_sources,
    check_forbidden_sources,
)
from rag_agent_audit.checks.fallback import check_fallback
from rag_agent_audit.checks.known_sources import check_known_sources
from rag_agent_audit.checks.tenant_leakage import check_tenant_leakage
from rag_agent_audit.checks.text_rules import check_must_contain, check_must_not_contain
from rag_agent_audit.checks.tool_calls import check_forbidden_tools
from rag_agent_audit.checks.tool_policy import check_tool_policy
from rag_agent_audit.config import AuditTestCase
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult


def run_checks(
    test: AuditTestCase,
    response: NormalizedResponse,
    fallback_patterns: list[str],
    *,
    known_sources: frozenset[str] | None = None,
    manifest_label: str = "",
) -> list[CheckResult]:
    """Run all checks defined on a test case. Returns results in a stable order.

    known_sources
        ``None`` (default) means no manifest was configured on the suite.
        Pass a frozenset to enable the ``known_sources`` check.

    manifest_label
        Display string for the manifest path used in failure diagnostics.
    """
    return [
        check_expected_sources(response, test.expected_sources),
        check_forbidden_sources(response, test.forbidden_sources),
        check_forbidden_retrieved_sources(response, test.forbidden_retrieved_sources),
        check_must_contain(response, test.must_contain),
        check_must_not_contain(response, test.must_not_contain),
        check_fallback(response, test.should_fallback, fallback_patterns),
        check_forbidden_tools(response, test.forbidden_tools),
        check_tenant_leakage(
            response, test.allowed_source_prefixes, test.forbidden_tenant_ids
        ),
        check_known_sources(
            response, test.require_known_sources, known_sources, manifest_label
        ),
        check_tool_policy(
            response,
            test.allowed_tools,
            test.required_approval_tools,
            test.forbidden_tool_patterns,
        ),
    ]
