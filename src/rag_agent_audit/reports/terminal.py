"""Terminal report using Rich for readable CI output."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table

from rag_agent_audit.result import TestResult


def print_terminal_report(suite_name: str, results: list[TestResult]) -> None:
    console = Console()

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    console.print()
    console.print(f"[bold]RAG Agent Audit — {suite_name}[/bold]")
    console.print(f"Passed: [green]{passed}[/green]  Failed: [red]{failed}[/red]  Total: {total}")
    console.print()

    if failed == 0:
        console.print("[green]All tests passed.[/green]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Test", style="white")
    table.add_column("Check", style="cyan")
    table.add_column("Result", style="white")
    table.add_column("Detail", style="dim")

    for result in results:
        if result.error:
            table.add_row(result.test_name, "adapter", "[red]ERROR[/red]", result.error)
            continue

        for cr in result.check_results:
            if not cr.passed:
                table.add_row(
                    result.test_name,
                    cr.check_name,
                    "[red]FAIL[/red]",
                    cr.message,
                )

    console.print(table)
