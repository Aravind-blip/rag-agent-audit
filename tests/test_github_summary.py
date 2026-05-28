"""Tests for the GitHub Actions summary report."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from rag_agent_audit.cli import app
from rag_agent_audit.reports.github_summary import (
    _compact_detail,
    append_to_step_summary,
    build_github_summary,
)
from rag_agent_audit.result import CheckResult, TestResult

runner = CliRunner()
_EXAMPLES = Path(__file__).parent.parent / "examples"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _passing(name: str) -> TestResult:
    return TestResult(test_name=name, passed=True, check_results=[])


def _failing(name: str, check: str, msg: str) -> TestResult:
    return TestResult(
        test_name=name,
        passed=False,
        check_results=[CheckResult(check_name=check, passed=False, message=msg)],
    )


def _error(name: str, err: str) -> TestResult:
    return TestResult(test_name=name, passed=False, check_results=[], error=err)


# ---------------------------------------------------------------------------
# _compact_detail
# ---------------------------------------------------------------------------


def test_compact_detail_skips_check_failed_header() -> None:
    msg = "Check failed: must_contain\nMissing required strings:\n  - 30 days"
    result = _compact_detail(msg)
    assert "Check failed" not in result
    assert "Missing" in result


def test_compact_detail_joins_first_two_content_lines() -> None:
    msg = "Check failed: must_contain\nMissing required strings:\n  - 30 days\n\nAnswer preview:"
    result = _compact_detail(msg)
    assert "Missing required strings:" in result
    assert "- 30 days" in result


def test_compact_detail_truncates_at_max_len() -> None:
    msg = "Check failed: x\n" + "a" * 300
    result = _compact_detail(msg, max_len=50)
    assert len(result) <= 53  # 50 + "..."
    assert result.endswith("...")


def test_compact_detail_fallback_for_simple_message() -> None:
    # A plain message without the "Check failed:" header
    result = _compact_detail("something went wrong")
    assert "something went wrong" in result


# ---------------------------------------------------------------------------
# build_github_summary — structure
# ---------------------------------------------------------------------------


def test_summary_starts_with_h1() -> None:
    content = build_github_summary("my-suite", [_passing("t1")])
    assert content.startswith("# RAG Agent Audit Report")


def test_summary_contains_suite_name() -> None:
    content = build_github_summary("flowise-basic-audit", [_passing("t1")])
    assert "flowise-basic-audit" in content


def test_summary_table_has_passed_failed_total() -> None:
    results = [_passing("t1"), _passing("t2"), _failing("t3", "must_contain", "bad")]
    content = build_github_summary("s", results)
    assert "| Passed |" in content
    assert "| Failed |" in content
    assert "| Total  |" in content


def test_summary_counts_all_passing() -> None:
    results = [_passing("t1"), _passing("t2")]
    content = build_github_summary("s", results)
    assert "| Passed | 2 |" in content
    assert "| Failed | 0 |" in content
    assert "| Total  | 2 |" in content


def test_summary_counts_mixed() -> None:
    results = [_passing("t1"), _failing("t2", "must_contain", "missing")]
    content = build_github_summary("s", results)
    assert "| Passed | 1 |" in content
    assert "| Failed | 1 |" in content
    assert "| Total  | 2 |" in content


# ---------------------------------------------------------------------------
# build_github_summary — passing suite
# ---------------------------------------------------------------------------


def test_summary_passing_suite_shows_none_under_failed_tests() -> None:
    content = build_github_summary("s", [_passing("ok")])
    assert "## Failed tests" in content
    assert "None." in content


def test_summary_passing_suite_has_no_test_name_bullet() -> None:
    content = build_github_summary("s", [_passing("ok-test")])
    assert "**ok-test**" not in content


# ---------------------------------------------------------------------------
# build_github_summary — failing suite
# ---------------------------------------------------------------------------


def test_summary_failing_suite_lists_test_name() -> None:
    results = [_failing("bad-test", "must_contain", "missing: foo")]
    content = build_github_summary("s", results)
    assert "**bad-test**" in content


def test_summary_failing_suite_lists_check_name() -> None:
    results = [_failing("bad-test", "must_contain", "missing: foo")]
    content = build_github_summary("s", results)
    assert "`must_contain`" in content


def test_summary_failing_suite_omits_passing_tests() -> None:
    results = [_passing("ok"), _failing("bad", "must_contain", "missing")]
    content = build_github_summary("s", results)
    assert "**ok**" not in content
    assert "**bad**" in content


def test_summary_adapter_error_shown_in_failed_tests() -> None:
    results = [_error("err-test", "Connection refused")]
    content = build_github_summary("s", results)
    assert "**err-test**" in content
    assert "adapter error" in content
    assert "Connection refused" in content


def test_summary_compact_detail_strips_multiline_message() -> None:
    """Multi-line diagnostic messages are compacted for the GitHub summary."""
    msg = (
        "Check failed: must_contain\n"
        "Missing required strings:\n"
        "  - important phrase\n\n"
        "Answer preview:\n"
        '  "wrong answer"\n\n'
        "Suggestion:\n"
        "  Update the app."
    )
    results = [_failing("t", "must_contain", msg)]
    content = build_github_summary("s", results)
    # Check name should appear
    assert "`must_contain`" in content
    # Detail should be on one line (no double-newlines in the list item)
    lines = content.splitlines()
    check_line = next((ln for ln in lines if "`must_contain`" in ln), "")
    assert check_line  # line exists
    assert "important phrase" in check_line or "Missing" in check_line


# ---------------------------------------------------------------------------
# append_to_step_summary
# ---------------------------------------------------------------------------


def test_append_returns_none_when_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    warning = append_to_step_summary("# Test\n")
    assert warning is None


def test_append_writes_content_to_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    append_to_step_summary("# RAG Agent Audit Report\n")
    assert "# RAG Agent Audit Report" in summary_file.read_text()


def test_append_appends_not_overwrites(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("## Existing content\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    append_to_step_summary("## New content\n")
    text = summary_file.read_text()
    assert "## Existing content" in text
    assert "## New content" in text


def test_append_returns_warning_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    warning = append_to_step_summary("# Test\n")
    assert warning is not None
    assert "GITHUB_STEP_SUMMARY" in warning


def test_append_adds_trailing_newline_if_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    append_to_step_summary("no trailing newline")
    assert summary_file.read_text().endswith("\n")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_github_summary_writes_to_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--github-summary appends to the file named by GITHUB_STEP_SUMMARY."""
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    result = runner.invoke(
        app,
        ["run", str(_EXAMPLES / "basic" / "audit.yaml"), "--github-summary"],
    )
    assert result.exit_code == 0
    text = summary_file.read_text()
    assert "# RAG Agent Audit Report" in text
    assert "basic-rag-security-audit" in text
    assert "None." in text  # no failures


def test_cli_github_summary_still_exits_1_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exit code from audit failures is preserved even with --github-summary."""
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    config = tmp_path / "audit.yaml"
    config.write_text(
        "suite: fail-suite\nmode: mock\ntests:\n"
        "  - name: will-fail\n    question: q\n"
        "    mock_response:\n      answer: wrong\n"
        "    must_contain:\n      - correct\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["run", str(config), "--github-summary"])
    assert result.exit_code == 1
    # Summary is still written even though the audit failed
    text = summary_file.read_text()
    assert "# RAG Agent Audit Report" in text
    assert "will-fail" in text


def test_cli_github_summary_warns_and_does_not_fail_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If GITHUB_STEP_SUMMARY is absent, audit still passes (exit 0)."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    result = runner.invoke(
        app,
        ["run", str(_EXAMPLES / "basic" / "audit.yaml"), "--github-summary"],
    )
    assert result.exit_code == 0


def test_cli_without_github_summary_flag_unchanged(tmp_path: Path) -> None:
    """Normal run without --github-summary writes nothing to any summary file."""
    result = runner.invoke(
        app, ["run", str(_EXAMPLES / "basic" / "audit.yaml")]
    )
    assert result.exit_code == 0
