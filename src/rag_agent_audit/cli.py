"""
CLI entry point for rag-agent-audit.

Commands:
  init         Generate a starter audit.yaml from a template
  inspect      Probe an endpoint and suggest response_mapping
  validate     Validate a config file without running tests
  run          Execute an audit suite
  corpus scan  Scan a directory tree and produce a JSONL corpus manifest
  corpus stats Print statistics from a JSONL corpus manifest
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from rag_agent_audit.adapters.base import BaseAdapter
from rag_agent_audit.adapters.http import HTTPAdapter
from rag_agent_audit.adapters.mock import MockAdapter
from rag_agent_audit.config import load_suite
from rag_agent_audit.corpus import (
    DEFAULT_INCLUDE_EXT_STR,
    compute_stats,
    format_bytes,
    format_stats,
    iter_manifest,
    merge_exclude_dirs,
    parse_include_exts,
    record_to_jsonl,
    scan_corpus,
)
from rag_agent_audit.corpus_generate import (
    DEFAULT_ENDPOINT,
    DEFAULT_MAX_RISKY_TESTS,
    DEFAULT_MAX_SOURCE_TESTS,
    DEFAULT_SUITE_NAME,
    DEFAULT_TENANT_PREFIX_FORMAT,
    generate_tests_yaml,
)
from rag_agent_audit.init_command import InitError, run_init
from rag_agent_audit.inspect_command import inspect_endpoint
from rag_agent_audit.reports.github_summary import append_to_step_summary, build_github_summary
from rag_agent_audit.reports.json_report import build_json_report
from rag_agent_audit.reports.junit import build_junit_report
from rag_agent_audit.reports.markdown import build_markdown_report
from rag_agent_audit.reports.terminal import print_terminal_report
from rag_agent_audit.runner import run_suite
from rag_agent_audit.templates import SUPPORTED_TEMPLATES

app = typer.Typer(
    name="rag-agent-audit",
    help="CI regression testing for RAG apps and AI agents.",
    add_completion=False,
)
corpus_app = typer.Typer(
    name="corpus",
    help="Corpus scanning and inventory commands.",
    add_completion=False,
)
app.add_typer(corpus_app, name="corpus")

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    config: Path = typer.Argument(..., help="Path to audit.yaml"),
    format: str = typer.Option(  # noqa: A002
        "terminal",
        "--format",
        "-f",
        help="Output format: terminal, json, markdown, junit",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to file"),
    github_summary: bool = typer.Option(
        False,
        "--github-summary",
        help="Append a Markdown summary to $GITHUB_STEP_SUMMARY (GitHub Actions).",
    ),
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
    elif format == "junit":
        report_text = build_junit_report(suite.suite, results)
        if output:
            output.write_text(report_text, encoding="utf-8")
            console.print(f"JUnit XML report written to {output}")
        else:
            print(report_text)
    else:
        err_console.print(
            f"[red]Unknown format:[/red] '{format}'. Use: terminal, json, markdown, junit"
        )
        raise typer.Exit(2)

    if github_summary:
        warning = append_to_step_summary(build_github_summary(suite.suite, results))
        if warning:
            err_console.print(f"[yellow]Warning:[/yellow] {warning}")

    if failed > 0:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# corpus scan
# ---------------------------------------------------------------------------


@corpus_app.command("scan")
def corpus_scan(
    root: Path = typer.Argument(..., help="Root directory to scan."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write JSONL manifest to this file (default: stdout).",
    ),
    tenant_from_path: int | None = typer.Option(
        None,
        "--tenant-from-path",
        help="Infer tenant_id from this path-segment index (0 = first directory).",
    ),
    include_ext: str = typer.Option(
        DEFAULT_INCLUDE_EXT_STR,
        "--include-ext",
        help="Comma-separated file extensions to include.",
    ),
    exclude_dir: list[str] | None = typer.Option(
        None,
        "--exclude-dir",
        help="Directory name to exclude (repeatable; added to built-in exclusions).",
    ),
    max_files: int | None = typer.Option(
        None,
        "--max-files",
        help="Stop after this many files (useful for previewing large corpora).",
    ),
) -> None:
    """Scan a directory tree and write a JSONL corpus manifest."""
    if not root.exists():
        err_console.print(f"[red]Error:[/red] Path does not exist: {root}")
        raise typer.Exit(2)
    if not root.is_dir():
        err_console.print(f"[red]Error:[/red] Not a directory: {root}")
        raise typer.Exit(2)

    include_exts = parse_include_exts(include_ext)
    exclude_dirs = merge_exclude_dirs(exclude_dir)

    file_count = 0
    total_bytes = 0

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as fh:
            for record in scan_corpus(
                root,
                include_exts=include_exts,
                exclude_dirs=exclude_dirs,
                tenant_segment=tenant_from_path,
                max_files=max_files,
            ):
                fh.write(record_to_jsonl(record) + "\n")
                file_count += 1
                total_bytes += record.size_bytes
        summary = f"Scanned {file_count} file(s)  ({format_bytes(total_bytes)})"
        console.print(f"[green]✓[/green] {summary}")
        console.print(f"  Written to {output}")
    else:
        for record in scan_corpus(
            root,
            include_exts=include_exts,
            exclude_dirs=exclude_dirs,
            tenant_segment=tenant_from_path,
            max_files=max_files,
        ):
            print(record_to_jsonl(record))
            file_count += 1
            total_bytes += record.size_bytes
        err_console.print(f"Scanned {file_count} file(s)  ({format_bytes(total_bytes)})")


# ---------------------------------------------------------------------------
# corpus stats
# ---------------------------------------------------------------------------


@corpus_app.command("stats")
def corpus_stats(
    manifest: Path = typer.Argument(..., help="Path to JSONL manifest file."),
) -> None:
    """Print statistics from a JSONL corpus manifest."""
    if not manifest.exists():
        err_console.print(f"[red]Error:[/red] Manifest not found: {manifest}")
        raise typer.Exit(2)

    stats = compute_stats(iter_manifest(manifest))
    print(format_stats(stats))


# ---------------------------------------------------------------------------
# corpus generate-tests
# ---------------------------------------------------------------------------


@corpus_app.command("generate-tests")
def corpus_generate_tests(
    manifest: Path = typer.Argument(..., help="Path to JSONL manifest file."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write generated audit YAML to this file (default: stdout).",
    ),
    suite: str = typer.Option(
        DEFAULT_SUITE_NAME,
        "--suite",
        help="Suite name to embed in the generated config.",
    ),
    endpoint: str = typer.Option(
        DEFAULT_ENDPOINT,
        "--endpoint",
        help="Target endpoint URL to embed in the generated config.",
    ),
    max_source_tests: int = typer.Option(
        DEFAULT_MAX_SOURCE_TESTS,
        "--max-source-tests",
        help="Maximum number of source-coverage tests to generate.",
    ),
    max_risky_tests: int = typer.Option(
        DEFAULT_MAX_RISKY_TESTS,
        "--max-risky-tests",
        help="Maximum number of risky-filename tests to generate.",
    ),
    tenant_prefix_format: str = typer.Option(
        DEFAULT_TENANT_PREFIX_FORMAT,
        "--tenant-prefix-format",
        help=(
            "Format string for allowed_source_prefixes."
            " Uses {tenant_id} as the placeholder (e.g. '{tenant_id}/')."
        ),
    ),
) -> None:
    """Generate a starter audit YAML from a JSONL corpus manifest."""
    if not manifest.exists():
        err_console.print(f"[red]Error:[/red] Manifest not found: {manifest}")
        raise typer.Exit(2)

    yaml_str, result = generate_tests_yaml(
        iter_manifest(manifest),
        suite_name=suite,
        endpoint=endpoint,
        max_source_tests=max_source_tests,
        max_risky_tests=max_risky_tests,
        tenant_prefix_format=tenant_prefix_format,
    )

    if result.total_test_count == 0:
        err_console.print(
            "[yellow]Warning:[/yellow] No tests generated."
            " The manifest may be empty or contain no usable records."
        )
        raise typer.Exit(1)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml_str, encoding="utf-8")
        console.print(f"[green]✓[/green] Generated {result.total_test_count} test(s).")
        console.print(
            f"  Source coverage : {result.source_test_count}"
            f"  |  Risky files : {result.risky_test_count}"
            f"  |  Tenant prefix : {result.tenant_prefix_test_count}"
        )
        console.print(f"  Written to {output}")
        console.print(f"  Next: rag-agent-audit validate {output}")
    else:
        # stdout-only path: no extra text — keeps the output pipe-safe.
        print(yaml_str, end="")


if __name__ == "__main__":
    app()
