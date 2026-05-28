"""
Small formatting helpers for audit failure messages.

Used internally by check modules to produce actionable, readable output.
Not part of the public API.
"""

from __future__ import annotations


def preview_text(text: str, limit: int = 300) -> str:
    """Return a whitespace-normalised, length-capped preview of *text*.

    - Collapses runs of whitespace to a single space.
    - Appends "..." when truncated.
    - Returns the literal string "<empty>" when *text* is blank.
    """
    if not text or not text.strip():
        return "<empty>"
    normalized = " ".join(text.split())
    if len(normalized) > limit:
        return normalized[:limit] + "..."
    return normalized


def format_list(items: list[str]) -> str:
    """Format *items* as an indented bulleted list.

    Returns ``  (none)`` for empty lists so callers never emit blank sections.
    """
    if not items:
        return "  (none)"
    return "\n".join(f"  - {item}" for item in items)
