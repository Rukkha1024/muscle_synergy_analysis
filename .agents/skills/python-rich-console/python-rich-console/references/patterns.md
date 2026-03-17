# Common Refactor Patterns

## Pattern A: print-heavy script -> structured console output

When a script uses many `print()` calls:

1. introduce one shared `Console()`
2. keep the existing control flow
3. replace only user-visible output first
4. convert aligned text blocks to `Table`
5. convert success/error callouts to `Panel.fit()` or styled `console.print()`

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def show_results(rows: list[tuple[str, str]]) -> None:
    table = Table(title="Run summary")
    table.add_column("Step")
    table.add_column("Status")
    for step, status in rows:
        table.add_row(step, status)
    console.print(table)
    console.print(Panel.fit("Done", title="Status"))
```

## Pattern B: long loop -> progress bar

If there is one obvious loop, start with `track()`.
Only move to `Progress` when you need multiple tasks or custom columns.

```python
from rich.progress import track

for path in track(paths, description="Uploading..."):
    upload(path)
```

## Pattern C: existing logging -> RichHandler

If the code already uses `logging`, preserve that structure.
Replace handler setup rather than sprinkling extra prints.

```python
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[RichHandler()],
)
log = logging.getLogger("app")
```

## Pattern D: better exceptions for developer tools

Install rich tracebacks as early as practical in internal tools, dev scripts, and CLIs where developers benefit from better error visibility.

```python
from rich.traceback import install

install(show_locals=True)
```

For a handled exception:

```python
from rich.console import Console

console = Console()

try:
    do_work()
except Exception:
    console.print_exception(show_locals=True)
```

## Pattern E: dual-path human vs machine output

Treat machine-readable output as a first-class path, not a fallback.

```python
import json
from rich.console import Console
from rich.table import Table

console = Console()


def render(rows: list[dict[str, object]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
        return

    table = Table(title="Jobs")
    table.add_column("Job")
    table.add_column("Result")
    for row in rows:
        table.add_row(str(row["job"]), str(row["result"]))
    console.print(table)
```

## Pattern F: export terminal output as artifacts

When the terminal render itself is an artifact, create the console with `record=True` and save the result.

```python
from rich.console import Console
from rich.panel import Panel

console = Console(record=True)
console.print(Panel.fit("Build complete", title="CI"))
console.save_html("report.html", clear=False)
console.save_svg("report.svg", clear=False)
console.save_text("report.txt", clear=False)
```
