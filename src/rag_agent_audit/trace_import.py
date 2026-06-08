"""
Offline trace import and normalization.

Reads exported trace files (Langfuse JSONL or OpenTelemetry JSONL spans) and
writes normalized TraceEvent JSONL.  No network calls are made; this module
operates entirely on local files.

Public API
----------
import_langfuse(path)    — yield TraceEvent objects from a Langfuse JSONL export.
import_otel(path)        — yield TraceEvent objects from an OTel JSONL span export.
event_to_jsonl(event)    — serialize a TraceEvent to a JSONL line.
iter_trace_events(path)  — read normalized TraceEvent JSONL produced by this module.
compute_trace_stats(events) — aggregate TraceStats from a TraceEvent stream.
format_trace_stats(stats)   — format TraceStats as a human-readable report.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TraceEvent:
    """Normalized representation of a single trace span / observation.

    Fields mirror the audit engine's NormalizedResponse where applicable so
    that future work can run checks directly against imported traces.
    """

    trace_id: str = ""
    span_id: str = ""
    name: str = ""
    input: str = ""
    answer: str = ""
    citations: list[str] = field(default_factory=list)
    retrieved_sources: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    approved_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceStats:
    """Aggregated statistics over a stream of TraceEvent objects."""

    total_events: int = 0
    by_format: dict[str, int] = field(default_factory=dict)
    events_with_tool_calls: int = 0
    unique_tool_calls: list[str] = field(default_factory=list)
    events_with_citations: int = 0
    unique_citations: list[str] = field(default_factory=list)
    events_with_retrieved_sources: int = 0
    unique_retrieved_sources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_first(data: dict[str, Any], *keys: str, default: str = "") -> str:
    """Return str(data[key]) for the first key present in *data*, or *default*."""
    for key in keys:
        val = data.get(key)
        if val is not None:
            return str(val)
    return default


def _extract_text(val: Any, *keys: str) -> str:
    """Extract a plain-text string from a JSON value.

    - ``None``   → ``""``
    - ``str``    → value as-is
    - ``dict``   → first matching key whose value is a ``str`` (checked in
                   order); empty string if no match
    - anything else → ``""``

    This is conservative: complex nested structures silently return ``""``
    rather than a stringified dict.
    """
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        for key in keys:
            candidate = val.get(key)
            if isinstance(candidate, str):
                return candidate
    return ""


def _to_list(val: Any) -> list[str]:
    """Coerce a JSON value to a list of non-empty strings.

    - ``None``            → ``[]``
    - ``list``            → each element cast to str, empty strings dropped
    - comma-separated str → split on ``","``
    - other non-empty str → ``[val]``
    - empty str / other   → ``[]``
    """
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val if str(v).strip()]
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return []
        if "," in val:
            return [s.strip() for s in val.split(",") if s.strip()]
        return [val]
    return []


def _iter_jsonl(
    path: Path,
) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield (lineno, parsed_dict) for every non-blank line in *path*.

    Raises
    ------
    ValueError
        On any line that is not valid JSON, with the filename and line number
        included in the message.
    """
    name = path.name
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Trace file {name} has invalid JSON on line {lineno}: {exc.msg}"
                ) from exc
            yield lineno, data


# ---------------------------------------------------------------------------
# Langfuse importer
# ---------------------------------------------------------------------------


def _import_langfuse_record(data: dict[str, Any]) -> TraceEvent:
    """Convert one Langfuse-like JSON record to a TraceEvent."""
    return TraceEvent(
        trace_id=_get_first(data, "id", "traceId", "trace_id"),
        span_id=_get_first(data, "spanId", "span_id", "observation_id"),
        name=_get_first(data, "name"),
        # input / output can be plain strings or structured dicts
        input=_extract_text(data.get("input"), "question", "input", "text"),
        answer=_extract_text(data.get("output"), "answer", "text", "output"),
        citations=_to_list(data.get("citations")),
        retrieved_sources=_to_list(data.get("retrieved_sources")),
        tool_calls=_to_list(data.get("tool_calls")),
        approved_tools=_to_list(data.get("approved_tools")),
        metadata={"source_format": "langfuse"},
    )


def import_langfuse(path: Path) -> Iterator[TraceEvent]:
    """Yield normalized TraceEvent objects from a Langfuse JSONL export.

    Blank lines are silently skipped.

    Raises
    ------
    ValueError
        On any non-blank line that contains invalid JSON.
    """
    for _lineno, data in _iter_jsonl(path):
        yield _import_langfuse_record(data)


# ---------------------------------------------------------------------------
# OpenTelemetry importer
# ---------------------------------------------------------------------------


