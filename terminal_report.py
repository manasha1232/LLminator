from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from llminator.reporting.schema import ScanReport


def render_report(report: ScanReport, console: Console) -> None:
    summary = report.summary
    accent = "green" if summary.failed == 0 and summary.errors == 0 else "red"
    console.print(
        Panel(
            f"[bold]{summary.passed} passed[/bold]  •  "
            f"[bold]{summary.failed} failed[/bold]  •  "
            f"{summary.errors} errors  •  {summary.skipped} skipped",
            title=f"Scan complete — {report.target.name}",
            border_style=accent,
        )
    )
    table = Table(border_style="cyan", show_lines=True)
    table.add_column("Engine")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Severity")
    table.add_column("Details")
    colors = {
        "pass": "green",
        "fail": "red",
        "error": "yellow",
        "skipped": "dim",
        "inconclusive": "yellow",
    }
    for result in report.results:
        table.add_row(
            result.engine,
            result.check,
            f"[{colors[result.status]}]{result.status}[/{colors[result.status]}]",
            result.severity,
            result.details,
        )
    console.print(table)
    suggestions = list(
        dict.fromkeys(
            suggestion
            for result in report.results
            for suggestion in result.remediation
        )
    )
    if suggestions:
        rendered = "\n".join(
            f"[cyan]{index}.[/cyan] {suggestion}"
            for index, suggestion in enumerate(suggestions, 1)
        )
        console.print(
            Panel(
                rendered,
                title="Suggested next steps",
                border_style="bright_magenta",
            )
        )
