"""
Config schema for rag-agent-audit.

Parses and validates audit.yaml files. All fields use strict types
so validation errors are clear and actionable.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Test-case model
# ---------------------------------------------------------------------------

class AuditTestCase(BaseModel):
    name: str
    question: str

    # Mock mode: inline response instead of hitting an endpoint
    mock_response: dict[str, Any] | None = None

    # Per-test headers (merged with suite-level headers)
    headers: dict[str, str] = Field(default_factory=dict)

    # Check definitions
    expected_sources: list[str] = Field(default_factory=list)
    forbidden_sources: list[str] = Field(default_factory=list)
    forbidden_retrieved_sources: list[str] = Field(default_factory=list)
    must_contain: list[str] = Field(default_factory=list)
    must_not_contain: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    should_fallback: bool | None = None
    allowed_source_prefixes: list[str] = Field(default_factory=list)
    forbidden_tenant_ids: list[str] = Field(default_factory=list)
    require_known_sources: bool = False

    @field_validator("name")
    @classmethod
    def name_must_be_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9\-]*$", v):
            raise ValueError(
                f"Test name '{v}' must be lowercase alphanumeric with hyphens "
                f"(e.g. 'block-cross-tenant-citation')."
            )
        return v

    @model_validator(mode="after")
    def mock_or_endpoint_required(self) -> AuditTestCase:
        # Individual tests can rely on suite-level mode; we validate this
        # at suite level. Here we just ensure mock_response is dict if present.
        return self


# ---------------------------------------------------------------------------
# Response mapping model
# ---------------------------------------------------------------------------

class ResponseMapping(BaseModel):
    """JSONPath expressions that map app-specific response fields to
    normalized fields. Supports any JSON shape."""

    answer: str = "$.answer"
    citations: str = "$.citations[*].source"
    retrieved_sources: str = "$.debug.retrieved[*].source"
    tool_calls: str = "$.tool_calls[*].name"


# ---------------------------------------------------------------------------
# Request config (HTTP mode)
# ---------------------------------------------------------------------------

class RequestConfig(BaseModel):
    method: Literal["POST", "GET"] = "POST"
    headers: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Suite defaults
# ---------------------------------------------------------------------------

class SuiteDefaults(BaseModel):
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    retries: int = Field(default=0, ge=0, le=3)
    fail_on_empty_citations: bool = False


# ---------------------------------------------------------------------------
# Top-level suite config
# ---------------------------------------------------------------------------

class AuditSuite(BaseModel):
    suite: str
    mode: Literal["mock", "http"] = "mock"

    # HTTP mode only
    endpoint: str | None = None
    request: RequestConfig = Field(default_factory=RequestConfig)

    response_mapping: ResponseMapping = Field(default_factory=ResponseMapping)
    fallback_patterns: list[str] = Field(default_factory=list)
    defaults: SuiteDefaults = Field(default_factory=SuiteDefaults)

    # Optional: path to a JSONL corpus manifest for the known_sources check.
    # Relative paths are resolved against the audit YAML file at run time.
    known_sources_manifest: str | None = None

    tests: list[AuditTestCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> AuditSuite:
        if self.mode == "http" and not self.endpoint:
            raise ValueError(
                "mode 'http' requires an 'endpoint' field "
                "(e.g. endpoint: http://localhost:8000/api/chat)."
            )
        if self.mode == "mock":
            missing = [t.name for t in self.tests if t.mock_response is None]
            if missing:
                raise ValueError(
                    f"mode 'mock' requires a 'mock_response' on every test. "
                    f"Missing on: {', '.join(missing)}"
                )
        if not self.tests:
            raise ValueError("Suite must define at least one test.")
        return self

    @field_validator("suite")
    @classmethod
    def suite_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("suite name cannot be empty.")
        return v.strip()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_env_vars(text: str) -> str:
    """Replace ${VAR_NAME} placeholders with environment variable values.

    Raises ValueError for any variable that is not set, so secrets are
    never silently skipped.
    """
    def replace(m: re.Match[str]) -> str:
        var = m.group(1)
        val = os.environ.get(var)
        if val is None:
            raise ValueError(
                f"Environment variable '{var}' referenced in config is not set."
            )
        return val

    return _ENV_VAR_RE.sub(replace, text)


def load_suite(path: str | Path) -> AuditSuite:
    """Load and validate an audit.yaml file.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the YAML is invalid or the config fails validation.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = config_path.read_text(encoding="utf-8")

    try:
        raw = _expand_env_vars(raw)
    except ValueError as e:
        raise ValueError(f"Config env expansion failed: {e}") from e

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a YAML mapping, got: {type(data).__name__}")

    from pydantic import ValidationError

    try:
        return AuditSuite.model_validate(data)
    except ValidationError as e:
        # Reformat pydantic errors into readable messages
        lines = [f"Config validation failed in {config_path}:"]
        for err in e.errors():
            loc = " -> ".join(str(p) for p in err["loc"])
            lines.append(f"  [{loc}] {err['msg']}")
        raise ValueError("\n".join(lines)) from e
