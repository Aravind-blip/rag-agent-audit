"""Base adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from rag_agent_audit.config import AuditTestCase, ResponseMapping
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.utils import jsonpath


class BaseAdapter(ABC):
    """All adapters must implement send_request."""

    @abstractmethod
    def send_request(self, test: AuditTestCase) -> NormalizedResponse:
        ...

    def _normalize(self, raw: dict[str, Any], mapping: ResponseMapping) -> NormalizedResponse:
        """Convert a raw response dict to NormalizedResponse using JSONPath mapping."""
        return NormalizedResponse(
            answer=jsonpath.extract_scalar(mapping.answer, raw),
            citations=[str(v) for v in jsonpath.extract(mapping.citations, raw)],
            retrieved_sources=[str(v) for v in jsonpath.extract(mapping.retrieved_sources, raw)],
            tool_calls=[str(v) for v in jsonpath.extract(mapping.tool_calls, raw)],
            raw=raw,
        )
