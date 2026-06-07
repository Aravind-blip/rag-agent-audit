# rag-agent-audit

CI regression testing for RAG apps and AI agents.

[![CI](https://github.com/Aravind-blip/rag-agent-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/Aravind-blip/rag-agent-audit/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Why

RAG and agent systems fail in ways that standard backend tests miss. A user in Tenant A asks a broad question. The retriever pulls a document from Tenant B. The model summarizes it. The citation points to Tenant B's source. The answer leaks restricted data — and no HTTP status code changed.

`rag-agent-audit` helps catch known regression patterns across retrieval, citation, answer generation, and tool calls. Run it in CI to surface these regressions before deployment.

It does not guarantee security, replace access control design, or certify compliance. It is a regression testing tool.

## What it checks

| Check | Description |
|-------|-------------|
| `expected_sources` | Fails if a required citation is missing from the answer |
| `forbidden_sources` | Fails if a restricted source appears in citations |
| `forbidden_retrieved_sources` | Fails if a restricted source was retrieved, even if not cited |
| `must_contain` | Fails if a required string is absent from the answer |
| `must_not_contain` | Fails if a prohibited string (e.g. prompt injection echo) appears in the answer |
| `should_fallback` | Fails if the system answers when it should refuse, or refuses when it should answer |
| `forbidden_tools` | Fails if a prohibited tool (e.g. `delete_user`) was called |
| `tenant_leakage` | Fails if any citation or retrieved source violates allowed namespace prefixes or contains a forbidden tenant ID |
| `known_sources` | Fails if any citation or retrieved source is not present in a JSONL corpus manifest (exact path match) |
| `tool_policy` | Fails if a called tool is outside an allowlist (`allowed_tools`), matches a forbidden glob pattern (`forbidden_tool_patterns`), or was called without explicit approval (`required_approval_tools`) |

## What it does not do

- It does not guarantee your system is secure.
- It does not replace access control, secure retrieval design, or threat modeling.
- It does not perform LLM-as-judge evaluation (uses deterministic checks only).
- It does not scan infrastructure or network configuration.
- It does not certify compliance with any standard.

## Installation

### From PyPI

```bash
pip install rag-agent-audit
```

Or, for a CLI tool installed in an isolated environment:

```bash
pipx install rag-agent-audit
```

Requires Python 3.10+.

### From source

```bash
git clone https://github.com/Aravind-blip/rag-agent-audit.git
cd rag-agent-audit
pip install -e .
```

### Docker

```bash
docker build -t rag-agent-audit .
```

No local Python environment required. See [Docker usage](#docker) below.

---

## Quickstart

### 1. Generate a config

```bash
# Mock mode — no running app needed
rag-agent-audit init basic --output audit.yaml

# Flowise — runs against a local Flowise endpoint
rag-agent-audit init flowise \
  --endpoint 'http://localhost:3000/api/v1/prediction/${FLOWISE_CHATFLOW_ID}' \
  --output flowise-audit.yaml

# FastAPI / custom HTTP
rag-agent-audit init fastapi \
  --endpoint http://localhost:8000/chat \
  --output audit.yaml
```

Prints to stdout if `--output` is omitted, so you can review before writing.

### 2. Run in mock mode

```bash
rag-agent-audit run audit.yaml
```

```
RAG Agent Audit — basic-rag-security-audit
Passed: 4  Failed: 0  Total: 4

All tests passed.
```

Mock mode uses inline YAML responses — no running app, no network.

### 3. Inspect a real endpoint

Before writing checks, probe your endpoint to see what fields it returns:

```bash
rag-agent-audit inspect \
  --endpoint http://localhost:3000/api/v1/prediction/<FLOW_ID> \
  --question "Say hello in one sentence."
```

Output:

```
Endpoint responded successfully.
Status: 200

Detected response fields:
  text          string
  sourceDocuments  array[2]

Suggested response_mapping:
  answer: $.text
  citations: $.sourceDocuments[*].source
```

Copy the suggested `response_mapping` into your `audit.yaml`.

### 4. Run against a real HTTP endpoint

```yaml
suite: my-rag-audit
mode: http
endpoint: http://localhost:8000/api/chat

request:
  headers:
    authorization: "Bearer ${API_TOKEN}"

response_mapping:
  answer: $.answer
  citations: $.citations[*].source
  tool_calls: $.tool_calls[*].name

tests:
  - name: refund-policy-check
    question: "What is the refund policy?"
    expected_sources:
      - "refund_policy.pdf"
    must_contain:
      - "30 days"
```

```bash
API_TOKEN=mytoken rag-agent-audit run audit.yaml
```

---

## Response mapping

Map your app's JSON response shape using JSONPath:

```yaml
response_mapping:
  answer: $.result.text
  citations: $.result.sources[*].id
  retrieved_sources: $.debug.retrieved[*].source
  tool_calls: $.tool_calls[*].name
```

Use `rag-agent-audit inspect` to auto-detect fields from a live endpoint rather than guessing paths by hand.

---

## Reports

```bash
rag-agent-audit run audit.yaml                                      # terminal (default)
rag-agent-audit run audit.yaml --format json --output results.json
rag-agent-audit run audit.yaml --format markdown --output report.md
rag-agent-audit run audit.yaml --format junit --output results.xml  # JUnit XML for CI
```

Failure messages include a detail line, an answer preview, and a suggestion — designed to make regressions actionable without digging through logs.

---

## CI integration

Exit code is `0` if all checks pass, `1` if any fail, `2` on config error.

### JUnit XML

Most CI platforms (GitHub Actions, Jenkins, GitLab CI) can ingest JUnit XML directly:

```yaml
# .github/workflows/audit.yml
- name: Run RAG audit
  run: rag-agent-audit run audit.yaml --format junit --output audit-results.xml

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: audit-results
    path: audit-results.xml
```

### GitHub Actions step summary

Add `--github-summary` to append a Markdown table to the workflow run summary page:

```yaml
- name: Run RAG audit
  run: rag-agent-audit run audit.yaml --github-summary
```

The summary is written even if tests fail. If `GITHUB_STEP_SUMMARY` is not set (i.e., outside GitHub Actions), a warning is printed and the audit continues normally.

### Full GitHub Actions example

```yaml
- name: Run RAG audit
  run: |
    rag-agent-audit run audit.yaml \
      --format junit \
      --output audit-results.xml \
      --github-summary

- name: Upload JUnit results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: audit-results
    path: audit-results.xml
```

---

## Docker

Run without installing Python locally:

```bash
# Build
docker build -t rag-agent-audit .

# Run audit from current directory
docker run --rm \
  -v "$PWD:/workspace" \
  rag-agent-audit run /workspace/examples/basic/audit.yaml

# JUnit output written back to the host
docker run --rm \
  -v "$PWD:/workspace" \
  rag-agent-audit run /workspace/examples/basic/audit.yaml \
  --format junit \
  --output /workspace/audit-results.xml
```

Mount your config and example files under `/workspace` (or any path). The container has no network dependencies for mock mode.

For HTTP mode, the container must be able to reach your endpoint — use `--network host` or Docker Compose networking as appropriate for your setup.

---

## Commands

```
rag-agent-audit init [TEMPLATE]     Generate a starter audit.yaml
  --endpoint URL                    Endpoint URL (flowise, fastapi templates)
  --output PATH / -o PATH           Write to file instead of stdout
  --force                           Overwrite if file exists
  Supported templates: basic, flowise, fastapi

rag-agent-audit inspect             Probe an endpoint and suggest response_mapping
  --endpoint URL                    (required)
  --question TEXT                   Probe question (default: "Say hello in one sentence.")
  --timeout FLOAT                   Request timeout in seconds (default: 20)

rag-agent-audit validate FILE       Validate config without running tests

rag-agent-audit run FILE            Run an audit suite
  --format terminal|json|markdown|junit
  --output PATH / -o PATH           Write report to file
  --github-summary                  Append Markdown summary to $GITHUB_STEP_SUMMARY
```

---

## Flowise example

`examples/flowise/` contains a smoke and security-pattern audit for a local Flowise endpoint. It checks that the chatflow responds without leaking environment variables, prompt templates, or calling dangerous tools — the same patterns you would want to verify in any RAG deployment.

Requires:
- Flowise running locally (`docker run -p 3000:3000 flowiseai/flowise` or similar)
- `FLOWISE_CHATFLOW_ID` set to a valid chatflow ID in your Flowise instance

```bash
FLOWISE_CHATFLOW_ID=<your-chatflow-id> rag-agent-audit run examples/flowise/audit.yaml
```

See [`examples/flowise/README.md`](examples/flowise/README.md) for setup details.

---

## Limitations

- **Deterministic checks only.** Pattern and source name matching. No LLM judge, no semantic evaluation.
- **Mock mode accuracy.** Mock responses test your check config and CI pipeline, not your actual app.
- **Retrieved sources require debug output.** `forbidden_retrieved_sources` only works if your app exposes retriever output in the response.
- **Not a complete security solution.** Passing tests does not mean your system is secure. Combine with access control, logging, manual review, and threat modeling.
- **Docker HTTP mode requires network access.** Mock-mode audits run fully offline; HTTP-mode audits require container network access to the target endpoint.

---

## Roadmap

- **v0.2** ✓ `init`, `inspect`, JUnit XML, GitHub Actions summary, Docker, improved diagnostics
- **v0.3** — OWASP LLM test packs, prompt injection corpus
- **v0.4** — Agent tool sequence checks, MCP tool policy checks
- **v0.5** — OpenTelemetry export, Langfuse trace import
- **v1.0** — Stable schema, PyPI release, complete docs

---

## Publishing

Releases are published to PyPI automatically when a GitHub Release is created.
Publishing uses [Trusted Publishing (OIDC)](https://docs.pypi.org/trusted-publishers/) — no API tokens are stored in the repository.

```
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
# Create and publish the GitHub Release — CI handles the rest.
```

See [docs/release.md](docs/release.md) for the full release checklist, TestPyPI dry-run instructions, and Trusted Publishing setup.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

Apache 2.0. See [LICENSE](LICENSE).
