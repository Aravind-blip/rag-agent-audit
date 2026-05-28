"""
Core logic for the `rag-agent-audit inspect` command.

Sends a probe POST request to an endpoint, analyses the JSON response shape,
and suggests a response_mapping for use in audit.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

_ANSWER_CANDIDATES = ("text", "answer", "message", "output")


@dataclass
class InspectResult:
    """Structured output from an inspect probe."""

    success: bool
    status_code: int | None = None
    error: str | None = None
    fields: list[tuple[str, str]] = field(default_factory=list)
    suggestions: dict[str, str] = field(default_factory=dict)


def _type_label(value: Any) -> str:  # noqa: ANN401
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return f"array[{len(value)}]"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _collect_fields(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (jsonpath, type_label) pairs for root and one level of nesting."""
    result: list[tuple[str, str]] = []
    for key, value in data.items():
        result.append((f"$.{key}", _type_label(value)))
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                result.append((f"$.{key}.{nested_key}", _type_label(nested_value)))
    return result


def _suggest_mapping(data: dict[str, Any]) -> dict[str, str]:
    """Suggest response_mapping entries based on common response shapes."""
    suggestions: dict[str, str] = {}

    # Answer field: first match in priority order
    for candidate in _ANSWER_CANDIDATES:
        if isinstance(data.get(candidate), str):
            suggestions["answer"] = f"$.{candidate}"
            break

    # Fallback: result.text
    if "answer" not in suggestions:
        result_obj = data.get("result")
        if isinstance(result_obj, dict) and isinstance(result_obj.get("text"), str):
            suggestions["answer"] = "$.result.text"

    # citations or sources
    citations = data.get("citations")
    if (
        isinstance(citations, list)
        and citations
        and isinstance(citations[0], dict)
        and "source" in citations[0]
    ):
        suggestions["citations"] = "$.citations[*].source"
    else:
        sources = data.get("sources")
        if (
            isinstance(sources, list)
            and sources
            and isinstance(sources[0], dict)
            and "source" in sources[0]
        ):
            suggestions["citations"] = "$.sources[*].source"

    # retrieved_sources inside debug
    debug = data.get("debug")
    if isinstance(debug, dict):
        retrieved = debug.get("retrieved")
        if (
            isinstance(retrieved, list)
            and retrieved
            and isinstance(retrieved[0], dict)
            and "source" in retrieved[0]
        ):
            suggestions["retrieved_sources"] = "$.debug.retrieved[*].source"

    # tool_calls
    tool_calls = data.get("tool_calls")
    if (
        isinstance(tool_calls, list)
        and tool_calls
        and isinstance(tool_calls[0], dict)
        and "name" in tool_calls[0]
    ):
        suggestions["tool_calls"] = "$.tool_calls[*].name"

    return suggestions


def inspect_endpoint(
    endpoint: str,
    question: str,
    timeout: float = 20.0,
) -> InspectResult:
    """Send a probe POST request and return a structured InspectResult.

    Never raises; all errors are captured inside InspectResult.
    """
    payload: dict[str, Any] = {"question": question, "streaming": False}

    try:
        response = httpx.post(endpoint, json=payload, timeout=timeout)
    except httpx.ConnectError as exc:
        return InspectResult(success=False, error=f"Connection failed: {exc}")
    except httpx.TimeoutException:
        return InspectResult(success=False, error=f"Request timed out after {timeout}s.")
    except httpx.RequestError as exc:
        return InspectResult(success=False, error=f"Request error: {exc}")

    status = response.status_code

    if status >= 400:
        return InspectResult(
            success=False,
            status_code=status,
            error=f"Endpoint returned HTTP {status}.",
        )

    try:
        raw: Any = response.json()
    except Exception:  # noqa: BLE001
        return InspectResult(
            success=False,
            status_code=status,
            error="Response is not valid JSON.",
        )

    if not isinstance(raw, dict):
        return InspectResult(
            success=False,
            status_code=status,
            error=f"Expected a JSON object at root, got {type(raw).__name__}.",
        )

    data: dict[str, Any] = raw

    return InspectResult(
        success=True,
        status_code=status,
        fields=_collect_fields(data),
        suggestions=_suggest_mapping(data),
    )
