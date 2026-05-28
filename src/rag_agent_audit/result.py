"""Check result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    message: str


@dataclass
class TestResult:
    test_name: str
    passed: bool
    check_results: list[CheckResult]
    error: str | None = None  # set if the adapter raised before checks ran
