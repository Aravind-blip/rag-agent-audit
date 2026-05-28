"""
Business logic for the `rag-agent-audit init` command.

Separated from cli.py so it can be tested without invoking the CLI layer.
"""

from __future__ import annotations

from pathlib import Path

from rag_agent_audit.templates import SUPPORTED_TEMPLATES, get_template


class InitError(Exception):
    """Raised for recoverable user-facing errors during init."""


def run_init(
    template: str,
    output: Path | None,
    endpoint: str | None,
    force: bool,
) -> str:
    """Generate a starter audit config and optionally write it to *output*.

    Returns the YAML content string.
    Raises InitError on recoverable user errors (bad template, file exists).
    """
    if template not in SUPPORTED_TEMPLATES:
        raise InitError(
            f"Unknown template '{template}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_TEMPLATES))}"
        )

    yaml_content = get_template(template, endpoint)

    if output is None:
        return yaml_content

    if output.exists() and not force:
        raise InitError(
            f"File already exists: {output}\n"
            "Use --force to overwrite."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml_content, encoding="utf-8")
    return yaml_content
