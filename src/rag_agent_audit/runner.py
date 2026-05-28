"""
Test runner.

Iterates test cases, dispatches to the right adapter, runs checks,
and collects TestResult objects.
"""

from __future__ import annotations

from rag_agent_audit.adapters.base import BaseAdapter
from rag_agent_audit.checks import run_checks
from rag_agent_audit.config import AuditSuite
from rag_agent_audit.result import TestResult


def run_suite(suite: AuditSuite, adapter: BaseAdapter) -> list[TestResult]:
    results: list[TestResult] = []

    for test in suite.tests:
        try:
            response = adapter.send_request(test)
        except Exception as e:
            results.append(
                TestResult(
                    test_name=test.name,
                    passed=False,
                    check_results=[],
                    error=str(e),
                )
            )
            continue

        check_results = run_checks(test, response, suite.fallback_patterns)
        passed = all(cr.passed for cr in check_results)
        results.append(TestResult(test_name=test.name, passed=passed, check_results=check_results))

    return results
