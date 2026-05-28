"""Markdown report — suitable for GitHub Actions job summaries."""

from __future__ import annotations

from rag_agent_audit.result import TestResult


def build_markdown_report(suite_name: str, results: list[TestResult]) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    lines: list[str] = [
        f"# RAG Agent Audit — {suite_name}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Total  | {total} |",
        f"| Passed | {passed} |",
        f"| Failed | {failed} |",
        "",
    ]

    if failed == 0:
        lines.append("✅ All tests passed.")
        return "\n".join(lines)

    lines += ["## Failed Tests", ""]

    for result in results:
        if result.error:
            lines += [
                f"### ❌ {result.test_name}",
                "",
                f"**Adapter error:** {result.error}",
                "",
            ]
            continue

        failed_checks = [cr for cr in result.check_results if not cr.passed]
        if not failed_checks:
            continue

        lines += [f"### ❌ {result.test_name}", ""]
        for cr in failed_checks:
            lines += [
                f"**Check:** `{cr.check_name}`  ",
                f"**Detail:** {cr.message}",
                "",
            ]

    return "\n".join(lines)
