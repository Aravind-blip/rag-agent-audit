# Changelog

## v0.8.0 — Unreleased

### Added
- `rag-agent-audit trace import langfuse <file> [--output]` — imports a Langfuse-like JSONL export and writes normalized trace-events JSONL. Supports `id`/`traceId`/`trace_id`, `spanId`/`span_id`/`observation_id`, string and dict `input`/`output` fields, and all audit list fields (`citations`, `retrieved_sources`, `tool_calls`, `approved_tools`).
- `rag-agent-audit trace import otel <file> [--output]` — imports an OpenTelemetry JSONL span export. Extracts audit fields from `attributes` using `rag.input`, `rag.answer`, `rag.citations`, `rag.retrieved_sources`, `agent.tool_calls`, and `agent.approved_tools`. Accepts both list values and comma-separated strings.
- `rag-agent-audit trace stats <file>` — prints statistics from a normalized trace-events file: total events, count by source format, events with tool calls / citations / retrieved sources, and sorted unique values for each.
- `TraceEvent` and `TraceStats` dataclasses in `src/rag_agent_audit/trace_import.py` as the canonical normalized event model.
- Example trace files (`examples/traces/langfuse-traces.jsonl`, `examples/traces/otel-traces.jsonl`) and `examples/traces/README.md` with field mapping tables.

### Notes
- Does not connect to Langfuse, any OpenTelemetry collector, or any network resource.
- Importing trace files does not run audit checks; it only normalizes events for inspection.
- Blank lines are silently ignored; malformed JSON raises `ValueError` with the filename and line number.

---

## v0.7.0 — 2026-06-08

### Added
- `package.yml` CI workflow — builds sdist and wheel on every PR and push to `main`, runs `twine check`, and smoke-tests the installed wheel in a clean virtual environment. Distribution artifacts are uploaded for inspection.
- `publish-testpypi.yml` workflow — manual (`workflow_dispatch`) publish to TestPyPI using Trusted Publishing (OIDC). No API tokens required.
- `publish-pypi.yml` workflow — publishes to PyPI when a GitHub Release is published. Uses Trusted Publishing (OIDC) with a dedicated `pypi` environment for approval gating. Separated into `build` and `publish` jobs so the distribution artifact is inspectable before upload.
- `docs/release.md` — step-by-step release checklist covering version bump, tagging, GitHub Release creation, TestPyPI dry-run, Trusted Publishing setup, and post-release install verification.
- `twine>=5.0.0` added to `[project.optional-dependencies] dev` for local package validation.
- Updated `README.md` Installation section with `pip install rag-agent-audit` and `pipx` instructions; added a Publishing section with a link to the release docs.

---

## v0.6.0 — 2026-06-06

### Added
- `tool_policy` check — enforces three independent sub-rules in a single check result:
  - `allowed_tools` — fails if any called tool is not in an explicit allowlist (test-level field).
  - `forbidden_tool_patterns` — fails if any called tool matches an fnmatch glob pattern (test-level field).
  - `required_approval_tools` — fails if a tool requiring approval was called without appearing in the response's `approved_tools` list; also fails with a configuration error if `approved_tools` is not mapped on the suite.
- `approved_tools` field on `ResponseMapping` (`str | None`, default `None`). When set to a JSONPath expression, the adapter extracts approved tool names from the response. Existing configs without this field continue to work unchanged.
- `allowed_tools`, `required_approval_tools`, and `forbidden_tool_patterns` fields on `AuditTestCase` (all default to empty list). All existing test cases without these fields continue to work unchanged.
- `approved_tools` field on `NormalizedResponse` (`list[str] | None`, default `None`). `None` signals that the mapping was not configured; `[]` signals configured but no approvals present.
- Example audit config (`examples/agent-tool-policy/`) with six mock-mode test cases covering all three sub-rules.

### Notes
- Does not connect to live MCP servers or implement any MCP protocol client.
- `forbidden_tools` (v0.1) and `tool_policy` (v0.6) are independent checks and can be used together.

---

## v0.5.0 — 2026-06-06

