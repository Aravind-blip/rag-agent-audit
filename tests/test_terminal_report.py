"""Tests for the terminal report renderer."""

from __future__ import annotations

import io

from rich.console import Console

from rag_agent_audit.reports.terminal import _compact_message, print_terminal_report
from rag_agent_audit.result import CheckResult, TestResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture(suite_name: str, results: list[TestResult]) -> str:
    """Run print_terminal_report with a captured console; return plain text."""
    buf = io.StringIO()
    # width=200 prevents wrapping; force_terminal=False (default for StringIO)
    # strips ANSI codes so assertions work on plain text.
    console = Console(file=buf, width=200)
    print_terminal_report(suite_name, results, console=console)
    return buf.getvalue()


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


_MULTILINE_MSG = (
    "Check failed: must_contain\n"
    "Missing required strings:\n"
    "  - 30 days\n"
    "\n"
    "Answer preview:\n"
    '  "wrong answer text here"\n'
    "\n"
    "Suggestion:\n"
    "  Update your response."
)


# ---------------------------------------------------------------------------
# _compact_message unit tests
# ---------------------------------------------------------------------------


def test_compact_message_skips_check_failed_header() -> None:
    msg = "Check failed: must_contain\nMissing required strings:\n  - 30 days"
    result = _compact_message(msg)
    assert "Check failed" not in result
    assert "Missing" in result


def test_compact_message_joins_first_two_content_lines() -> None:
    msg = "Check failed: must_contain\nMissing required strings:\n  - 30 days\n\nAnswer:"
    result = _compact_message(msg)
    assert "Missing required strings:" in result
    assert "30 days" in result


def test_compact_message_truncates_at_max_len() -> None:
    msg = "Check failed: x\n" + "a" * 200
    result = _compact_message(msg, max_len=50)
    assert len(result) <= 53  # 50 + "..."
    assert result.endswith("...")


def test_compact_message_passthrough_for_plain_message() -> None:
    result = _compact_message("something went wrong")
    assert "something went wrong" in result


def test_compact_message_strips_leading_spaces_from_lines() -> None:
    msg = "Check failed: x\n  - item one\n  - item two"
    result = _compact_message(msg)
    assert "item one" in result
    assert "item two" in result
    assert "Check failed" not in result


# ---------------------------------------------------------------------------
# print_terminal_report — passing suite
# ---------------------------------------------------------------------------


def test_passing_suite_shows_all_tests_passed() -> None:
    out = _capture("my-suite", [_passing("t1"), _passing("t2")])
    assert "All tests passed" in out


def test_passing_suite_shows_counts() -> None:
    out = _capture("s", [_passing("t1"), _passing("t2")])
    assert "Passed:" in out
    assert "2" in out


def test_passing_suite_no_details_section() -> None:
    out = _capture("s", [_passing("t1")])
    assert "Failed test details" not in out


def test_passing_suite_shows_suite_name() -> None:
    out = _capture("my-awesome-suite", [_passing("t1")])
    assert "my-awesome-suite" in out


# ---------------------------------------------------------------------------
# print_terminal_report — failing suite: compact table
# ---------------------------------------------------------------------------


def test_failing_suite_shows_failed_count() -> None:
    out = _capture("s", [_failing("bad-test", "must_contain", _MULTILINE_MSG)])
    assert "Failed:" in out


def test_failing_suite_table_contains_test_name() -> None:
    out = _capture("s", [_failing("bad-test", "must_contain", _MULTILINE_MSG)])
    assert "bad-test" in out


def test_failing_suite_table_contains_check_name() -> None:
    out = _capture("s", [_failing("bad-test", "must_contain", _MULTILINE_MSG)])
    assert "must_contain" in out


def test_failing_suite_table_detail_is_compact() -> None:
    """The table's Detail column must NOT contain the full multi-line message."""
    out = _capture("s", [_failing("bad-test", "must_contain", _MULTILINE_MSG)])
    # The "Answer preview:" section header should only appear in the details block,
    # not be what the compact summary shows.  Check that the raw header line is
    # not directly in the first portion of output (before the details section).
    before_details = out.split("Failed test details")[0] if "Failed test details" in out else out
    # Full raw multi-line body should not be crammed into the table section.
    assert "Answer preview:" not in before_details


