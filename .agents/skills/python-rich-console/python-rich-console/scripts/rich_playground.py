# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=14.1,<15",
# ]
# ///

from __future__ import annotations

import argparse
import logging
import time
from typing import Callable

from rich import print_json
from rich.console import Console
from rich.live import Live
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, track
from rich.table import Table
from rich.terminal_theme import MONOKAI
from rich.traceback import install

install(show_locals=True)


RenderDemo = Callable[[Console], None]


def demo_table(console: Console) -> None:
    table = Table(title="Build Results")
    table.add_column("Step")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_row("lint", "[green]ok[/]", "1.2s")
    table.add_row("tests", "[yellow]warn[/]", "4.8s")
    table.add_row("deploy", "[red]failed[/]", "0.7s")
    console.print(table)



def demo_panel(console: Console) -> None:
    console.print(Panel.fit("Release blocked: fix failing deploy step", title="Notice"))



def demo_markdown(console: Console) -> None:
    md = Markdown(
        "# Release Notes\n\n"
        "- Added Rich table output\n"
        "- Improved tracebacks\n"
        "- Introduced progress bars\n"
    )
    console.print(md)



def demo_track(console: Console) -> None:
    for _ in track(range(5), description="Processing..."):
        time.sleep(0.05)
    console.print("[bold green]track() finished[/]")



def demo_progress(console: Console) -> None:
    with Progress(console=console) as progress:
        build_task = progress.add_task("Build", total=50)
        test_task = progress.add_task("Tests", total=80)
        while not progress.finished:
            progress.update(build_task, advance=1)
            progress.update(test_task, advance=2)
            time.sleep(0.03)



def demo_live(console: Console) -> None:
    table = Table(title="Live Queue")
    table.add_column("ID")
    table.add_column("State")
    with Live(table, console=console, refresh_per_second=4, transient=True):
        for index in range(5):
            table.add_row(str(index), "[green]running[/]")
            time.sleep(0.08)
    console.print("[bold green]live demo complete[/]")



def demo_logging(console: Console) -> None:
    logger = logging.getLogger("rich-playground")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = RichHandler(console=console)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.info("Starting demo")
    logger.warning("One warning for visibility")
    logger.error("Example failure message")



def demo_json(console: Console) -> None:
    console.rule("JSON")
    print_json(data={"ok": True, "count": 3, "items": ["a", "b", "c"]})



def demo_exception(console: Console) -> None:
    console.rule("Handled exception")
    try:
        values = [1, 2, 3]
        _ = values[10]
    except Exception:
        console.print_exception(show_locals=True)


DEMO_MAP: dict[str, RenderDemo] = {
    "table": demo_table,
    "panel": demo_panel,
    "markdown": demo_markdown,
    "track": demo_track,
    "progress": demo_progress,
    "live": demo_live,
    "logging": demo_logging,
    "json": demo_json,
    "exception": demo_exception,
}



def run_demo(console: Console, mode: str) -> None:
    if mode == "all":
        ordered_modes = [
            "panel",
            "table",
            "markdown",
            "track",
            "progress",
            "live",
            "logging",
            "json",
            "exception",
        ]
        for name in ordered_modes:
            console.rule(name)
            DEMO_MAP[name](console)
        return

    DEMO_MAP[mode](console)



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Demonstrate common Rich renderables.")
    parser.add_argument(
        "--mode",
        default="all",
        choices=["all", *DEMO_MAP.keys()],
        help="Which demo to run.",
    )
    parser.add_argument("--save-html", help="Optional output path for HTML export.")
    parser.add_argument("--save-svg", help="Optional output path for SVG export.")
    parser.add_argument("--save-text", help="Optional output path for text export.")
    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    record = any([args.save_html, args.save_svg, args.save_text])
    console = Console(record=record)

    run_demo(console, args.mode)

    if args.save_html:
        console.save_html(args.save_html, clear=False)
    if args.save_svg:
        console.save_svg(args.save_svg, theme=MONOKAI, clear=False)
    if args.save_text:
        console.save_text(args.save_text, clear=False)


if __name__ == "__main__":
    main()
