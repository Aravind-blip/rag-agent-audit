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
from rag_agent_audit.checks.tenant_leakage import check_tenant_leakage
from rag_agent_audit.checks.text_rules import check_must_contain, check_must_not_contain
from rag_agent_audit.checks.tool_calls import check_forbidden_tools
from rag_agent_audit.config import AuditTestCase
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult


def run_checks(
    test: AuditTestCase,
    response: NormalizedResponse,
    fallback_patterns: list[str],
) -> list[CheckResult]:
    """Run all checks defined on a test case. Returns results in a stable order."""
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
    ]
