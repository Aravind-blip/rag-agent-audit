"""
String matching utilities used by the check engine.

All matching is case-insensitive substring matching by default.
Exact matching is used for source identifiers.
"""

from __future__ import annotations


def contains_any(text: str, patterns: list[str]) -> list[str]:
    """Return the subset of patterns found in text (case-insensitive)."""
    text_lower = text.lower()
    return [p for p in patterns if p.lower() in text_lower]


def sources_overlap(actual: list[str], forbidden: list[str]) -> list[str]:
    """Return forbidden sources that appear in actual (case-insensitive exact match)."""
    actual_lower = {s.lower() for s in actual}
    return [f for f in forbidden if f.lower() in actual_lower]


def sources_missing(actual: list[str], expected: list[str]) -> list[str]:
    """Return expected sources not found in actual (case-insensitive exact match)."""
    actual_lower = {s.lower() for s in actual}
    return [e for e in expected if e.lower() not in actual_lower]
