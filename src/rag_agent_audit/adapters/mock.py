"""
Mock adapter.

Serves inline mock_response values from the test case config.
No network calls. Works offline. Essential for CI and contributor onboarding.
"""

from __future__ import annotations

from rag_agent_audit.adapters.base import BaseAdapter
from rag_agent_audit.config import AuditTestCase, ResponseMapping
from rag_agent_audit.normalizer import NormalizedResponse


class MockAdapter(BaseAdapter):
    def __init__(self, mapping: ResponseMapping) -> None:
        self._mapping = mapping

    def send_request(self, test: AuditTestCase) -> NormalizedResponse:
        if test.mock_response is None:
            raise ValueError(
                f"Test '{test.name}' has no mock_response. "
                "Set mode: mock and add a mock_response block."
            )
        return self._normalize(test.mock_response, self._mapping)
