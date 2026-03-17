# Copy-Paste Snippets

## 1. Starter console module

```python
from rich.console import Console
from rich.traceback import install

install(show_locals=True)
console = Console()
```

## 2. Replace basic prints

```python
from rich.console import Console

console = Console()

console.print("[bold green]Done[/]")
console.print("Wrote", 12, "files")
```

## 3. Compact notice panel

```python
from rich.panel import Panel

console.print(Panel.fit("Release blocked: failing tests", title="Notice"))
```

## 4. Summary table

```python
from rich.table import Table


def make_summary(rows: list[tuple[str, str]]) -> Table:
    table = Table(title="Summary")
    table.add_column("Step")
    table.add_column("Status")
    for step, status in rows:
        table.add_row(step, status)
    return table

console.print(make_summary([("lint", "ok"), ("tests", "failed")]))
```

## 5. Markdown in terminal

```python
from rich.markdown import Markdown

md = Markdown("# Notes\n\n- Added progress\n- Improved traceback")
console.print(md)
```

## 6. Single-loop progress

```python
from rich.progress import track

for item in track(items, description="Processing..."):
    process(item)
```

## 7. Multi-task progress

```python
import time
from rich.progress import Progress

with Progress() as progress:
    download = progress.add_task("Download", total=100)
    upload = progress.add_task("Upload", total=40)

    while not progress.finished:
        progress.update(download, advance=1)
        progress.update(upload, advance=0.4)
        time.sleep(0.05)
```

## 8. Existing logging with RichHandler

```python
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[RichHandler()],
)
log = logging.getLogger("app")
log.info("Starting")
```

## 9. Rich traceback for handled exceptions

```python
try:
    run_job()
except Exception:
    console.print_exception(show_locals=True)
```

## 10. Keep JSON mode plain

```python
import json
from rich.table import Table


def emit(rows: list[dict[str, object]], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(rows, ensure_ascii=False))
        return

    table = Table(title="Jobs")
    table.add_column("Job")
    table.add_column("State")
    for row in rows:
        table.add_row(str(row["job"]), str(row["state"]))
    console.print(table)
```

## 11. Non-interactive fallback

```python
from rich.console import Console
from rich.progress import track

console = Console()

if console.is_terminal:
    for item in track(items, description="Processing..."):
        process(item)
else:
    for item in items:
        process(item)
    console.print(f"Processed {len(items)} items")
```

## 12. Export to HTML / SVG / text

```python
from rich.console import Console
from rich.panel import Panel

console = Console(record=True)
console.print(Panel.fit("Build complete", title="CI"))
console.save_html("report.html", clear=False)
console.save_svg("report.svg", clear=False)
console.save_text("report.txt", clear=False)
```

## 13. Capture output for tests

```python
from rich.console import Console

console = Console()
with console.capture() as capture:
    console.print("[bold green]ok[/]")
rendered = capture.get()
assert "ok" in rendered
```

## 14. Use stderr for errors

```python
from rich.console import Console

error_console = Console(stderr=True)
error_console.print("[bold red]fatal:[/] invalid config")
```
