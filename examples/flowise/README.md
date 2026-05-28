# Flowise example

This example runs a smoke and security-pattern audit against a local [Flowise](https://flowiseai.com/) endpoint.

It checks that the chatflow:
- responds without errors
- does not echo back prompt templates or system messages
- does not include environment variable values (API keys, passwords) in its answer
- does not call dangerous tools (file deletion, shell execution, email export)

These are regression checks — they help catch known bad patterns in responses.
They do not imply that Flowise is insecure, and passing these checks does not
mean your deployment is fully secure.

---

## Prerequisites

1. **Flowise running locally.** The simplest way:

   ```bash
   docker run -p 3000:3000 flowiseai/flowise
   ```

   Or follow the [Flowise installation guide](https://docs.flowiseai.com/getting-started).

2. **A chatflow ID.** Open the Flowise UI, create or open a chatflow, and copy the ID from the URL:

   ```
   http://localhost:3000/chatflow/<FLOWISE_CHATFLOW_ID>
   ```

---

## Running the audit

```bash
FLOWISE_CHATFLOW_ID=<your-chatflow-id> rag-agent-audit run examples/flowise/audit.yaml
```

Or with Docker:

```bash
FLOWISE_CHATFLOW_ID=<your-chatflow-id> docker run --rm \
  --network host \
  -v "$PWD:/workspace" \
  -e FLOWISE_CHATFLOW_ID \
  rag-agent-audit run /workspace/examples/flowise/audit.yaml
```

`--network host` is needed so the container can reach Flowise on `localhost:3000`.

---

## What the checks cover

| Test | What it checks |
|------|----------------|
| `flowise-basic-response` | Chatflow responds without errors or tracebacks |
| `flowise-prompt-template-not-leaked` | Prompt template is not echoed in the answer |
| `flowise-developer-message-not-leaked` | System/developer message is not echoed |
| `flowise-private-api-key-request` | Common API key patterns do not appear in the answer |
| `flowise-local-env-file-request` | `.env` file contents are not echoed |
| `flowise-database-secret-request` | Database credentials are not echoed |
| `flowise-dangerous-file-delete-request` | Dangerous file-deletion tools are not called |
| `flowise-dangerous-email-request` | Data export / email tools are not called |
| `flowise-shell-command-request` | Shell execution tools are not called |
| `flowise-no-tool-call-baseline` | A benign summary question does not trigger dangerous tools |

---

## Adapting for your chatflow

The default `response_mapping` assumes Flowise's standard response shape:

```yaml
response_mapping:
  answer: $.text
  citations: $.citations[*].source
  retrieved_sources: $.debug.retrieved[*].source
  tool_calls: $.tool_calls[*].name
```

If your chatflow returns a different shape, use `inspect` to detect it:

```bash
rag-agent-audit inspect \
  --endpoint "http://localhost:3000/api/v1/prediction/${FLOWISE_CHATFLOW_ID}" \
  --question "Say hello in one sentence."
```

Then update `response_mapping` in `audit.yaml` with the suggested paths.

---

## Limitations

- **Mock mode is not available for this example.** The Flowise example uses `mode: http` and requires a running Flowise instance.
- **`forbidden_retrieved_sources` checks require Flowise to expose retriever output.** If your chatflow does not include debug retrieval output in the response, those checks will always pass vacuously.
- **`forbidden_tools` checks require tool call names in the response.** Standard Flowise chatflows may not expose this field; update `response_mapping` if yours does.
- These checks test against specific string patterns. They do not guarantee your chatflow cannot be prompted into other behaviors not covered here.
