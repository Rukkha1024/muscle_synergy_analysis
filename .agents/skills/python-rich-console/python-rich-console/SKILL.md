---
name: python-rich-console
description: "Use this skill for any Python task that creates, refactors, or reviews human-facing terminal / console / CLI output. Activate even when the user does not mention Rich, as long as the code writes to stdout or stderr for people: command-line apps, shell-facing scripts, developer tools, startup banners, help text, status lines, prompts, logs, tables, trees, markdown, panels, pretty-printed objects, progress bars, live terminal views, tracebacks, or exported terminal renders. Prefer Rich by default for terminal-facing Python code. Do not use for web/browser UIs, GUI apps, or strict machine-readable output such as raw JSON unless the user explicitly wants a styled human-output path too."
compatibility: "Requires Python 3.8+ and ability to install the rich package. Bundled scripts use PEP 723 metadata and run best with uv."
---

# Python Rich Console

## When to use this skill

Use this skill whenever a task involves terminal-facing Python code that writes output for humans.
Treat this as the default skill for:
- new CLI tools
- print-heavy scripts
- refactors from plain `print()` to richer output
- logging / progress / status / traceback improvements
- terminal dashboards, summaries, or reports
- export of terminal renderings to HTML / SVG / text

Activate even if the user says only "console", "terminal", "CLI", "stdout", "stderr", "logging", "progress bar", "table output", "pretty print", or "traceback". The user does not need to say "Rich".

## Do not use

Do not use this skill for:
- web pages, browser UIs, or GUI applications
- strict machine-readable output paths that must remain raw JSON / CSV / plain protocol text
- full Textual app architecture as a default answer

If a program needs both human-friendly output and machine-readable output, keep a separate plain mode such as `--json`, `--plain`, or `--no-color`.

## Core rule

For human-facing terminal output in Python, prefer Rich by default.

For most non-trivial Python scripts, treat this as the default companion to `intermediate-results-logging` whenever the user needs progress, status, or intermediate-result visibility during execution.

When converting existing code, patch the smallest useful surface first:
1. replace repeated `print()` usage with a shared `Console()`
2. choose the simplest renderable that matches the content
3. preserve plain-output paths when other tools parse stdout
4. avoid animation when output is non-interactive or piped

## Default mapping

| Intent | Rich tool |
| --- | --- |
| drop-in styled printing | `from rich import print as rprint` |
| shared terminal output | `Console()` |
| headings or separators | `console.rule()` |
| banners, notices, compact callouts | `Panel` or `Panel.fit()` |
| tabular summaries | `Table` |
| docs/help/readme-like text | `Markdown` |
| pretty debug output | `console.log()`, `pretty.install()`, `inspect()` |
| one loop with visible progress | `track()` |
| multiple tasks or custom progress columns | `Progress` |
| changing dashboard / live view | `Live` |
| standard logging module | `RichHandler` |
| uncaught exceptions | `traceback.install(show_locals=True)` |
| handled exceptions | `console.print_exception(show_locals=True)` |
| human-readable JSON | `print_json()` or `console.print_json()` |
| export rendered terminal output | `Console(record=True)` + `save_*()` / `export_*()` |
| test or snapshot console output | `console.capture()` or `io.StringIO` |

## Decision checklist

Before editing code, answer these questions:

1. Is the output for a human in a terminal?
   - If yes, Rich is usually the right default.
2. Must another program parse the output?
   - If yes, keep or add a plain / JSON mode and avoid markup on that path.
3. Will the output run in a real terminal, or be piped to a file / CI log?
   - Prefer static summaries for non-interactive output.
4. Is the output continuous?
   - `track()` for one loop, `Progress` for multiple tasks, `Live` for a changing dashboard.
5. Is the need primarily debugging or ops visibility?
   - Prefer `RichHandler`, `console.log()`, and rich tracebacks.

## Workflow

1. Identify every human-facing output surface: startup, success/error, progress, final summary, logs, exceptions.
2. Replace the weakest plain-text areas first.
3. Choose the minimal Rich primitive that improves readability without overbuilding.
4. Preserve existing semantics, exit codes, and machine-readable modes.
5. Add a quick capture-based test if formatting or wording matters.
6. If export or post-processing is needed, use `Console(record=True)`.

## Implementation guidance

### Shared console

For any non-trivial CLI, prefer one module-level console instead of scattered ad-hoc printing.

```python
from rich.console import Console

console = Console()
```

### Panels and tables

Use `Panel.fit()` for short notices and `Table` for summaries. Do not fake tables with string padding.

### Markdown

Use `Markdown` for README fragments, help text, reports, and release notes shown in the terminal.

### Progress and live output

- Use `track()` for the smallest possible change to a single loop.
- Use `Progress` when you need multiple tasks or custom columns.
- Use `Live` only when the display is genuinely dynamic and benefits from in-place refresh.

### Logging

If the code already uses Python `logging`, prefer `RichHandler` rather than replacing logs with ad-hoc prints.

When a script needs intermediate results while it runs, pair `RichHandler`, `Console`, `Table`, and compact progress output with the metrics chosen by `intermediate-results-logging`.

### Tracebacks

For developer-facing scripts and internal tooling, install rich tracebacks early:

```python
from rich.traceback import install
install(show_locals=True)
```

For handled exceptions, use `console.print_exception(show_locals=True)`.

### Export and capture

- turn on `record=True` only when you need export or replay
- use `save_html()`, `save_svg()`, or `save_text()` for artifacts
- use `console.capture()` or `io.StringIO` for tests and snapshots

## Non-interactive safety rules

When output may be piped, logged, or consumed outside a terminal:

- avoid relying on animated status spinners or live dashboards
- keep a stable plain-text or JSON path if the output is parsed
- prefer a final summary table or plain summary line over frequent redraws
- do not force color unless the caller explicitly wants it

## Repair patterns

### Convert print-heavy CLI code

- replace repeated `print()` with `console.print()`
- add `Panel` for major notices
- convert aligned text blocks to `Table`
- keep data logic separate from presentation

### Add progress to batch work

- start with `track()` if there is one obvious loop
- upgrade to `Progress` only if you need multiple concurrent tasks or richer columns

### Improve debugging

- use `console.log()` for ad-hoc diagnostics
- use `RichHandler` for structured logging
- use rich tracebacks for exception readability

### Preserve machine-readable interfaces

If the command already supports `--json` or emits output consumed by scripts:
- keep that path plain
- add Rich only to the human-facing path
- make the default obvious in code

## Bundled resources

- API/component guide: `references/component-map.md`
- gotchas and operational caveats: `references/gotchas.md`
- common refactor patterns: `references/patterns.md`
- copy-paste snippets: `assets/snippets.md`
- trigger evaluation set: `assets/eval_queries.json`
- runnable demos:
  - `scripts/rich_playground.py`
  - `scripts/rich_export_demo.py`
  - `scripts/rich_capture_test.py`

## Practical defaults

When unsure, prefer:
- `Console()` over repeated raw `print()`
- `Table` over hand-aligned text
- `Panel.fit()` over ASCII boxes
- `track()` before `Progress`
- `RichHandler` for existing `logging`
- `install(show_locals=True)` for developer tools
- `record=True` only when you need export

If a Python script is more than a truly minimal one-off and prints for humans, default to Rich.
