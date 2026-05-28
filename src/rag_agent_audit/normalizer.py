"""
Normalized response model.

Every adapter (mock, HTTP, future LangChain/MCP) produces a NormalizedResponse.
Check engine only operates on this model, never on raw response dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedResponse:
    """Canonical representation of an app response.

    Fields:
        answer: The text answer from the RAG system.
        citations: Source identifiers cited in the answer (e.g. filenames).
        retrieved_sources: Sources the retriever pulled, even if not cited.
            Requires debug output from the app; empty list if unavailable.
        tool_calls: Names of tools called during this request.
        raw: The original response dict, preserved for debugging.
    """

    answer: str = ""
    citations: list[str] = field(default_factory=list)
    retrieved_sources: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
