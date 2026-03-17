# Component Map

Use this guide when deciding which Rich primitive to reach for first.

| Situation | Prefer | Why |
| --- | --- | --- |
| Replace a few `print()` calls fast | `from rich import print as rprint` | Smallest drop-in change |
| Reusable console output across a CLI | `Console()` | Centralizes rendering, width, stderr, and capture/export options |
| Section header / separator | `console.rule()` | Cleaner than manual `-----` lines |
| Short alert, result, or banner | `Panel.fit()` | Compact framed message |
| Multi-row summary | `Table` | Proper alignment, headers, and styles |
| README/help/changelog text in terminal | `Markdown` | Rich renders headings, lists, emphasis, and code blocks |
| One loop with progress | `track()` | Minimal code change |
| Multiple tasks / custom columns | `Progress` | Better control over task state |
| Continuously changing status board | `Live` | In-place refresh without flooding scrollback |
| Existing `logging` module | `RichHandler` | Better formatting without discarding logging structure |
| Uncaught exceptions | `traceback.install()` | Rich tracebacks globally |
| Handled exceptions | `console.print_exception()` | Better error reporting in catch blocks |
| Pretty JSON for humans | `print_json()` | Keeps JSON valid while formatting it |
| Export terminal render | `Console(record=True)` | Enables `export_*()` and `save_*()` |
| Snapshot / assertion in tests | `console.capture()` or `io.StringIO` | Lets tests assert against rendered text |

## Human vs machine output

Use Rich for human-facing terminal output. Keep a separate plain path when another program parses stdout.

```python
import json
from rich.console import Console
from rich.table import Table

console = Console()


def emit_report(rows: list[dict[str, object]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
        return

    table = Table(title="Report")
    table.add_column("Name")
    table.add_column("Status")
    for row in rows:
        table.add_row(str(row["name"]), str(row["status"]))
    console.print(table)
```

## Minimal starter patterns

### Shared console

```python
from rich.console import Console

console = Console()
```

### Table

```python
from rich.table import Table


def render_summary(items: list[tuple[str, str]]) -> Table:
    table = Table(title="Summary")
    table.add_column("Step")
    table.add_column("Status")
    for step, status in items:
        table.add_row(step, status)
    return table
```

### Panel

```python
from rich.panel import Panel

console.print(Panel.fit("Deploy failed", title="Notice"))
```

### Markdown

```python
from rich.markdown import Markdown

console.print(Markdown("# Release notes\n\n- Added Rich output"))
```

### Progress

```python
from rich.progress import track

for item in track(work_items, description="Processing..."):
    process(item)
```

### Logging

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

### Tracebacks

```python
from rich.traceback import install

install(show_locals=True)
```

## Escalation path

Start simple and escalate only when needed:

1. `rprint` or `Console.print`
2. `Panel` / `Table` / `Markdown`
3. `track()`
4. `Progress`
5. `Live`
