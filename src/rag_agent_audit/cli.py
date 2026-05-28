"""
CLI entry point for rag-agent-audit.

Commands:
  init      Generate a starter audit.yaml from a template
  inspect   Probe an endpoint and suggest response_mapping
  validate  Validate a config file without running tests
  run       Execute an audit suite
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from rag_agent_audit.adapters.base import BaseAdapter
from rag_agent_audit.adapters.http import HTTPAdapter
from rag_agent_audit.adapters.mock import MockAdapter
from rag_agent_audit.config import load_suite
from rag_agent_audit.init_command import InitError, run_init
from rag_agent_audit.inspect_command import inspect_endpoint
from rag_agent_audit.reports.json_report import build_json_report
from rag_agent_audit.reports.markdown import build_markdown_report
from rag_agent_audit.reports.terminal import print_terminal_report
from rag_agent_audit.runner import run_suite
from rag_agent_audit.templates import SUPPORTED_TEMPLATES

app = typer.Typer(
    name="rag-agent-audit",
    help="CI security regression testing for RAG apps and AI agents.",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


@app.command()
def init(
    template: str = typer.Argument(
        "basic",
        help=f"Template name. Supported: {', '.join(sorted(SUPPORTED_TEMPLATES))}",
    ),
    endpoint: str | None = typer.Option(
        None,
        "--endpoint",
        help="Endpoint URL for http templates (flowise, fastapi).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write config to this file instead of stdout.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite output file if it already exists.",
    ),
) -> None:
    """Generate a starter audit config from a template."""
    try:
        content = run_init(template, output, endpoint, force)
    except InitError as e:
        err_console.print(f"[red]init error:[/red] {e}")
        raise typer.Exit(1) from e

    if output is None:
        print(content, end="")
    else:
        console.print(f"[green]✓[/green] Created audit config: {output}")
        console.print(f"  Template : {template}")
        console.print(f"  Next     : rag-agent-audit validate {output}")
        console.print(f"           : rag-agent-audit run {output}")


@app.command()
def inspect(
    endpoint: str = typer.Option(
        ...,
        "--endpoint",
        help="Endpoint URL to probe (e.g. http://localhost:3000/api/v1/prediction/ID).",
    ),
    question: str = typer.Option(
        "Say hello in one sentence.",
        "--question",
        help="Probe question to send.",
    ),
    timeout: float = typer.Option(
        20.0,
        "--timeout",
        help="Request timeout in seconds.",
    ),
) -> None:
    """Probe an endpoint and suggest a response_mapping for audit.yaml."""
    result = inspect_endpoint(endpoint, question, timeout)

    if not result.success:
        if result.status_code is not None:
            err_console.print("[red]Endpoint returned an error.[/red]")
            err_console.print(f"Status: {result.status_code}")
        else:
            err_console.print("[red]Endpoint not reachable.[/red]")
        if result.error:
            err_console.print(f"Error: {result.error}")
        raise typer.Exit(1)

    console.print("[green]Endpoint responded successfully.[/green]")
    console.print(f"Status: {result.status_code}")

    if result.fields:
        console.print("\nDetected response fields:")
        col_width = max(len(path) for path, _ in result.fields) + 2
        for path, type_label in result.fields:
            console.print(f"  {path:<{col_width}}{type_label}")
    else:
        console.print("\n(No fields detected in response.)")

    if result.suggestions:
        console.print("\nSuggested response_mapping:")
        for field_name, jsonpath in result.suggestions.items():
            console.print(f"  {field_name}: {jsonpath}")
    else:
        console.print("\n(No response_mapping suggestions — response shape is unrecognised.)")


@app.command()
def validate(config: Path = typer.Argument(..., help="Path to audit.yaml")) -> None:
    """Validate a config file and report any errors."""
    try:
        suite = load_suite(config)
        msg = f"Config valid: {len(suite.tests)} test(s) in suite '{suite.suite}'."
        console.print(f"[green]✓[/green] {msg}")
    except (FileNotFoundError, ValueError) as e:
        err_console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def run(
    config: Path = typer.Argument(..., help="Path to audit.yaml"),
    format: str = typer.Option("terminal", "--format", "-f", help="Output format: terminal, json, markdown"),  # noqa: E501
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to file"),
) -> None:
    """Run an audit suite and exit 0 on pass, 1 on failure."""
    try:
        suite = load_suite(config)
    except (FileNotFoundError, ValueError) as e:
        err_console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(2) from e

    adapter: BaseAdapter
    if suite.mode == "mock":
        adapter = MockAdapter(suite.response_mapping)
    else:
        assert suite.endpoint is not None  # validated by config
        adapter = HTTPAdapter(suite.endpoint, suite.request, suite.response_mapping, suite.defaults)

    results = run_suite(suite, adapter)
    failed = sum(1 for r in results if not r.passed)

    if format == "terminal":
        print_terminal_report(suite.suite, results)
    elif format == "json":
        report_text = build_json_report(suite.suite, results)
        if output:
            output.write_text(report_text)
            console.print(f"JSON report written to {output}")
        else:
            print(report_text)
    elif format == "markdown":
        report_text = build_markdown_report(suite.suite, results)
        if output:
            output.write_text(report_text)
            console.print(f"Markdown report written to {output}")
        else:
            print(report_text)
    else:
        err_console.print(f"[red]Unknown format:[/red] '{format}'. Use: terminal, json, markdown")
        raise typer.Exit(2)

    if failed > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
