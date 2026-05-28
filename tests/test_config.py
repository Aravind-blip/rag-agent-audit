"""Tests for config loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from rag_agent_audit.config import load_suite

VALID_MOCK_YAML = textwrap.dedent("""\
    suite: test-suite
    mode: mock

    fallback_patterns:
      - "I could not find"

    tests:
      - name: basic-mock-test
        question: "What is the refund policy?"
        mock_response:
          answer: "30 day refunds."
          citations:
            - source: "refund.pdf"
        expected_sources:
          - "refund.pdf"
""")


def test_valid_mock_config_loads(tmp_path: Path) -> None:
    f = tmp_path / "audit.yaml"
    f.write_text(VALID_MOCK_YAML)
    suite = load_suite(f)
    assert suite.suite == "test-suite"
    assert suite.mode == "mock"
    assert len(suite.tests) == 1
    assert suite.tests[0].name == "basic-mock-test"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_suite(tmp_path / "nonexistent.yaml")


def test_http_mode_without_endpoint_raises(tmp_path: Path) -> None:
    yaml = textwrap.dedent("""\
        suite: bad-config
        mode: http
        tests:
          - name: some-test
            question: "Hello?"
            mock_response:
              answer: "Hi"
    """)
    f = tmp_path / "audit.yaml"
    f.write_text(yaml)
    with pytest.raises(ValueError, match="endpoint"):
        load_suite(f)


def test_mock_mode_missing_mock_response_raises(tmp_path: Path) -> None:
    yaml = textwrap.dedent("""\
        suite: bad-mock
        mode: mock
        tests:
          - name: broken-test
            question: "Hello?"
    """)
    f = tmp_path / "audit.yaml"
    f.write_text(yaml)
    with pytest.raises(ValueError, match="mock_response"):
        load_suite(f)


def test_invalid_test_name_raises(tmp_path: Path) -> None:
    yaml = textwrap.dedent("""\
        suite: test-suite
        mode: mock
        tests:
          - name: "Invalid Name!"
            question: "Hello?"
            mock_response:
              answer: "Hi"
    """)
    f = tmp_path / "audit.yaml"
    f.write_text(yaml)
    with pytest.raises(ValueError, match="lowercase"):
        load_suite(f)


def test_empty_suite_raises(tmp_path: Path) -> None:
    yaml = textwrap.dedent("""\
        suite: empty-suite
        mode: mock
        tests: []
    """)
    f = tmp_path / "audit.yaml"
    f.write_text(yaml)
    with pytest.raises(ValueError, match="at least one test"):
        load_suite(f)


def test_env_var_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_TOKEN", "abc123")
    yaml = textwrap.dedent("""\
        suite: env-test
        mode: mock
        request:
          headers:
            authorization: "Bearer ${TEST_TOKEN}"
        tests:
          - name: env-test-case
            question: "Hello?"
            mock_response:
              answer: "Hi"
    """)
    f = tmp_path / "audit.yaml"
    f.write_text(yaml)
    suite = load_suite(f)
    assert suite.request.headers["authorization"] == "Bearer abc123"


def test_missing_env_var_raises(tmp_path: Path) -> None:
    yaml = textwrap.dedent("""\
        suite: env-missing
        mode: mock
        request:
          headers:
            authorization: "Bearer ${MISSING_VAR}"
        tests:
          - name: some-test
            question: "Hello?"
            mock_response:
              answer: "Hi"
    """)
    f = tmp_path / "audit.yaml"
    f.write_text(yaml)
    with pytest.raises(ValueError, match="MISSING_VAR"):
        load_suite(f)
