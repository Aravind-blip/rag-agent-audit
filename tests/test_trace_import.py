"""Tests for trace_import module and CLI trace commands (v0.8)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from rag_agent_audit.cli import app
from rag_agent_audit.trace_import import (
    TraceEvent,
    TraceStats,
    compute_trace_stats,
    event_to_jsonl,
    format_trace_stats,
    import_langfuse,
    import_otel,
    iter_trace_events,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_jsonl(path: Path, lines: list[dict]) -> None:  # type: ignore[type-arg]
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def read_jsonl(path: Path) -> list[dict]:  # type: ignore[type-arg]
    result = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                result.append(json.loads(raw))
    return result


# ===========================================================================
# Langfuse importer — unit tests
# ===========================================================================


def test_langfuse_basic_fields(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t1", "name": "agent.run", "input": "Q?", "output": "A."}])
    events = list(import_langfuse(f))
    assert len(events) == 1
    e = events[0]
    assert e.trace_id == "t1"
    assert e.name == "agent.run"
    assert e.input == "Q?"
    assert e.answer == "A."


def test_langfuse_trace_id_camel(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"traceId": "t2", "name": "x"}])
    events = list(import_langfuse(f))
    assert events[0].trace_id == "t2"


def test_langfuse_trace_id_underscore(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"trace_id": "t3", "name": "x"}])
    events = list(import_langfuse(f))
    assert events[0].trace_id == "t3"


def test_langfuse_id_takes_priority_over_traceId(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "primary", "traceId": "secondary", "name": "x"}])
    events = list(import_langfuse(f))
    assert events[0].trace_id == "primary"


def test_langfuse_span_id_camel(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "spanId": "s1", "name": "x"}])
    events = list(import_langfuse(f))
    assert events[0].span_id == "s1"


def test_langfuse_span_id_underscore(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "span_id": "s2", "name": "x"}])
    events = list(import_langfuse(f))
    assert events[0].span_id == "s2"


def test_langfuse_span_id_observation(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "observation_id": "obs-1", "name": "x"}])
    events = list(import_langfuse(f))
    assert events[0].span_id == "obs-1"


def test_langfuse_input_string(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "input": "plain question"}])
    events = list(import_langfuse(f))
    assert events[0].input == "plain question"


def test_langfuse_input_dict_question_key(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "input": {"question": "nested Q"}}])
    events = list(import_langfuse(f))
    assert events[0].input == "nested Q"


def test_langfuse_input_dict_input_key(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "input": {"input": "alt key Q"}}])
    events = list(import_langfuse(f))
    assert events[0].input == "alt key Q"


def test_langfuse_output_string(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "output": "plain answer"}])
    events = list(import_langfuse(f))
    assert events[0].answer == "plain answer"


def test_langfuse_output_dict_answer_key(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "output": {"answer": "nested A"}}])
    events = list(import_langfuse(f))
    assert events[0].answer == "nested A"


def test_langfuse_citations_list(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "citations": ["a.md", "b.md"]}])
    events = list(import_langfuse(f))
    assert events[0].citations == ["a.md", "b.md"]


def test_langfuse_tool_calls_list(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "tool_calls": ["search_docs"]}])
    events = list(import_langfuse(f))
    assert events[0].tool_calls == ["search_docs"]


def test_langfuse_retrieved_sources_list(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "retrieved_sources": ["c.md"]}])
    events = list(import_langfuse(f))
    assert events[0].retrieved_sources == ["c.md"]


def test_langfuse_approved_tools_list(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t", "name": "x", "approved_tools": ["write_db"]}])
    events = list(import_langfuse(f))
    assert events[0].approved_tools == ["write_db"]


def test_langfuse_missing_optional_fields_use_defaults(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{}])
    events = list(import_langfuse(f))
    e = events[0]
    assert e.trace_id == ""
    assert e.span_id == ""
    assert e.name == ""
    assert e.input == ""
    assert e.answer == ""
    assert e.citations == []
    assert e.retrieved_sources == []
    assert e.tool_calls == []
    assert e.approved_tools == []


def test_langfuse_blank_lines_ignored(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    f.write_text(
        '\n{"id": "t1", "name": "a"}\n\n{"id": "t2", "name": "b"}\n\n',
        encoding="utf-8",
    )
    events = list(import_langfuse(f))
    assert len(events) == 2


def test_langfuse_malformed_json_raises(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    f.write_text('{"id": "ok"}\nnot json\n', encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="invalid JSON"):
        list(import_langfuse(f))


def test_langfuse_source_format_in_metadata(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": "t"}])
    events = list(import_langfuse(f))
    assert events[0].metadata.get("source_format") == "langfuse"


def test_langfuse_multiple_events(tmp_path: Path) -> None:
    f = tmp_path / "lf.jsonl"
    write_jsonl(f, [{"id": f"t{i}", "name": f"e{i}"} for i in range(5)])
    events = list(import_langfuse(f))
    assert len(events) == 5
    assert events[2].trace_id == "t2"


# ===========================================================================
# OTel importer — unit tests
# ===========================================================================


def test_otel_basic_fields(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(f, [{"traceId": "tr1", "spanId": "sp1", "name": "rag.query"}])
    events = list(import_otel(f))
    assert len(events) == 1
    e = events[0]
    assert e.trace_id == "tr1"
    assert e.span_id == "sp1"
    assert e.name == "rag.query"


def test_otel_trace_id_underscore(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(f, [{"trace_id": "tr2", "name": "x"}])
    events = list(import_otel(f))
    assert events[0].trace_id == "tr2"


def test_otel_span_id_underscore(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(f, [{"traceId": "tr", "span_id": "sp2", "name": "x"}])
    events = list(import_otel(f))
    assert events[0].span_id == "sp2"


def test_otel_rag_input_attribute(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(f, [{"traceId": "t", "name": "x", "attributes": {"rag.input": "my question"}}])
    events = list(import_otel(f))
    assert events[0].input == "my question"


def test_otel_rag_answer_attribute(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f, [{"traceId": "t", "name": "x", "attributes": {"rag.answer": "my answer"}}]
    )
    events = list(import_otel(f))
    assert events[0].answer == "my answer"


def test_otel_rag_citations_list(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f,
        [{"traceId": "t", "name": "x", "attributes": {"rag.citations": ["a.md", "b.md"]}}],
    )
    events = list(import_otel(f))
    assert events[0].citations == ["a.md", "b.md"]


def test_otel_rag_citations_comma_separated(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f,
        [{"traceId": "t", "name": "x", "attributes": {"rag.citations": "a.md,b.md"}}],
    )
    events = list(import_otel(f))
    assert events[0].citations == ["a.md", "b.md"]


def test_otel_tool_calls_list(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f,
        [
            {
                "traceId": "t",
                "name": "x",
                "attributes": {"agent.tool_calls": ["search_docs", "get_policy"]},
            }
        ],
    )
    events = list(import_otel(f))
    assert events[0].tool_calls == ["search_docs", "get_policy"]


def test_otel_tool_calls_comma_separated(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    attrs = {"agent.tool_calls": "search_docs,get_policy"}
    write_jsonl(f, [{"traceId": "t", "name": "x", "attributes": attrs}])
    events = list(import_otel(f))
    assert events[0].tool_calls == ["search_docs", "get_policy"]


def test_otel_approved_tools_list(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f, [{"traceId": "t", "name": "x", "attributes": {"agent.approved_tools": ["write_db"]}}]
    )
    events = list(import_otel(f))
    assert events[0].approved_tools == ["write_db"]


def test_otel_retrieved_sources_list(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f,
        [{"traceId": "t", "name": "x", "attributes": {"rag.retrieved_sources": ["c.md"]}}],
    )
    events = list(import_otel(f))
    assert events[0].retrieved_sources == ["c.md"]


def test_otel_retrieved_sources_comma_separated(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f,
        [{"traceId": "t", "name": "x", "attributes": {"rag.retrieved_sources": "c.md,d.md"}}],
    )
    events = list(import_otel(f))
    assert events[0].retrieved_sources == ["c.md", "d.md"]


def test_otel_missing_attributes_key(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(f, [{"traceId": "t", "name": "x"}])
    events = list(import_otel(f))
    e = events[0]
    assert e.input == ""
    assert e.citations == []
    assert e.tool_calls == []


def test_otel_partial_attributes(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(
        f, [{"traceId": "t", "name": "x", "attributes": {"rag.input": "only input present"}}]
    )
    events = list(import_otel(f))
    e = events[0]
    assert e.input == "only input present"
    assert e.answer == ""
    assert e.citations == []


def test_otel_blank_lines_ignored(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    f.write_text(
        '\n{"traceId": "t1"}\n\n{"traceId": "t2"}\n',
        encoding="utf-8",
    )
    events = list(import_otel(f))
    assert len(events) == 2


def test_otel_malformed_json_raises(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    f.write_text('{"traceId": "ok"}\n!!bad\n', encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="invalid JSON"):
        list(import_otel(f))


def test_otel_source_format_in_metadata(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(f, [{"traceId": "t"}])
    events = list(import_otel(f))
    assert events[0].metadata.get("source_format") == "otel"


def test_otel_multiple_events(tmp_path: Path) -> None:
    f = tmp_path / "ot.jsonl"
    write_jsonl(f, [{"traceId": f"t{i}", "spanId": f"s{i}", "name": f"e{i}"} for i in range(4)])
    events = list(import_otel(f))
    assert len(events) == 4
    assert events[3].trace_id == "t3"


# ===========================================================================
# Serialization — event_to_jsonl / iter_trace_events
# ===========================================================================


def test_event_to_jsonl_is_valid_json() -> None:
    e = TraceEvent(trace_id="t", span_id="s", name="n", input="Q", answer="A")
    line = event_to_jsonl(e)
    data = json.loads(line)
    assert data["trace_id"] == "t"
    assert data["name"] == "n"
    assert data["input"] == "Q"
    assert data["answer"] == "A"


def test_event_to_jsonl_deterministic() -> None:
    e = TraceEvent(
        trace_id="t", tool_calls=["b", "a"], citations=["z.md", "a.md"]
    )
    assert event_to_jsonl(e) == event_to_jsonl(e)


def test_event_to_jsonl_contains_metadata() -> None:
    e = TraceEvent(metadata={"source_format": "langfuse"})
    data = json.loads(event_to_jsonl(e))
    assert data["metadata"]["source_format"] == "langfuse"


def test_iter_trace_events_roundtrip(tmp_path: Path) -> None:
    f = tmp_path / "events.jsonl"
    original = TraceEvent(
        trace_id="t1",
        span_id="s1",
        name="n",
        input="Q",
        answer="A",
        citations=["a.md"],
        retrieved_sources=["b.md"],
        tool_calls=["search"],
        approved_tools=["search"],
        metadata={"source_format": "langfuse"},
    )
    f.write_text(event_to_jsonl(original) + "\n", encoding="utf-8")
    events = list(iter_trace_events(f))
    assert len(events) == 1
    e = events[0]
    assert e.trace_id == "t1"
    assert e.citations == ["a.md"]
    assert e.tool_calls == ["search"]
    assert e.metadata["source_format"] == "langfuse"


def test_iter_trace_events_blank_lines_ignored(tmp_path: Path) -> None:
    f = tmp_path / "events.jsonl"
    e = TraceEvent(trace_id="t1")
    f.write_text(f"\n{event_to_jsonl(e)}\n\n", encoding="utf-8")
    events = list(iter_trace_events(f))
    assert len(events) == 1


def test_iter_trace_events_malformed_raises(tmp_path: Path) -> None:
    f = tmp_path / "events.jsonl"
    f.write_text("not json\n", encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="invalid JSON"):
        list(iter_trace_events(f))


# ===========================================================================
# Statistics
# ===========================================================================


def _make_stats_events() -> list[TraceEvent]:
    return [
        TraceEvent(
            trace_id="t1",
            tool_calls=["search_docs"],
            citations=["a.md"],
            retrieved_sources=["a.md"],
            metadata={"source_format": "langfuse"},
        ),
        TraceEvent(
            trace_id="t2",
            tool_calls=["write_db", "search_docs"],
            citations=["b.md"],
            metadata={"source_format": "langfuse"},
        ),
        TraceEvent(
            trace_id="t3",
            metadata={"source_format": "otel"},
        ),
    ]


def test_stats_total_events() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.total_events == 3


def test_stats_by_format() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.by_format == {"langfuse": 2, "otel": 1}


def test_stats_events_with_tool_calls() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.events_with_tool_calls == 2


def test_stats_unique_tool_calls_sorted() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.unique_tool_calls == ["search_docs", "write_db"]


def test_stats_events_with_citations() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.events_with_citations == 2


def test_stats_unique_citations_sorted() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.unique_citations == ["a.md", "b.md"]


def test_stats_events_with_retrieved_sources() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.events_with_retrieved_sources == 1


def test_stats_unique_retrieved_sources_sorted() -> None:
    stats = compute_trace_stats(iter(_make_stats_events()))
    assert stats.unique_retrieved_sources == ["a.md"]


def test_stats_empty_stream() -> None:
    stats = compute_trace_stats(iter([]))
    assert stats.total_events == 0
    assert stats.by_format == {}
    assert stats.events_with_tool_calls == 0
    assert stats.unique_tool_calls == []
    assert stats.events_with_citations == 0
    assert stats.unique_citations == []


def test_stats_unknown_format_counted() -> None:
    events = [TraceEvent(trace_id="t", metadata={})]
    stats = compute_trace_stats(iter(events))
    assert stats.by_format == {"unknown": 1}


def test_format_trace_stats_contains_total() -> None:
    stats = TraceStats(total_events=7)
    output = format_trace_stats(stats)
    assert "7" in output
    assert "Total events" in output


def test_format_trace_stats_contains_format() -> None:
    stats = TraceStats(by_format={"langfuse": 3, "otel": 2})
    output = format_trace_stats(stats)
    assert "langfuse=3" in output
    assert "otel=2" in output


def test_format_trace_stats_no_tools_shows_none() -> None:
    stats = TraceStats()
    output = format_trace_stats(stats)
    assert "(none)" in output


def test_format_trace_stats_shows_tool_names() -> None:
    stats = TraceStats(unique_tool_calls=["search_docs", "write_db"])
    output = format_trace_stats(stats)
    assert "search_docs" in output
    assert "write_db" in output


# ===========================================================================
# CLI — trace import langfuse
# ===========================================================================


def test_cli_trace_import_langfuse_writes_output(tmp_path: Path) -> None:
    input_f = tmp_path / "lf.jsonl"
    output_f = tmp_path / "out.jsonl"
    write_jsonl(
        input_f,
        [{"id": "t1", "name": "agent.run", "input": "Q?", "output": "A.", "citations": ["x.md"]}],
    )
    result = runner.invoke(
        app, ["trace", "import", "langfuse", str(input_f), "--output", str(output_f)]
    )
    assert result.exit_code == 0
    events = read_jsonl(output_f)
    assert len(events) == 1
    assert events[0]["trace_id"] == "t1"
    assert events[0]["citations"] == ["x.md"]


def test_cli_trace_import_langfuse_missing_input() -> None:
    result = runner.invoke(app, ["trace", "import", "langfuse", "/no/such/file.jsonl"])
    assert result.exit_code == 2


def test_cli_trace_import_langfuse_stdout(tmp_path: Path) -> None:
    input_f = tmp_path / "lf.jsonl"
    write_jsonl(input_f, [{"id": "t1", "name": "x"}])
    result = runner.invoke(app, ["trace", "import", "langfuse", str(input_f)])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[0])
    assert data["trace_id"] == "t1"


def test_cli_trace_import_langfuse_empty_file_exits_1(tmp_path: Path) -> None:
    input_f = tmp_path / "empty.jsonl"
    input_f.write_text("", encoding="utf-8")
    result = runner.invoke(app, ["trace", "import", "langfuse", str(input_f)])
    assert result.exit_code == 1


# ===========================================================================
# CLI — trace import otel
# ===========================================================================


def test_cli_trace_import_otel_writes_output(tmp_path: Path) -> None:
    input_f = tmp_path / "ot.jsonl"
    output_f = tmp_path / "out.jsonl"
    write_jsonl(
        input_f,
        [
            {
                "traceId": "tr1",
                "spanId": "sp1",
                "name": "rag.query",
                "attributes": {
                    "rag.input": "Q?",
                    "rag.answer": "A.",
                    "agent.tool_calls": ["search_docs"],
                },
            }
        ],
    )
    result = runner.invoke(
        app, ["trace", "import", "otel", str(input_f), "--output", str(output_f)]
    )
    assert result.exit_code == 0
    events = read_jsonl(output_f)
    assert len(events) == 1
    assert events[0]["trace_id"] == "tr1"
    assert events[0]["tool_calls"] == ["search_docs"]


def test_cli_trace_import_otel_missing_input() -> None:
    result = runner.invoke(app, ["trace", "import", "otel", "/no/such/file.jsonl"])
    assert result.exit_code == 2


def test_cli_trace_import_otel_stdout(tmp_path: Path) -> None:
    input_f = tmp_path / "ot.jsonl"
    write_jsonl(input_f, [{"traceId": "tr2", "name": "x"}])
    result = runner.invoke(app, ["trace", "import", "otel", str(input_f)])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[0])
    assert data["trace_id"] == "tr2"


def test_cli_trace_import_otel_empty_file_exits_1(tmp_path: Path) -> None:
    input_f = tmp_path / "empty.jsonl"
    input_f.write_text("", encoding="utf-8")
    result = runner.invoke(app, ["trace", "import", "otel", str(input_f)])
    assert result.exit_code == 1


# ===========================================================================
# CLI — trace stats
# ===========================================================================


def test_cli_trace_stats_prints_stats(tmp_path: Path) -> None:
    events_f = tmp_path / "events.jsonl"
    events = [
        TraceEvent(
            trace_id="t1",
            tool_calls=["search_docs"],
            citations=["a.md"],
            metadata={"source_format": "langfuse"},
        ),
        TraceEvent(
            trace_id="t2",
            metadata={"source_format": "otel"},
        ),
    ]
    with open(events_f, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(event_to_jsonl(e) + "\n")

    result = runner.invoke(app, ["trace", "stats", str(events_f)])
    assert result.exit_code == 0
    assert "Total events" in result.output
    assert "2" in result.output
    assert "langfuse=1" in result.output or "langfuse" in result.output


def test_cli_trace_stats_missing_file() -> None:
    result = runner.invoke(app, ["trace", "stats", "/no/such/events.jsonl"])
    assert result.exit_code == 2


def test_cli_trace_stats_empty_file(tmp_path: Path) -> None:
    events_f = tmp_path / "empty.jsonl"
    events_f.write_text("", encoding="utf-8")
    result = runner.invoke(app, ["trace", "stats", str(events_f)])
    assert result.exit_code == 0
    assert "0" in result.output