def _import_otel_record(data: dict[str, Any]) -> TraceEvent:
    """Convert one OTel-like span JSON record to a TraceEvent."""
    attrs: dict[str, Any] = data.get("attributes") or {}
    return TraceEvent(
        trace_id=_get_first(data, "traceId", "trace_id"),
        span_id=_get_first(data, "spanId", "span_id"),
        name=_get_first(data, "name"),
        input=_extract_text(attrs.get("rag.input")),
        answer=_extract_text(attrs.get("rag.answer")),
        citations=_to_list(attrs.get("rag.citations")),
        retrieved_sources=_to_list(attrs.get("rag.retrieved_sources")),
        tool_calls=_to_list(attrs.get("agent.tool_calls")),
        approved_tools=_to_list(attrs.get("agent.approved_tools")),
        metadata={"source_format": "otel"},
    )


def import_otel(path: Path) -> Iterator[TraceEvent]:
    """Yield normalized TraceEvent objects from an OTel JSONL span export.

    Blank lines are silently skipped.

    Raises
    ------
    ValueError
        On any non-blank line that contains invalid JSON.
    """
    for _lineno, data in _iter_jsonl(path):
        yield _import_otel_record(data)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def event_to_jsonl(event: TraceEvent) -> str:
    """Serialize a TraceEvent to a single JSONL line.

    Field order is stable and matches the TraceEvent definition.
    """
    return json.dumps(
        {
            "trace_id": event.trace_id,
            "span_id": event.span_id,
            "name": event.name,
            "input": event.input,
            "answer": event.answer,
            "citations": event.citations,
            "retrieved_sources": event.retrieved_sources,
            "tool_calls": event.tool_calls,
            "approved_tools": event.approved_tools,
            "metadata": event.metadata,
        }
    )


def iter_trace_events(path: Path) -> Iterator[TraceEvent]:
    """Yield TraceEvent objects from a normalized trace-events JSONL file.

    Blank lines are silently skipped.

    Raises
    ------
    ValueError
        On any non-blank line that contains invalid JSON.
    """
    for _lineno, data in _iter_jsonl(path):
        yield TraceEvent(
            trace_id=data.get("trace_id", ""),
            span_id=data.get("span_id", ""),
            name=data.get("name", ""),
            input=data.get("input", ""),
            answer=data.get("answer", ""),
            citations=data.get("citations") or [],
            retrieved_sources=data.get("retrieved_sources") or [],
            tool_calls=data.get("tool_calls") or [],
            approved_tools=data.get("approved_tools") or [],
            metadata=data.get("metadata") or {},
        )


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def compute_trace_stats(events: Iterator[TraceEvent]) -> TraceStats:
    """Aggregate TraceStats from a stream of TraceEvent objects."""
    total = 0
    by_format: dict[str, int] = {}
    events_with_tool_calls = 0
    unique_tools: set[str] = set()
    events_with_citations = 0
    unique_cit: set[str] = set()
    events_with_retrieved = 0
    unique_ret: set[str] = set()

    for event in events:
        total += 1
        fmt = event.metadata.get("source_format", "unknown")
        by_format[fmt] = by_format.get(fmt, 0) + 1

        if event.tool_calls:
            events_with_tool_calls += 1
            unique_tools.update(event.tool_calls)

        if event.citations:
            events_with_citations += 1
            unique_cit.update(event.citations)

        if event.retrieved_sources:
            events_with_retrieved += 1
            unique_ret.update(event.retrieved_sources)

    return TraceStats(
        total_events=total,
        by_format=dict(sorted(by_format.items())),
        events_with_tool_calls=events_with_tool_calls,
        unique_tool_calls=sorted(unique_tools),
        events_with_citations=events_with_citations,
        unique_citations=sorted(unique_cit),
        events_with_retrieved_sources=events_with_retrieved,
        unique_retrieved_sources=sorted(unique_ret),
    )


def format_trace_stats(stats: TraceStats) -> str:
    """Format TraceStats as a human-readable, deterministic report string."""
    by_fmt = (
        ", ".join(f"{k}={v}" for k, v in stats.by_format.items())
        if stats.by_format
        else "(none)"
    )
    tools_str = ", ".join(stats.unique_tool_calls) if stats.unique_tool_calls else "(none)"
    cit_str = ", ".join(stats.unique_citations) if stats.unique_citations else "(none)"
    ret_str = (
        ", ".join(stats.unique_retrieved_sources)
        if stats.unique_retrieved_sources
        else "(none)"
    )

    return (
        "Trace event statistics\n"
        f"  Total events                : {stats.total_events}\n"
        f"  By source format            : {by_fmt}\n"
        f"  Events with tool calls      : {stats.events_with_tool_calls}\n"
        f"  Unique tool calls           : {tools_str}\n"
        f"  Events with citations       : {stats.events_with_citations}\n"
        f"  Unique citation sources     : {cit_str}\n"
        f"  Events with retrieved srcs  : {stats.events_with_retrieved_sources}\n"
        f"  Unique retrieved sources    : {ret_str}"
    )
