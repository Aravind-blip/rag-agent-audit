"""Tests for the inspect command core logic."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from rag_agent_audit.inspect_command import (
    _collect_fields,
    _suggest_mapping,
    _type_label,
    inspect_endpoint,
)

# ---------------------------------------------------------------------------
# _type_label
# ---------------------------------------------------------------------------


def test_type_label_string() -> None:
    assert _type_label("hello") == "string"


def test_type_label_int() -> None:
    assert _type_label(42) == "integer"


def test_type_label_float() -> None:
    assert _type_label(3.14) == "number"


def test_type_label_bool() -> None:
    assert _type_label(True) == "boolean"


def test_type_label_none() -> None:
    assert _type_label(None) == "null"


def test_type_label_list() -> None:
    assert _type_label([1, 2, 3]) == "array[3]"


def test_type_label_dict() -> None:
    assert _type_label({"a": 1}) == "object"


# ---------------------------------------------------------------------------
# _collect_fields
# ---------------------------------------------------------------------------


def test_collect_fields_flat() -> None:
    data: dict[str, Any] = {"text": "hello", "chatId": "abc"}
    fields = _collect_fields(data)
    paths = [p for p, _ in fields]
    assert "$.text" in paths
    assert "$.chatId" in paths


def test_collect_fields_nested() -> None:
    data: dict[str, Any] = {"debug": {"retrieved": []}}
    fields = _collect_fields(data)
    paths = [p for p, _ in fields]
    assert "$.debug" in paths
    assert "$.debug.retrieved" in paths


def test_collect_fields_skips_deep_nesting() -> None:
    data: dict[str, Any] = {"a": {"b": {"c": "deep"}}}
    fields = _collect_fields(data)
    paths = [p for p, _ in fields]
    assert "$.a" in paths
    assert "$.a.b" in paths
    # Three levels deep is not collected
    assert "$.a.b.c" not in paths


# ---------------------------------------------------------------------------
# _suggest_mapping
# ---------------------------------------------------------------------------


def test_suggest_answer_text() -> None:
    data: dict[str, Any] = {"text": "hello"}
    suggestions = _suggest_mapping(data)
    assert suggestions["answer"] == "$.text"


def test_suggest_answer_answer_field() -> None:
    data: dict[str, Any] = {"answer": "hello"}
    suggestions = _suggest_mapping(data)
    assert suggestions["answer"] == "$.answer"


def test_suggest_answer_message_field() -> None:
    data: dict[str, Any] = {"message": "hello"}
    suggestions = _suggest_mapping(data)
    assert suggestions["answer"] == "$.message"


def test_suggest_answer_output_field() -> None:
    data: dict[str, Any] = {"output": "hello"}
    suggestions = _suggest_mapping(data)
    assert suggestions["answer"] == "$.output"


def test_suggest_answer_text_takes_priority_over_answer() -> None:
    # text appears first in the candidate list, so it wins
    data: dict[str, Any] = {"text": "from text", "answer": "from answer"}
    suggestions = _suggest_mapping(data)
    assert suggestions["answer"] == "$.text"


def test_suggest_answer_result_text() -> None:
    data: dict[str, Any] = {"result": {"text": "hello"}}
    suggestions = _suggest_mapping(data)
    assert suggestions["answer"] == "$.result.text"


def test_suggest_citations_from_citations_key() -> None:
    data: dict[str, Any] = {"citations": [{"source": "policy.pdf"}]}
    suggestions = _suggest_mapping(data)
    assert suggestions["citations"] == "$.citations[*].source"


def test_suggest_citations_from_sources_key() -> None:
    data: dict[str, Any] = {"sources": [{"source": "policy.pdf"}]}
    suggestions = _suggest_mapping(data)
    assert suggestions["citations"] == "$.sources[*].source"


def test_citations_key_preferred_over_sources() -> None:
    data: dict[str, Any] = {
        "citations": [{"source": "a.pdf"}],
        "sources": [{"source": "b.pdf"}],
    }
    suggestions = _suggest_mapping(data)
    assert suggestions["citations"] == "$.citations[*].source"


def test_suggest_retrieved_sources() -> None:
    data: dict[str, Any] = {"debug": {"retrieved": [{"source": "policy.pdf"}]}}
    suggestions = _suggest_mapping(data)
    assert suggestions["retrieved_sources"] == "$.debug.retrieved[*].source"


def test_suggest_tool_calls() -> None:
    data: dict[str, Any] = {"tool_calls": [{"name": "search"}]}
    suggestions = _suggest_mapping(data)
    assert suggestions["tool_calls"] == "$.tool_calls[*].name"


def test_suggest_empty_list_not_suggested() -> None:
    data: dict[str, Any] = {"citations": [], "tool_calls": []}
    suggestions = _suggest_mapping(data)
    assert "citations" not in suggestions
    assert "tool_calls" not in suggestions


def test_suggest_no_fields() -> None:
    data: dict[str, Any] = {"unknown_key": 123}
    suggestions = _suggest_mapping(data)
    assert suggestions == {}


def test_suggest_full_fastapi_response() -> None:
    data: dict[str, Any] = {
        "answer": "Refunds take 30 days.",
        "citations": [{"source": "policy.pdf"}],
        "debug": {"retrieved": [{"source": "policy.pdf"}]},
        "tool_calls": [],
    }
    suggestions = _suggest_mapping(data)
    assert suggestions["answer"] == "$.answer"
    assert suggestions["citations"] == "$.citations[*].source"
    assert suggestions["retrieved_sources"] == "$.debug.retrieved[*].source"
    assert "tool_calls" not in suggestions  # empty list


# ---------------------------------------------------------------------------
# inspect_endpoint — mocked httpx.post
# ---------------------------------------------------------------------------


def _make_response(
    status: int, body: Any, content_type: str = "application/json"
) -> httpx.Response:
    if content_type == "application/json":
        content = json.dumps(body).encode()
    else:
        content = str(body).encode()
    return httpx.Response(status, content=content, headers={"content-type": content_type})


def test_flowise_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"text": "Hello!", "question": "Say hello", "chatId": "abc", "sessionId": "xyz"}
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _make_response(200, payload))

    result = inspect_endpoint("http://localhost:3000/test", "Say hello")

    assert result.success
    assert result.status_code == 200
    assert result.error is None
    assert result.suggestions["answer"] == "$.text"
    paths = [p for p, _ in result.fields]
    assert "$.text" in paths
    assert "$.chatId" in paths


def test_fastapi_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "answer": "Refunds take 30 days.",
        "citations": [{"source": "policy.pdf"}],
        "debug": {"retrieved": [{"source": "policy.pdf"}]},
        "tool_calls": [],
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _make_response(200, payload))

    result = inspect_endpoint("http://localhost:8000/chat", "What is the refund policy?")

    assert result.success
    assert result.suggestions["answer"] == "$.answer"
    assert result.suggestions["citations"] == "$.citations[*].source"
    assert result.suggestions["retrieved_sources"] == "$.debug.retrieved[*].source"


def test_non_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **kw: httpx.Response(200, content=b"<html>not json</html>",
                                         headers={"content-type": "text/html"}),
    )

    result = inspect_endpoint("http://localhost:9999/bad", "hello")

    assert not result.success
    assert result.status_code == 200
    assert result.error is not None
    assert "JSON" in result.error


def test_http_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _make_response(500, {"error": "internal"}))

    result = inspect_endpoint("http://localhost:9999/err", "hello")

    assert not result.success
    assert result.status_code == 500
    assert "500" in (result.error or "")


def test_http_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _make_response(404, {"error": "not found"}))

    result = inspect_endpoint("http://localhost:9999/missing", "hello")

    assert not result.success
    assert result.status_code == 404


def test_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_connect(*a: Any, **kw: Any) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "post", raise_connect)

    result = inspect_endpoint("http://localhost:1/nope", "hello")

    assert not result.success
    assert result.status_code is None
    assert "Connection failed" in (result.error or "")


def test_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_timeout(*a: Any, **kw: Any) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", raise_timeout)

    result = inspect_endpoint("http://localhost:1/slow", "hello")

    assert not result.success
    assert "timed out" in (result.error or "")


def test_json_array_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _make_response(200, [1, 2, 3]))

    result = inspect_endpoint("http://localhost:9999/array", "hello")

    assert not result.success
    assert result.error is not None
    assert "JSON object" in result.error


def test_probe_sends_correct_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return _make_response(200, {"text": "hi"})

    monkeypatch.setattr(httpx, "post", fake_post)

    inspect_endpoint("http://localhost:3000/ep", "Test question", timeout=5.0)

    assert captured["url"] == "http://localhost:3000/ep"
    assert captured["json"] == {"question": "Test question", "streaming": False}
