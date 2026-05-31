# Changelog

All notable changes to this project will be documented in this file.

The format follows the spirit of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses semantic versioning once public releases begin.

## v0.3.0 — Unreleased

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
