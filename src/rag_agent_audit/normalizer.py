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
        approved_tools: Tools that were explicitly approved (e.g. via a human
            approval gate or policy engine).  ``None`` means the
            ``approved_tools`` JSONPath mapping is not configured on the suite;
            an empty list means the mapping is configured but no approvals were
            present in this response.
        raw: The original response dict, preserved for debugging.
    """

    answer: str = ""
    citations: list[str] = field(default_factory=list)
    retrieved_sources: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    approved_tools: list[str] | None = None
    raw: dict[str, Any] = field(default_factory=dict)
