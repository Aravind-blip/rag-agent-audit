# Contributing to rag-agent-audit

## How to contribute

1. Pick an existing issue or open a new one.
2. Comment on the issue before starting significant work. This avoids duplicate effort and lets the maintainer flag design concerns early.
3. Fork the repo and create a feature branch: `git checkout -b add-junit-report`
4. Add tests for any behavior change. PRs without tests for new checks or features will not be merged.
5. Run `pytest` and `ruff check src tests` before opening a PR.
6. Open a PR with a clear description and test plan.

## Pull request requirements

- Keep PRs focused on one thing.
- Add or update tests for user-facing changes.
- Update docs for user-facing changes.
- Do not include unrelated formatting changes.
- Do not add new dependencies without discussion in an issue first.

## Local setup

```bash
git clone https://github.com/Aravind-blip/rag-agent-audit.git
cd rag-agent-audit
pip install -e ".[dev]"
pytest
ruff check src tests
```

## Good first issues

Look for issues labeled `good first issue`. These are scoped tasks where the design is already settled and the implementation is straightforward.

If you open a PR on a good first issue, the maintainer will review it promptly. If you don't hear back within a week, comment on the PR.

## Adding a new check

1. Add a function in `src/rag_agent_audit/checks/`.
2. Add the check field to `AuditTestCase` in `config.py`.
3. Register it in `checks/__init__.py` inside `run_checks()`.
4. Add tests in `tests/test_<check_name>.py`.
5. Update the README check table.

## Adding a new adapter

1. Subclass `BaseAdapter` in `src/rag_agent_audit/adapters/`.
2. Implement `send_request(test: AuditTestCase) -> NormalizedResponse`.
3. Wire it into the `run` command in `cli.py` if it needs a new mode.
4. Add tests using a mock or recorded response.
5. Add an example in `examples/`.

## Code style

- Python 3.10+, type hints throughout.
- `ruff` for linting. Run `ruff check src tests` before committing.
- Keep functions small and focused.
- Error messages should tell the user what to fix, not just what went wrong.

## Commit messages

Use conventional commits format:

```
feat: add JUnit XML report output
fix: handle empty citations list in expected_sources check
docs: add HTTP adapter example
test: add fallback check edge cases
```

## Questions

Open a GitHub issue with the `question` label.
