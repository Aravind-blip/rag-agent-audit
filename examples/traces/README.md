# Trace Import Examples

Sample trace export files for the `rag-agent-audit trace import` commands (v0.8).

No running service, API key, or network connection is needed.

## Files

| File | Format | Records |
|------|--------|---------|
| `langfuse-traces.jsonl` | Langfuse-like JSONL export | 3 |
| `otel-traces.jsonl` | OpenTelemetry span JSONL | 3 |

## Quick start

```bash
# Import Langfuse traces
rag-agent-audit trace import langfuse examples/traces/langfuse-traces.jsonl \
  --output /tmp/langfuse-events.jsonl

# Import OTel spans
rag-agent-audit trace import otel examples/traces/otel-traces.jsonl \
  --output /tmp/otel-events.jsonl

# Inspect statistics
rag-agent-audit trace stats /tmp/langfuse-events.jsonl
rag-agent-audit trace stats /tmp/otel-events.jsonl
```

## Normalized output format

Every imported event is written as a single JSON object per line:

```json
{
  "trace_id": "trace-001",
  "span_id": "span-001",
  "name": "agent.run",
  "input": "What is the refund policy?",
  "answer": "Refunds are available within 30 days.",
  "citations": ["org_a/refund_policy.md"],
  "retrieved_sources": ["org_a/refund_policy.md"],
  "tool_calls": ["search_docs"],
  "approved_tools": ["search_docs"],
  "metadata": {"source_format": "langfuse"}
}
```

## Langfuse field mapping

| Normalized field | Langfuse source fields (first match wins) |
|-----------------|------------------------------------------|
| `trace_id` | `id`, `traceId`, `trace_id` |
| `span_id` | `spanId`, `span_id`, `observation_id` |
| `name` | `name` |
| `input` | `input` (string or dict with `question`/`input`/`text` key) |
| `answer` | `output` (string or dict with `answer`/`text`/`output` key) |
| `citations` | `citations` |
| `retrieved_sources` | `retrieved_sources` |
| `tool_calls` | `tool_calls` |
| `approved_tools` | `approved_tools` |

## OTel field mapping

| Normalized field | OTel source |
|-----------------|-------------|
| `trace_id` | `traceId` or `trace_id` |
| `span_id` | `spanId` or `span_id` |
| `name` | `name` |
| `input` | `attributes["rag.input"]` |
| `answer` | `attributes["rag.answer"]` |
| `citations` | `attributes["rag.citations"]` (list or comma-separated string) |
| `retrieved_sources` | `attributes["rag.retrieved_sources"]` (list or comma-separated string) |
| `tool_calls` | `attributes["agent.tool_calls"]` (list or comma-separated string) |
| `approved_tools` | `attributes["agent.approved_tools"]` (list or comma-separated string) |

## Notes

- Blank lines in input files are silently ignored.
- Missing optional fields default to empty strings or empty lists.
- No network calls are made; all processing is local.
- Importing does not run audit checks. Use `rag-agent-audit run` for that.
