"""Tests for the JUnit XML report module."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rag_agent_audit.cli import app
from rag_agent_audit.reports.junit import build_junit_report
from rag_agent_audit.result import CheckResult, TestResult

runner = CliRunner()
_EXAMPLES = Path(__file__).parent.parent / "examples"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(xml_str: str) -> ET.Element:
    """Parse XML string (with or without declaration) and return the root."""
    return ET.fromstring(xml_str.encode("utf-8"))


def _passing(name: str) -> TestResult:
    return TestResult(test_name=name, passed=True, check_results=[])


def _failing(name: str, *messages: str, check_name: str = "must_contain") -> TestResult:
    checks = [
        CheckResult(check_name=check_name, passed=False, message=msg)
        for msg in messages
    ]
    return TestResult(test_name=name, passed=False, check_results=checks)


def _error(name: str, error: str) -> TestResult:
    return TestResult(test_name=name, passed=False, check_results=[], error=error)


# ---------------------------------------------------------------------------
# Root element / counts
# ---------------------------------------------------------------------------


def test_root_tag_is_testsuite() -> None:
    root = _parse(build_junit_report("my-suite", [_passing("t1")]))
    assert root.tag == "testsuite"


def test_root_has_required_attributes() -> None:
    root = _parse(build_junit_report("my-suite", [_passing("t1"), _passing("t2")]))
    assert root.attrib["name"] == "my-suite"
    assert root.attrib["tests"] == "2"
    assert root.attrib["failures"] == "0"


def test_failure_count_reflects_failures() -> None:
    results = [_passing("ok"), _failing("bad", "missing phrase")]
    root = _parse(build_junit_report("s", results))
    assert root.attrib["failures"] == "1"
    assert root.attrib["tests"] == "2"


def test_all_failing() -> None:
    results = [_failing("a", "x"), _failing("b", "y")]
    root = _parse(build_junit_report("s", results))
    assert root.attrib["failures"] == "2"
    assert root.attrib["tests"] == "2"


# ---------------------------------------------------------------------------
# <testcase> elements
# ---------------------------------------------------------------------------


def test_testcase_count_matches_results() -> None:
    results = [_passing("t1"), _passing("t2"), _failing("t3", "oops")]
    root = _parse(build_junit_report("s", results))
    assert len(root.findall("testcase")) == 3


def test_testcase_classname_is_tool_name() -> None:
    root = _parse(build_junit_report("s", [_passing("my-test")]))
    tc = root.find("testcase")
    assert tc is not None
    assert tc.attrib["classname"] == "rag-agent-audit"


def test_testcase_name_matches_test_name() -> None:
    root = _parse(build_junit_report("s", [_passing("refund-policy")]))
    tc = root.find("testcase")
    assert tc is not None
    assert tc.attrib["name"] == "refund-policy"


def test_passing_testcase_has_no_failure_child() -> None:
    root = _parse(build_junit_report("s", [_passing("ok-test")]))
    tc = root.find("testcase")
    assert tc is not None
    assert tc.find("failure") is None


def test_failing_testcase_has_failure_child() -> None:
    root = _parse(build_junit_report("s", [_failing("bad-test", "missing word")]))
    tc = root.find("testcase")
    assert tc is not None
    failure = tc.find("failure")
    assert failure is not None


# ---------------------------------------------------------------------------
# <failure> element content
# ---------------------------------------------------------------------------


def test_failure_message_attribute_contains_check_name() -> None:
    result = _failing("t", "some detail", check_name="must_not_contain")
    root = _parse(build_junit_report("s", [result]))
    failure = root.find(".//failure")
    assert failure is not None
    assert "must_not_contain" in failure.attrib["message"]


def test_failure_text_contains_detail() -> None:
    result = _failing("t", "Answer contains prohibited strings: ['API_KEY=']")
    root = _parse(build_junit_report("s", [result]))
    failure = root.find(".//failure")
    assert failure is not None
    assert failure.text is not None
    assert "API_KEY=" in failure.text


def test_multiple_failed_checks_combined_in_one_failure() -> None:
    checks = [
        CheckResult(check_name="must_contain", passed=False, message="missing: foo"),
        CheckResult(check_name="forbidden_sources", passed=False, message="found: bar.pdf"),
    ]
    result = TestResult(test_name="multi-fail", passed=False, check_results=checks)
    root = _parse(build_junit_report("s", [result]))
    tc = root.find("testcase")
    assert tc is not None
    # Exactly one <failure> element even for multiple check failures
    assert len(tc.findall("failure")) == 1
    failure = tc.find("failure")
    assert failure is not None
    # Both check names appear in the message attribute
    assert "must_contain" in failure.attrib["message"]
    assert "forbidden_sources" in failure.attrib["message"]
    # Both details appear in the text body
    assert failure.text is not None
    assert "missing: foo" in failure.text
    assert "found: bar.pdf" in failure.text


def test_adapter_error_produces_failure() -> None:
    result = _error("err-test", "Connection timed out")
    root = _parse(build_junit_report("s", [result]))
    failure = root.find(".//failure")
    assert failure is not None
    assert "Adapter error" in failure.attrib["message"]
    assert failure.text is not None
    assert "Connection timed out" in failure.text


# ---------------------------------------------------------------------------
# XML escaping
# ---------------------------------------------------------------------------


def test_ampersand_in_suite_name_is_escaped() -> None:
    xml_str = build_junit_report("suite & audit", [_passing("t")])
    # If this does not raise, ElementTree parsed the escaping correctly
    root = _parse(xml_str)
    assert root.attrib["name"] == "suite & audit"


def test_lt_gt_in_failure_message_are_escaped() -> None:
    result = _failing("t", "Found: <script>alert('xss')</script>")
    xml_str = build_junit_report("s", [result])
    root = _parse(xml_str)
    failure = root.find(".//failure")
    assert failure is not None
    assert failure.text is not None
    assert "<script>" in failure.text  # round-trip through escape/unescape


def test_ampersand_in_failure_detail_is_escaped() -> None:
    result = _failing("t", "missing: foo & bar")
    xml_str = build_junit_report("s", [result])
    root = _parse(xml_str)
    failure = root.find(".//failure")
    assert failure is not None
    assert failure.text is not None
    assert "foo & bar" in failure.text


def test_xml_declaration_present() -> None:
    xml_str = build_junit_report("s", [_passing("t")])
    assert xml_str.startswith("<?xml")


def test_output_is_parseable_by_elementtree() -> None:
    """Round-trip: build → parse should not raise."""
    results = [
        _passing("pass-1"),
        _failing("fail-1", "bad output"),
        _error("err-1", "timeout"),
    ]
    xml_str = build_junit_report("complex-suite", results)
    root = _parse(xml_str)  # should not raise
    assert root.tag == "testsuite"


# ---------------------------------------------------------------------------
# CLI integration — write JUnit to file
# ---------------------------------------------------------------------------


def test_cli_junit_to_file(tmp_path: Path) -> None:
    output = tmp_path / "results.xml"
    result = runner.invoke(
        app,
        [
            "run", str(_EXAMPLES / "basic" / "audit.yaml"),
            "--format", "junit",
            "--output", str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()

    root = ET.parse(str(output)).getroot()
    assert root.tag == "testsuite"
    assert root.attrib["name"] == "basic-rag-security-audit"
    assert root.attrib["tests"] == "4"
    assert root.attrib["failures"] == "0"
    assert len(root.findall("testcase")) == 4


def test_cli_junit_failing_suite_to_file(tmp_path: Path) -> None:
    """Failing suite exits 1 and still writes valid XML with failure elements."""
    config = tmp_path / "audit.yaml"
    config.write_text(
        "suite: fail-suite\nmode: mock\ntests:\n"
        "  - name: bad-test\n    question: q\n"
        "    mock_response:\n      answer: wrong\n"
        "    must_contain:\n      - correct\n",
        encoding="utf-8",
    )
    output = tmp_path / "results.xml"
    result = runner.invoke(
        app, ["run", str(config), "--format", "junit", "--output", str(output)]
    )
    assert result.exit_code == 1
    assert output.exists()

    root = ET.parse(str(output)).getroot()
    assert root.attrib["failures"] == "1"
    failure = root.find(".//failure")
    assert failure is not None


def test_cli_junit_to_stdout(tmp_path: Path) -> None:
    """junit format without --output prints XML to stdout."""
    result = runner.invoke(
        app,
        ["run", str(_EXAMPLES / "basic" / "audit.yaml"), "--format", "junit"],
    )
    assert result.exit_code == 0
    assert "<?xml" in result.output
    assert "testsuite" in result.output


@pytest.mark.parametrize("fmt", ["json", "markdown"])
def test_existing_formats_still_work(fmt: str, tmp_path: Path) -> None:
    output = tmp_path / f"report.{fmt}"
    result = runner.invoke(
        app,
        [
            "run",
            str(_EXAMPLES / "basic" / "audit.yaml"),
            "--format",
            fmt,
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()
