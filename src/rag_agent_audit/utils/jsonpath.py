"""
JSONPath extraction utility.

Wraps jsonpath-ng to extract values from response dicts using
the JSONPath expressions defined in ResponseMapping.
"""

from __future__ import annotations

from typing import Any

from jsonpath_ng import parse  # type: ignore[import-untyped]
from jsonpath_ng.exceptions import JsonPathParserError  # type: ignore[import-untyped]


def extract(expression: str, data: dict[str, Any]) -> list[Any]:
    """Extract all values matching a JSONPath expression from data.

    Returns an empty list if nothing matches or the expression is blank.
    Raises ValueError for invalid JSONPath syntax so config errors are
    caught early.
    """
    if not expression or not expression.strip():
        return []

    try:
        parsed = parse(expression)
    except JsonPathParserError as e:
        raise ValueError(f"Invalid JSONPath expression '{expression}': {e}") from e

    return [match.value for match in parsed.find(data)]


def extract_scalar(expression: str, data: dict[str, Any]) -> str:
    """Extract the first matching value as a string, or empty string."""
    results = extract(expression, data)
    if not results:
        return ""
    val = results[0]
    return str(val) if val is not None else ""