### Added
- `known_sources` check — fails if any citation or retrieved source is not present in a JSONL corpus manifest (exact path match). Controlled by `known_sources_manifest` (suite-level path) and `require_known_sources: true` (test-level flag).
- Manifest path resolution: relative paths in `known_sources_manifest` are resolved against the audit YAML file at run time, so the manifest can live next to the config.

---

## v0.4.0 — 2026-05-31

### Added
- `corpus generate-tests` command for generating starter audit YAML from JSONL corpus manifests.
- Source coverage test generation from manifest paths.
- Risky filename test generation for source names containing terms like `secret`, `credential`, `password`, `token`, and `api_key`.
- Tenant-prefix test generation using `allowed_source_prefixes`.
- Deterministic generated YAML output that validates with `rag-agent-audit validate`.

### Notes
- Generated audit tests are starter templates and should be reviewed before running against a live endpoint.
- The command does not read document contents, index files, or run LLM calls.

---
All notable changes to this project will be documented in this file.

The format follows the spirit of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses semantic versioning once public releases begin.

## v0.3.0 — 2026-05-31

### Added
- `tenant_leakage` check — fails if any citation or retrieved source violates `allowed_source_prefixes` (prefix match) or contains a forbidden tenant ID (`forbidden_tenant_ids`, substring match). Both fields default to empty; the check is skipped when neither is configured.
- `corpus scan` command — streams matching files from a directory tree and writes a JSONL manifest (`ScanRecord` per line with path, size, extension, and optional tenant ID).
- `corpus stats` command — reads a JSONL manifest and prints a human-readable inventory: file counts by extension and tenant, duplicate basenames, risky-looking filenames, and largest files.
- Synthetic multi-tenant RAG test pack (`examples/multi-tenant-rag/`) with 12 deterministic test cases covering correct-tenant retrieval, cross-tenant isolation, credential elicitation, prompt injection echo, dangerous tool calls, out-of-corpus fallback, and the new `tenant_leakage` checks.
- OWASP LLM prompt injection test pack (`examples/prompt-injection/`) with 10 test cases targeting prompt injection echo, forbidden tool escalation, and system context leakage.

### Improved
- Terminal report now renders a compact summary table (Detail column capped at ~120 chars) followed by a full-diagnostics "Failed test details" section — long diagnostic messages no longer crowd the table.
- Corpus stats truncates display of duplicate basenames (first 20 groups, 5 paths each) and risky filenames (first 20) with "… and N more" summaries to keep output readable for large corpora.

---

## v0.2.0 — 2026-05-28

### Added
- `init` command for generating starter audit configs from templates (`basic`, `flowise`, `fastapi`).
- `inspect` command for probing a live endpoint, detecting response fields, and suggesting JSONPath mappings.
- JUnit XML report output (`--format junit`) for CI systems that ingest test results directly.
- GitHub Actions step summary support (`--github-summary`) — appends a Markdown table to `$GITHUB_STEP_SUMMARY`.
- Docker image support (`Dockerfile` and `.dockerignore`) — run audits without a local Python environment.

### Improved
- Failure diagnostics: check messages now include a structured detail line, an answer preview, and an actionable suggestion for each failing check type.
- CLI test coverage using Typer's `CliRunner`.

### Notes
- `examples/flowise/` remains a local smoke and security-pattern integration example. It is not a vulnerability claim against Flowise.

---

## 0.1.0 — Unreleased

### Added
- Initial CLI with `init`, `validate`, and `run` commands.
- YAML-based audit suite configuration.
- Mock adapter for local/offline testing.
- HTTP adapter for testing real RAG or agent endpoints.
- JSONPath response mapping for answers, citations, retrieved sources, and tool calls.
- Deterministic checks for expected sources, forbidden sources, forbidden retrieved sources, required text, prohibited text, fallback behavior, and forbidden tool calls.
- Terminal, JSON, and Markdown reports.
- GitHub Actions workflow for linting, tests, and example audit execution.
- Example mock audit suite.
- Contribution and security policy documents.
