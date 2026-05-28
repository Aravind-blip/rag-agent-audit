"""Check result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class CheckResult:
    __test__: ClassVar[bool] = False

    check_name: str
    passed: bool
    message: str


@dataclass
class TestResult:
    __test__: ClassVar[bool] = False

    test_name: str
    passed: bool
    check_results: list[CheckResult]
    error: str | None = None  # set if the adapter raised before checks ran