"""Terminal report using Rich for readable CI output."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table

from rag_agent_audit.result import TestResult

_COMPACT_MAX_LEN: int = 120


def _compact_message(message: str, max_len: int = _COMPACT_MAX_LEN) -> str:
    """Return a single-line summary of a (potentially multi-line) check message.

    Skips the "Check failed: …" header line and blank lines, then joins the
    first two remaining content lines.  Truncates at *max_len* characters.
    """
    content_lines = [
        line.strip()
        for line in message.splitlines()
        if line.strip() and not line.strip().startswith("Check failed:")
    ]
    detail = " ".join(content_lines[:2])
    if len(detail) > max_len:
        return detail[:max_len] + "..."
    return detail or message.strip()


def _print_full_diagnostics(results: list[TestResult], console: Console) -> None:
    """Print full check messages below the summary table, grouped by test name."""
    console.print("[bold]Failed test details:[/bold]")
    console.print()

    for result in results:
        if result.passed:
            continue

        console.print(f"[bold]{result.test_name}[/bold]")

        if result.error:
            console.print("  [dim]adapter error[/dim]")
            console.print(f"    {result.error}")
            console.print()
            continue

        for cr in result.check_results:
            if not cr.passed:
                console.print(f"  [cyan]{cr.check_name}[/cyan]")
                for line in cr.message.splitlines():
                    console.print(f"    {line}" if line else "")
                console.print()

        console.print()


def print_terminal_report(
    suite_name: str,
    results: list[TestResult],
    console: Console | None = None,
) -> None:
    """Print a Rich terminal report.

    When all tests pass, shows a compact summary.
    When any test fails, shows a compact table followed by a full-diagnostics
    section so long messages do not crowd the table.

    An optional *console* argument lets callers (and tests) capture output.
    """
    _console = console or Console()

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    _console.print()
    _console.print(f"[bold]RAG Agent Audit — {suite_name}[/bold]")
    _console.print(
        f"Passed: [green]{passed}[/green]  Failed: [red]{failed}[/red]  Total: {total}"
    )
    _console.print()

    if failed == 0:
        _console.print("[green]All tests passed.[/green]")
        return

    # ── Compact summary table ──────────────────────────────────────────────
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Test", style="white")
    table.add_column("Check", style="cyan")
    table.add_column("Result", style="white")
    table.add_column("Detail", style="dim")

    for result in results:
        if result.error:
            table.add_row(
                result.test_name,
                "adapter",
                "[red]ERROR[/red]",
                result.error,
            )
            continue
        for cr in result.check_results:
            if not cr.passed:
                table.add_row(
                    result.test_name,
                    cr.check_name,
                    "[red]FAIL[/red]",
                    _compact_message(cr.message),
                )

    _console.print(table)

    # ── Full diagnostics section ───────────────────────────────────────────
    _print_full_diagnostics(results, _console)
