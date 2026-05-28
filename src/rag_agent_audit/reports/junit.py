"""JUnit XML report — understood by GitHub Actions, Jenkins, GitLab, CircleCI."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from rag_agent_audit.result import TestResult


def build_junit_report(suite_name: str, results: list[TestResult]) -> str:
    """Return a JUnit XML string for *results*.

    Each TestResult becomes one <testcase>. Failing tests get a single
    <failure> element whose message attribute is a short summary and whose
    text body contains the full per-check details.
    """
    total = len(results)
    failure_count = sum(1 for r in results if not r.passed)

    suite_el = ET.Element(
        "testsuite",
        attrib={
            "name": suite_name,
            "tests": str(total),
            "failures": str(failure_count),
        },
    )

    for result in results:
        tc_el = ET.SubElement(
            suite_el,
            "testcase",
            attrib={"classname": "rag-agent-audit", "name": result.test_name},
        )
        if not result.passed:
            _attach_failure(tc_el, result)

    ET.indent(suite_el, space="  ")
    # encoding="unicode" is the only overload typed to return str in typeshed.
    # We prepend the declaration ourselves so consumers see a proper header.
    xml_body: str = ET.tostring(suite_el, encoding="unicode")
    return f"<?xml version='1.0' encoding='utf-8'?>\n{xml_body}"


def _attach_failure(tc_el: ET.Element, result: TestResult) -> None:
    """Attach a <failure> child to *tc_el* describing why *result* failed."""
    if result.error:
        short_msg = f"Adapter error: {result.error}"
        detail = short_msg
    else:
        failed_checks = [cr for cr in result.check_results if not cr.passed]
        if failed_checks:
            short_msg = "; ".join(cr.check_name for cr in failed_checks)
            detail = "\n".join(
                f"{cr.check_name}: {cr.message}" for cr in failed_checks
            )
        else:
            short_msg = "Test failed"
            detail = "Test marked as failed with no check detail."

    failure_el = ET.SubElement(tc_el, "failure", attrib={"message": short_msg})
    failure_el.text = f"\n{detail}\n"
