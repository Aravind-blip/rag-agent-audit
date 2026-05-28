"""
HTTP adapter.

Posts test questions to a real RAG/agent endpoint and normalizes
the response using JSONPath mapping.
"""

from __future__ import annotations

import httpx

from rag_agent_audit.adapters.base import BaseAdapter
from rag_agent_audit.config import AuditTestCase, RequestConfig, ResponseMapping, SuiteDefaults
from rag_agent_audit.normalizer import NormalizedResponse


class HTTPAdapter(BaseAdapter):
    def __init__(
        self,
        endpoint: str,
        request_config: RequestConfig,
        mapping: ResponseMapping,
        defaults: SuiteDefaults,
    ) -> None:
        self._endpoint = endpoint
        self._request_config = request_config
        self._mapping = mapping
        self._defaults = defaults

    def send_request(self, test: AuditTestCase) -> NormalizedResponse:
        headers = {**self._request_config.headers, **test.headers}
        payload = {"question": test.question}

        last_exc: Exception | None = None
        attempts = self._defaults.retries + 1

        for _ in range(attempts):
            try:
                resp = httpx.request(
                    method=self._request_config.method,
                    url=self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._defaults.timeout_seconds,
                )
                resp.raise_for_status()
                raw = resp.json()
                return self._normalize(raw, self._mapping)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_exc = e

        raise RuntimeError(
            f"HTTP request failed for test '{test.name}' after {attempts} attempt(s): {last_exc}"
        )