def test_failing_suite_table_compact_detail_has_first_content_line() -> None:
    out = _capture("s", [_failing("t", "must_contain", _MULTILINE_MSG)])
    before_details = out.split("Failed test details")[0]
    # "Missing required strings:" is the first content line after the header.
    assert "Missing required strings:" in before_details


# ---------------------------------------------------------------------------
# print_terminal_report — failing suite: full diagnostics section
# ---------------------------------------------------------------------------


def test_failing_suite_has_details_section_header() -> None:
    out = _capture("s", [_failing("t", "must_contain", _MULTILINE_MSG)])
    assert "Failed test details" in out


def test_failing_suite_details_contain_test_name() -> None:
    out = _capture("s", [_failing("my-test", "must_contain", _MULTILINE_MSG)])
    after_details = out.split("Failed test details")[1]
    assert "my-test" in after_details


def test_failing_suite_details_contain_check_name() -> None:
    out = _capture("s", [_failing("t", "my_check", _MULTILINE_MSG)])
    after_details = out.split("Failed test details")[1]
    assert "my_check" in after_details


def test_failing_suite_details_contain_full_message() -> None:
    out = _capture("s", [_failing("t", "must_contain", _MULTILINE_MSG)])
    after_details = out.split("Failed test details")[1]
    assert "Answer preview:" in after_details
    assert "Suggestion:" in after_details
    assert "30 days" in after_details


def test_failing_suite_details_contain_check_failed_header() -> None:
    """The "Check failed:" header stripped from the table should appear in details."""
    out = _capture("s", [_failing("t", "must_contain", _MULTILINE_MSG)])
    after_details = out.split("Failed test details")[1]
    assert "Check failed: must_contain" in after_details


def test_failing_suite_passing_tests_not_in_details() -> None:
    results = [_passing("ok-test"), _failing("bad-test", "must_contain", _MULTILINE_MSG)]
    out = _capture("s", results)
    after_details = out.split("Failed test details")[1]
    assert "ok-test" not in after_details
    assert "bad-test" in after_details


def test_multiple_failed_tests_all_appear_in_details() -> None:
    results = [
        _failing("test-a", "must_contain", _MULTILINE_MSG),
        _failing("test-b", "forbidden_sources", "Check failed: forbidden_sources\nBad source."),
    ]
    out = _capture("s", results)
    after_details = out.split("Failed test details")[1]
    assert "test-a" in after_details
    assert "test-b" in after_details


def test_multiple_failed_checks_same_test_all_in_details() -> None:
    result = TestResult(
        test_name="multi-check-fail",
        passed=False,
        check_results=[
            CheckResult(
                check_name="must_contain",
                passed=False,
                message="Check failed: must_contain\nLine A",
            ),
            CheckResult(
                check_name="forbidden_sources",
                passed=False,
                message="Check failed: forbidden_sources\nLine B",
            ),
        ],
    )
    out = _capture("s", [result])
    after_details = out.split("Failed test details")[1]
    assert "must_contain" in after_details
    assert "forbidden_sources" in after_details
    assert "Line A" in after_details
    assert "Line B" in after_details


# ---------------------------------------------------------------------------
# print_terminal_report — adapter errors
# ---------------------------------------------------------------------------


def test_adapter_error_appears_in_table() -> None:
    out = _capture("s", [_error("err-test", "Connection refused")])
    assert "err-test" in out
    assert "adapter" in out


def test_adapter_error_appears_in_details() -> None:
    out = _capture("s", [_error("err-test", "Connection refused")])
    after_details = out.split("Failed test details")[1]
    assert "err-test" in after_details
    assert "Connection refused" in after_details


def test_adapter_error_shows_adapter_error_label_in_details() -> None:
    out = _capture("s", [_error("err-test", "Timeout")])
    after_details = out.split("Failed test details")[1]
    assert "adapter error" in after_details
