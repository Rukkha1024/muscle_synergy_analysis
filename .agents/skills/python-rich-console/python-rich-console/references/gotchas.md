# Gotchas

## 1. Human output and machine output are different products

Do not add Rich markup to stdout if another tool consumes that stdout.
Keep a dedicated plain path such as `--json`, `--plain`, or `--no-color`.

## 2. Avoid over-animating non-interactive environments

Live dashboards, status spinners, and animated progress are best in interactive terminals.
When output is piped to a file or CI log, prefer a final table or a small set of stable status lines.

A safe pattern is to check `console.is_terminal` before choosing a highly dynamic display.

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

## 3. `record=True` is opt-in

Only use `Console(record=True)` when you need export or replay.
It is the right choice for `save_html()`, `save_svg()`, `save_text()`, and `export_*()`.
When saving multiple formats from the same recorded buffer, pass `clear=False` until the last save because the `save_*()` helpers clear the record by default.
Do not turn it on everywhere by habit.

## 4. Logging markup is not enabled by default

`RichHandler` does not render Console Markup in log messages by default. That is usually correct because arbitrary square brackets in logs are common.
If you really want markup for a specific message, enable it deliberately.

```python
log.error("[bold red]boom[/]", extra={"markup": True})
```

## 5. User-provided text may contain square brackets

If you print untrusted text with markup enabled, bracketed text may be interpreted as markup.
Use `markup=False` for raw text or escape the string before rendering.

## 6. File output needs width awareness

When writing a Rich `Console` to a file, consider setting a stable `width` so wrapped output is predictable.

```python
with open("report.txt", "wt", encoding="utf-8") as f:
    console = Console(file=f, width=100)
```

## 7. `Live` is not a default answer

Use `Live` only when the display genuinely changes in place. For one loop, prefer `track()`.
For a final summary, prefer `Table`.

## 8. Separate stdout and stderr when it matters

Rich supports `Console(stderr=True)` for an error console. This is useful when normal output and diagnostics should be separated.

## 9. Tests should assert stable text

For unit tests, `io.StringIO` or `console.capture()` keeps snapshot-style checks simple.
Avoid tests that depend on terminal animation timing.
