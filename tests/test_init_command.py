"""Tests for the init command (run_init) and template builders."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rag_agent_audit.config import load_suite
from rag_agent_audit.init_command import InitError, run_init
from rag_agent_audit.templates import SUPPORTED_TEMPLATES, get_template

# ---------------------------------------------------------------------------
# Template content tests
# ---------------------------------------------------------------------------


def test_basic_template_is_valid_yaml() -> None:
    content = get_template("basic")
    data = yaml.safe_load(content)
    assert data["mode"] == "mock"
    assert len(data["tests"]) >= 1


def test_flowise_template_is_valid_yaml() -> None:
    content = get_template("flowise", "http://localhost:3000/api/v1/prediction/test")
    data = yaml.safe_load(content)
    assert data["mode"] == "http"
    assert data["endpoint"] == "http://localhost:3000/api/v1/prediction/test"
    assert data["response_mapping"]["answer"] == "$.text"


def test_fastapi_template_is_valid_yaml() -> None:
    content = get_template("fastapi", "http://localhost:8000/chat")
    data = yaml.safe_load(content)
    assert data["mode"] == "http"
    assert data["endpoint"] == "http://localhost:8000/chat"
    assert data["response_mapping"]["answer"] == "$.answer"


def test_flowise_uses_default_endpoint_when_none() -> None:
    content = get_template("flowise")
    data = yaml.safe_load(content)
    assert "localhost:3000" in data["endpoint"]


def test_fastapi_uses_default_endpoint_when_none() -> None:
    content = get_template("fastapi")
    data = yaml.safe_load(content)
    assert "localhost:8000" in data["endpoint"]


def test_get_template_raises_on_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown template"):
        get_template("nonexistent")


def test_supported_templates_contains_expected() -> None:
    assert {"basic", "flowise", "fastapi"} == SUPPORTED_TEMPLATES


# ---------------------------------------------------------------------------
# run_init: stdout path (output=None)
# ---------------------------------------------------------------------------


def test_run_init_basic_stdout() -> None:
    content = run_init("basic", None, None, False)
    data = yaml.safe_load(content)
    assert data["mode"] == "mock"


def test_run_init_flowise_stdout() -> None:
    content = run_init("flowise", None, "http://localhost:3000/test", False)
    data = yaml.safe_load(content)
    assert data["endpoint"] == "http://localhost:3000/test"


def test_run_init_fastapi_stdout() -> None:
    content = run_init("fastapi", None, "http://localhost:8000/chat", False)
    data = yaml.safe_load(content)
    assert data["mode"] == "http"


def test_run_init_unknown_template_raises() -> None:
    with pytest.raises(InitError, match="Unknown template"):
        run_init("unknown", None, None, False)


# ---------------------------------------------------------------------------
# run_init: file-write path
# ---------------------------------------------------------------------------


def test_run_init_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "audit.yaml"
    run_init("basic", output, None, False)
    assert output.exists()
    suite = load_suite(output)
    assert suite.mode == "mock"


def test_run_init_does_not_overwrite_without_force(tmp_path: Path) -> None:
    output = tmp_path / "audit.yaml"
    output.write_text("existing content", encoding="utf-8")
    with pytest.raises(InitError, match="already exists"):
        run_init("basic", output, None, False)
    assert output.read_text() == "existing content"


def test_run_init_overwrites_with_force(tmp_path: Path) -> None:
    output = tmp_path / "audit.yaml"
    output.write_text("existing content", encoding="utf-8")
    run_init("basic", output, None, force=True)
    suite = load_suite(output)
    assert suite.mode == "mock"


def test_run_init_creates_parent_dirs(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "deep" / "audit.yaml"
    run_init("basic", output, None, False)
    assert output.exists()


# ---------------------------------------------------------------------------
# Generated configs pass load_suite validation
# ---------------------------------------------------------------------------


def test_basic_template_passes_validation(tmp_path: Path) -> None:
    output = tmp_path / "basic.yaml"
    run_init("basic", output, None, False)
    suite = load_suite(output)
    assert len(suite.tests) >= 1
    assert all(t.mock_response is not None for t in suite.tests)


def test_flowise_template_passes_validation(tmp_path: Path) -> None:
    output = tmp_path / "flowise.yaml"
    run_init("flowise", output, "http://localhost:3000/api/v1/prediction/test", False)
    suite = load_suite(output)
    assert suite.mode == "http"
    assert suite.endpoint == "http://localhost:3000/api/v1/prediction/test"
    assert len(suite.tests) >= 1


def test_fastapi_template_passes_validation(tmp_path: Path) -> None:
    output = tmp_path / "fastapi.yaml"
    run_init("fastapi", output, "http://localhost:8000/chat", False)
    suite = load_suite(output)
    assert suite.mode == "http"
    assert suite.endpoint == "http://localhost:8000/chat"
    assert len(suite.tests) >= 1
