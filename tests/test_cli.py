"""
CLI integration tests using Typer's CliRunner.

Content assertions are safe for commands that use direct print() output
(init to stdout, run --format json/markdown to stdout or file). For Rich
console output (validate, run terminal, inspect), only exit codes are
checked — Rich's module-level stdout reference isn't patched by CliRunner.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from rag_agent_audit.cli import app

runner = CliRunner()
_EXAMPLES = Path(__file__).parent.parent / "examples"


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Typer injects the app name and all registered sub-commands into --help
    assert "init" in result.output
    assert "validate" in result.output
    assert "run" in result.output
    assert "inspect" in result.output


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_basic_example() -> None:
    config = _EXAMPLES / "basic" / "audit.yaml"
    result = runner.invoke(app, ["validate", str(config)])
    assert result.exit_code == 0


def test_validate_missing_file() -> None:
    result = runner.invoke(app, ["validate", "/nonexistent/path/audit.yaml"])
    assert result.exit_code == 1


def test_validate_invalid_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    # Valid YAML but missing required 'suite' and 'tests' fields
    bad.write_text("not_a_suite_key: true\n", encoding="utf-8")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def test_run_basic_example() -> None:
    config = _EXAMPLES / "basic" / "audit.yaml"
    result = runner.invoke(app, ["run", str(config)])
    assert result.exit_code == 0


def test_run_format_json_to_stdout() -> None:
    """run --format json without --output prints raw JSON to stdout."""
    config = _EXAMPLES / "basic" / "audit.yaml"
    result = runner.invoke(app, ["run", str(config), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["suite"] == "basic-rag-security-audit"
    assert data["summary"]["total"] == 4
    assert data["summary"]["passed"] == 4
    assert data["summary"]["failed"] == 0


def test_run_format_json_to_file(tmp_path: Path) -> None:
    config = _EXAMPLES / "basic" / "audit.yaml"
    output = tmp_path / "report.json"
    result = runner.invoke(
        app, ["run", str(config), "--format", "json", "--output", str(output)]
    )
    assert result.exit_code == 0
    assert output.exists()
    data = json.loads(output.read_text())
    assert data["suite"] == "basic-rag-security-audit"
    assert data["summary"]["passed"] == 4


def test_run_format_markdown_to_stdout() -> None:
    """run --format markdown without --output prints Markdown to stdout."""
    config = _EXAMPLES / "basic" / "audit.yaml"
    result = runner.invoke(app, ["run", str(config), "--format", "markdown"])
    assert result.exit_code == 0
    assert "basic-rag-security-audit" in result.output


def test_run_format_markdown_to_file(tmp_path: Path) -> None:
    config = _EXAMPLES / "basic" / "audit.yaml"
    output = tmp_path / "report.md"
    result = runner.invoke(
        app, ["run", str(config), "--format", "markdown", "--output", str(output)]
    )
    assert result.exit_code == 0
    assert output.exists()
    assert "basic-rag-security-audit" in output.read_text()


def test_run_unknown_format() -> None:
    config = _EXAMPLES / "basic" / "audit.yaml"
    result = runner.invoke(app, ["run", str(config), "--format", "xml"])
    assert result.exit_code == 2


def test_run_failing_suite(tmp_path: Path) -> None:
    """A suite with a failing must_contain check exits 1."""
    config = tmp_path / "failing.yaml"
    config.write_text(
        textwrap.dedent("""\
            suite: failing-suite
            mode: mock
            tests:
              - name: will-fail
                question: "test"
                mock_response:
                  answer: "wrong answer"
                must_contain:
                  - "correct answer"
        """),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["run", str(config)])
    assert result.exit_code == 1


def test_run_missing_config() -> None:
    result = runner.invoke(app, ["run", "/nonexistent/path/audit.yaml"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_init_basic_to_stdout() -> None:
    """init basic without --output prints raw YAML — uses direct print()."""
    result = runner.invoke(app, ["init", "basic"])
    assert result.exit_code == 0
    assert "suite:" in result.output
    assert "mode: mock" in result.output
    assert "mock_response:" in result.output


def test_init_fastapi_to_stdout() -> None:
    result = runner.invoke(
        app, ["init", "fastapi", "--endpoint", "http://localhost:8000/chat"]
    )
    assert result.exit_code == 0
    assert "mode: http" in result.output
    assert "endpoint: http://localhost:8000/chat" in result.output


def test_init_basic_to_file(tmp_path: Path) -> None:
    output = tmp_path / "audit.yaml"
    result = runner.invoke(app, ["init", "basic", "--output", str(output)])
    assert result.exit_code == 0
    assert output.exists()


def test_init_flowise_to_file(tmp_path: Path) -> None:
    output = tmp_path / "flowise.yaml"
    result = runner.invoke(
        app,
        [
            "init",
            "flowise",
            "--endpoint",
            "http://localhost:3000/api/v1/prediction/test",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()
    import yaml
    data = yaml.safe_load(output.read_text())
    assert data["mode"] == "http"
    assert data["endpoint"] == "http://localhost:3000/api/v1/prediction/test"


def test_init_does_not_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "audit.yaml"
    output.write_text("existing content", encoding="utf-8")
    result = runner.invoke(app, ["init", "basic", "--output", str(output)])
    assert result.exit_code == 1
    assert output.read_text() == "existing content"


def test_init_force_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "audit.yaml"
    output.write_text("existing content", encoding="utf-8")
    result = runner.invoke(app, ["init", "basic", "--output", str(output), "--force"])
    assert result.exit_code == 0
    assert output.read_text() != "existing content"
    assert "suite:" in output.read_text()


def test_init_unknown_template() -> None:
    result = runner.invoke(app, ["init", "nonexistent"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# inspect (mocked httpx.post — no real network calls)
# ---------------------------------------------------------------------------


def test_inspect_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 response with a text field exits 0."""
    payload = {"text": "Hello!", "chatId": "abc", "sessionId": "xyz"}
    mock_resp = httpx.Response(
        200,
        content=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: mock_resp)
    result = runner.invoke(
        app, ["inspect", "--endpoint", "http://localhost:3000/test", "--question", "Say hello"]
    )
    assert result.exit_code == 0


def test_inspect_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_connect(*a: Any, **kw: Any) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "post", raise_connect)
    result = runner.invoke(app, ["inspect", "--endpoint", "http://localhost:1/nope"])
    assert result.exit_code == 1


def test_inspect_http_500(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_resp = httpx.Response(
        500,
        content=b'{"error": "internal server error"}',
        headers={"content-type": "application/json"},
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: mock_resp)
    result = runner.invoke(app, ["inspect", "--endpoint", "http://localhost:9999/broken"])
    assert result.exit_code == 1


def test_inspect_missing_endpoint() -> None:
    """--endpoint is required; missing it is a usage error (exit 2)."""
    result = runner.invoke(app, ["inspect"])
    assert result.exit_code == 2
