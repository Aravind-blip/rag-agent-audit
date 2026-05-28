# rag-agent-audit

CI security regression testing for RAG apps and AI agents.

[![CI](https://github.com/Aravind-blip/rag-agent-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/Aravind-blip/rag-agent-audit/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Why

RAG and agent systems fail in ways that standard backend tests miss. A user in Tenant A asks a broad question. The retriever pulls a document from Tenant B. The model summarizes it. The citation points to Tenant B's source. The answer leaks restricted data — and no HTTP status code changed.

`rag-agent-audit` tests the full path: retrieval, citation, answer generation, and tool calls. Run it in CI to catch these regressions before deployment.

## What it checks

| Check | Description |
|-------|-------------|
| `expected_sources` | Fails if a required citation is missing from the answer |
| `forbidden_sources` | Fails if a restricted source appears in citations |
| `forbidden_retrieved_sources` | Fails if a restricted source was retrieved, even if not cited |
| `must_contain` | Fails if a required string is absent from the answer |
| `must_not_contain` | Fails if a prohibited string (e.g. prompt injection) appears in the answer |
| `should_fallback` | Fails if the system answers when it should refuse, or refuses when it should answer |
| `forbidden_tools` | Fails if a prohibited tool (e.g. `delete_user`) was called |

## What it does not do

- It does not guarantee your system is secure.
- It does not replace access control, secure retrieval design, or threat modeling.
- It does not perform LLM-as-judge evaluation (v0.1 uses deterministic checks only).
- It does not scan infrastructure or network configuration.

## Installation

From source while the project is pre-release:

```bash
git clone https://github.com/Aravind-blip/rag-agent-audit.git
cd rag-agent-audit
pip install -e .
```

After a PyPI release, the package can use:

```bash
pip install rag-agent-audit
```

Requires Python 3.10+.

## Quickstart

### 1. Create an audit config

```bash
rag-agent-audit init > audit.yaml
```

### 2. Run in mock mode (no running app needed)

```bash
rag-agent-audit run examples/basic/audit.yaml
```

Output:

```
RAG Agent Audit — basic-rag-security-audit

Passed: 4  Failed: 0  Total: 4

All tests passed.
```

### 3. Run against a real HTTP endpoint

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

## Response mapping

Your app likely returns a different JSON shape than the default. Map it with JSONPath:

```yaml
response_mapping:
  answer: $.result.text
  citations: $.result.sources[*].id
  retrieved_sources: $.debug.retrieved[*].source
  tool_calls: $.tool_calls[*].name
```

## Reports

```bash
rag-agent-audit run audit.yaml                                     # terminal
rag-agent-audit run audit.yaml --format json --output results.json
rag-agent-audit run audit.yaml --format markdown --output report.md
```

## CI integration

Exit code is `0` if all checks pass, `1` if any fail, `2` on config error.

```yaml
# .github/workflows/audit.yml
- name: Run RAG audit
  run: rag-agent-audit run audit.yaml --format markdown --output audit-report.md

- name: Upload report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: audit-report
    path: audit-report.md
```

## Commands

```
rag-agent-audit init               Print a starter audit.yaml
rag-agent-audit validate FILE      Validate config without running tests
rag-agent-audit run FILE           Run an audit suite
  --format terminal|json|markdown
  --output PATH
```

## Limitations

- **Deterministic checks only.** Pattern and source name matching. No LLM judge, no semantic evaluation.
- **Mock mode accuracy.** Mock responses test your check config and CI pipeline, not your actual app.
- **Retrieved sources require debug output.** `forbidden_retrieved_sources` only works if your app exposes retriever output in the response.
- **Not a complete security solution.** Passing tests does not mean your system is secure. Combine with access control, logging, manual review, and threat modeling.

## Roadmap

- **v0.2** — JUnit XML report, Docker image, GitHub Actions summary integration
- **v0.3** — OWASP LLM test packs, prompt injection corpus
- **v0.4** — Agent tool sequence checks, MCP tool policy checks
- **v0.5** — OpenTelemetry export, Langfuse trace import
- **v1.0** — Stable schema, PyPI release, complete docs

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

Apache 2.0. See [LICENSE](LICENSE).
