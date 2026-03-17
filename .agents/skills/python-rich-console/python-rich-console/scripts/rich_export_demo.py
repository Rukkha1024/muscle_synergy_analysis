# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=14.1,<15",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.terminal_theme import MONOKAI



def build_console() -> Console:
    return Console(record=True)



def render_report(console: Console) -> None:
    console.print(Panel.fit("Nightly job report", title="CI"))

    table = Table(title="Pipeline")
    table.add_column("Job")
    table.add_column("Status")
    table.add_column("Seconds")
    table.add_row("lint", "[green]ok[/]", "12")
    table.add_row("tests", "[green]ok[/]", "46")
    table.add_row("deploy", "[yellow]skipped[/]", "0")
    console.print(table)

    console.print(
        Markdown(
            "## Notes\n\n"
            "- Deploy skipped because this run is from a feature branch.\n"
            "- HTML and SVG exports are suitable for artifact storage."
        )
    )



def write_exports(console: Console, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    console.save_html(outdir / "report.html", clear=False)
    console.save_svg(outdir / "report.svg", theme=MONOKAI, clear=False)
    console.save_text(outdir / "report.txt", clear=False)



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Rich output to HTML, SVG, and text.")
    parser.add_argument(
        "--outdir",
        default="rich-export",
        help="Directory where report.html, report.svg, and report.txt are written.",
    )
    return parser



def main() -> None:
    args = build_parser().parse_args()
    outdir = Path(args.outdir)
    console = build_console()
    render_report(console)
    write_exports(console, outdir)
    console.print(f"[bold green]Wrote exports to[/] {outdir}")


if __name__ == "__main__":
    main()
