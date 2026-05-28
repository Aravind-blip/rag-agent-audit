"""Tests for response normalizer and JSONPath extraction."""

from __future__ import annotations

from rag_agent_audit.adapters.mock import MockAdapter
from rag_agent_audit.config import AuditTestCase, ResponseMapping


def make_test(mock_response: dict) -> AuditTestCase:
    return AuditTestCase(
        name="test-case",
        question="test question",
        mock_response=mock_response,
    )


def make_adapter(mapping: ResponseMapping | None = None) -> MockAdapter:
    return MockAdapter(mapping or ResponseMapping())


def test_standard_response_normalizes() -> None:
    adapter = make_adapter()
    test = make_test({
        "answer": "Refunds within 30 days.",
        "citations": [{"source": "refund.pdf"}],
        "tool_calls": [],
    })
    result = adapter.send_request(test)
    assert result.answer == "Refunds within 30 days."
    assert result.citations == ["refund.pdf"]
    assert result.tool_calls == []


def test_empty_response_normalizes() -> None:
    adapter = make_adapter()
    test = make_test({
        "answer": "I could not find that.",
        "citations": [],
    })
    result = adapter.send_request(test)
    assert result.answer == "I could not find that."
    assert result.citations == []
    assert result.retrieved_sources == []


def test_tool_calls_extracted() -> None:
    adapter = make_adapter()
    test = make_test({
        "answer": "Done.",
        "citations": [],
        "tool_calls": [{"name": "send_email"}, {"name": "fetch_data"}],
    })
    result = adapter.send_request(test)
    assert result.tool_calls == ["send_email", "fetch_data"]


def test_custom_mapping() -> None:
    mapping = ResponseMapping(
        answer="$.result.text",
        citations="$.result.sources[*].id",
    )
    adapter = make_adapter(mapping)
    test = make_test({
        "result": {
            "text": "Custom format answer.",
            "sources": [{"id": "doc1.pdf"}, {"id": "doc2.pdf"}],
        }
    })
    result = adapter.send_request(test)
    assert result.answer == "Custom format answer."
    assert result.citations == ["doc1.pdf", "doc2.pdf"]


def test_missing_fields_return_defaults() -> None:
    adapter = make_adapter()
    test = make_test({"answer": "hello"})
    result = adapter.send_request(test)
    assert result.answer == "hello"
    assert result.citations == []
    assert result.tool_calls == []


def test_missing_mock_response_raises() -> None:
    import pytest
    adapter = make_adapter()
    test = AuditTestCase(name="no-mock", question="anything?")
    with pytest.raises(ValueError, match="mock_response"):
        adapter.send_request(test)
