# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "rich>=14.1,<15",
# ]
# ///

from __future__ import annotations

import argparse
from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table



def render_summary(console: Console) -> None:
    table = Table(title="Checks")
    table.add_column("Name")
    table.add_column("Result")
    table.add_row("lint", "ok")
    table.add_row("tests", "ok")
    console.print(Panel.fit("Run complete", title="Status"))
    console.print(table)



def via_capture() -> str:
    console = Console()
    with console.capture() as capture:
        render_summary(console)
    return capture.get()



def via_stringio() -> str:
    buffer = StringIO()
    console = Console(file=buffer, width=100)
    render_summary(console)
    return buffer.getvalue()



def assert_contains(rendered: str) -> None:
    required_terms = ["Run complete", "Checks", "lint", "tests"]
    missing = [term for term in required_terms if term not in rendered]
    if missing:
        missing_display = ", ".join(missing)
        raise SystemExit(f"Missing expected terms: {missing_display}\n\n{rendered}")



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Demonstrate capture-based testing of Rich output.")
    parser.add_argument(
        "--mode",
        default="capture",
        choices=["capture", "stringio"],
        help="How to collect rendered output.",
    )
    return parser



def main() -> None:
    args = build_parser().parse_args()
    rendered = via_capture() if args.mode == "capture" else via_stringio()
    assert_contains(rendered)
    print(rendered)
    print("Assertions passed")


if __name__ == "__main__":
    main()
