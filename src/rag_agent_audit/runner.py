"""
Test runner.

Iterates test cases, dispatches to the right adapter, runs checks,
and collects TestResult objects.
"""

from __future__ import annotations

from pathlib import Path

from rag_agent_audit.adapters.base import BaseAdapter
from rag_agent_audit.checks import run_checks
from rag_agent_audit.checks.known_sources import load_known_sources
from rag_agent_audit.config import AuditSuite
from rag_agent_audit.result import TestResult


def run_suite(
    suite: AuditSuite,
    adapter: BaseAdapter,
    *,
    config_dir: Path | None = None,
) -> list[TestResult]:
    """Execute all test cases in *suite* and return their results.

    config_dir
        Directory of the originating audit YAML file.  Used to resolve a
        relative ``known_sources_manifest`` path.  When ``None`` (the default)
        a relative manifest path is resolved against the current working
        directory.

    Raises
    ------
    FileNotFoundError
        If ``known_sources_manifest`` is set but the file cannot be found.
    ValueError
        If the manifest contains invalid JSON, a missing ``path`` field, or
        an invalid ``path`` value on any non-blank line.
    """
    # ── Load known sources once, before iterating tests ────────────────────
    known_sources: frozenset[str] | None = None
    manifest_label: str = ""

    if suite.known_sources_manifest:
        manifest_path = Path(suite.known_sources_manifest)
        if not manifest_path.is_absolute():
            base = config_dir if config_dir is not None else Path.cwd()
            manifest_path = base / manifest_path
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"known_sources_manifest not found: {manifest_path}"
            )
        known_sources = load_known_sources(manifest_path)
        manifest_label = suite.known_sources_manifest  # preserve original value

    # ── Run tests ───────────────────────────────────────────────────────────
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

        check_results = run_checks(
            test,
            response,
            suite.fallback_patterns,
            known_sources=known_sources,
            manifest_label=manifest_label,
        )
        passed = all(cr.passed for cr in check_results)
        results.append(TestResult(test_name=test.name, passed=passed, check_results=check_results))

    return results
