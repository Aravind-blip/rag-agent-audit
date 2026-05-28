# Changelog

All notable changes to this project will be documented in this file.

The format follows the spirit of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses semantic versioning once public releases begin.

## 0.1.0 - Unreleased

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
