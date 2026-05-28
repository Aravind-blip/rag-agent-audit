"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from rag_agent_audit.normalizer import NormalizedResponse


@pytest.fixture
def response_with_citations() -> NormalizedResponse:
    return NormalizedResponse(
        answer="Refunds are available within 30 days.",
        citations=["org_a_refund_policy.pdf"],
        retrieved_sources=["org_a_refund_policy.pdf"],
        tool_calls=[],
    )


@pytest.fixture
def empty_response() -> NormalizedResponse:
    return NormalizedResponse(
        answer="I could not find that information in the available sources.",
        citations=[],
        retrieved_sources=[],
        tool_calls=[],
    )


@pytest.fixture
def response_with_forbidden_citation() -> NormalizedResponse:
    return NormalizedResponse(
        answer="Here is the compensation policy.",
        citations=["org_b_compensation_policy.pdf"],
        retrieved_sources=["org_b_compensation_policy.pdf"],
        tool_calls=[],
    )
