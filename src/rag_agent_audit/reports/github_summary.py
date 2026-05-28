"""
GitHub Actions step-summary support.

build_github_summary  — pure function; returns a Markdown string.
append_to_step_summary — side-effect; appends to $GITHUB_STEP_SUMMARY.
"""

from __future__ import annotations

import os

from rag_agent_audit.result import TestResult


def _compact_detail(message: str, max_len: int = 200) -> str:
    """Return a single-line summary of a (potentially multi-line) failure message.

    Skips the "Check failed: …" header line and blank lines, then joins the
    first two remaining content lines.  Truncates at *max_len* characters.
    """
    content_lines = [
        line.strip()
        for line in message.splitlines()
        if line.strip() and not line.strip().startswith("Check failed:")
    ]
    detail = " ".join(content_lines[:2])
    if len(detail) > max_len:
        return detail[:max_len] + "..."
    return detail or message.strip()


def build_github_summary(suite_name: str, results: list[TestResult]) -> str:
    """Return a Markdown summary suitable for $GITHUB_STEP_SUMMARY."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    lines: list[str] = [
        "# RAG Agent Audit Report",
        "",
        f"Suite: {suite_name}",
        "",
        "| Metric | Value |",
        "| ------ | ----: |",
        f"| Passed | {passed} |",
        f"| Failed | {failed} |",
        f"| Total  | {total} |",
        "",
        "## Failed tests",
        "",
    ]

    if failed == 0:
        lines.append("None.")
        lines.append("")
        return "\n".join(lines)

    for result in results:
        if result.passed:
            continue

        lines.append(f"- **{result.test_name}**")

        if result.error:
            lines.append(f"  - adapter error: {result.error}")
            continue

        for cr in result.check_results:
            if not cr.passed:
                detail = _compact_detail(cr.message)
                lines.append(f"  - `{cr.check_name}`: {detail}")

    lines.append("")
    return "\n".join(lines)


def append_to_step_summary(content: str) -> str | None:
    """Append *content* to the file named by $GITHUB_STEP_SUMMARY.

    Returns ``None`` on success.
    Returns a warning string if the env var is unset or the write fails;
    callers should print the warning but must not treat it as an audit failure.
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return (
            "--github-summary was passed but GITHUB_STEP_SUMMARY is not set; "
            "summary not written."
        )
    try:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(content)
            if not content.endswith("\n"):
                fh.write("\n")
    except OSError as exc:
        return f"Could not write to GITHUB_STEP_SUMMARY ({summary_path}): {exc}"
    return None
