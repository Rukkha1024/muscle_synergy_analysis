---
name: excel-xlwings-workflow
description: >-
  Automate and validate Excel workbook tasks in this repository. In WSL or
  headless Linux environments, default to openpyxl; use xlwings only when the
  active environment actually supports desktop Excel automation. Use when
  creating/updating `.xlsx` or `.xlsm` files, writing formulas, filling
  ranges, or generating Excel reports. Always reopen the output workbook to
  verify formula/function errors and unexpected blank cells, minimize sheet
  count, and document every Excel Table with a `table_guide` sheet. In
  `analysis/` workflows tied to statistical or aggregation exploration, prefer
  `.py` for Excel generation while allowing `.ipynb` for exploration.
---

# Excel Xlwings Workflow

## Non-Negotiable Rules

- In this repository's common WSL/headless environment, default to `openpyxl` for workbook generation and validation.
- Use `xlwings` only when the active environment actually supports desktop Excel automation and the task benefits from native Excel behavior.
- If `xlwings` is unavailable or the current environment cannot automate a desktop Excel session, explicitly note that constraint and continue with `openpyxl`.
- Do not use `pandas.ExcelWriter` or shell-only alternatives as the primary Excel engine unless the user explicitly overrides.
- Default output workbook format to `.xlsx` (switch to `.xlsm` only when the user explicitly needs macros).
- Unless there is a specific reason not to, store written data as **Text** in Excel.
  - Applies when the task is “plain text entry” (labels, IDs, codes, keys, categorical fields) rather than numeric computation or Excel formulas.
  - Rationale: prevents Excel auto-coercion (dropping leading zeros, scientific notation, date auto-parsing).
  - Implementation (xlwings): set the target range/column `number_format` to `"@"` **before** writing values, and write values as strings (`str(...)`) when appropriate.
  - Exception: do not force **Text** format for columns that must remain numeric for calculation/charting/statistics; keep those as numeric formats.
- For `analysis/` tasks in statistical-analysis or aggregation contexts:
  - Prefer `.ipynb` for exploratory analysis/aggregation attempts.
  - Prefer `.py` scripts for final Excel workbook generation.
  - Apply this as a context-specific preference, not as a global hard rule for every workflow.
- Keep sheet count minimal. Default to 2 sheets unless the user requests otherwise:
  - one data sheet (for example `tables`)
  - one metadata sheet `table_guide`
- If the workbook is for human interpretation rather than machine-only export, it may add multiple data sheets as long as each sheet clearly explains itself.
- For audit or diagnostics workbooks that include a `summary` sheet:
  - place a short `table reading guide` block above the first table
  - include one worked example that walks through the main interpretation path using the actual column names
  - do not leave the user to infer how `selected`, `raw`, or `detail` tables connect to each other
- Do not limit explanation blocks to `summary` only when the workbook has important detail sheets.
  - Each important table sheet should include a short guide block above the table.
  - The guide block should include `purpose`, `key columns`, and at least one worked example.
  - In this repository, worked examples should be written in Korean unless the user explicitly asks otherwise.
- Write user-facing outputs as Excel Tables (`ListObject`) rather than loose ranges whenever feasible.
- `table_guide` is mandatory when tables are generated. Each table must have a human-readable description.
- For interpretation workbooks, `table_guide` should act as a reading index, not just a raw inventory.
  - Prefer adding a `column_guide` field or equivalent text that explains what the main columns mean.
- Run commands in Windows `PowerShell` or `cmd` syntax only when the environment supports Windows Excel automation. In non-Windows or headless environments, document the limitation and use the available Python-based fallback path.
- When writing plain labels via `xlwings`, do not start cell text with `=` (for example avoid `=== ... ===`).
  - Reason: Excel interprets leading `=` as a formula and may throw COM error `0x800A03EC`/`-2146827284`.
  - Use non-`=` prefixes for section titles (for example `[section] ...`).

## Standard Workflow

1. Confirm workbook path, required outputs, and minimal sheet design.
2. In `analysis/` statistical or aggregation workflows, use `.ipynb` for exploration when needed.
3. Define table inventory first (table name, target sheet, start cell, and description).
4. Implement final Excel-generation logic in a `.py` script with `xlwings` when available; otherwise use an explicit `openpyxl` fallback and record why.
5. Create Excel Tables for outputs, and preserve formulas/formatting where needed.
6. Add sheet-level guide blocks for human-facing interpretation sheets.
7. Populate `table_guide` with per-table descriptions and concise column-reading help.
8. Save workbook and close handles (`wb.close()`, app context exit).
9. Reopen the saved workbook and run validation checks.
10. Open the saved workbook in Excel UI once for visual QA when the environment supports it. If not, record that the visual QA step was skipped because desktop Excel automation was unavailable.
11. If any issue is found, fix and rerun steps 4 to 10.

## Sheet and Table Rules

- Prefer one consolidated data sheet unless data volume or user requirements justify more.
- Use stable table names, for example `tbl_<domain>_<scope>`.
- Avoid duplicate/empty sheets and scattered unstructured ranges.
- If a sheet exists primarily to expose one important table, place the table on that sheet and explain the sheet in-place instead of forcing the user to cross-reference another sheet first.
- If a workbook contains both summary and detail tables, the summary sheet should explain:
  - what each key selection field means
  - how to move from the summary table to the detailed evidence table
  - one concrete example row or scenario
- Required `table_guide` columns:
  - `table_name`
  - `sheet_name`
  - `table_range`
  - `description`
  - `key_columns`
  - `column_guide` (recommended for interpretation workbooks)
  - `notes` (optional)
- `description` should explain what the table represents and how to interpret it in one short sentence.
- `column_guide` should briefly explain what the main columns mean, using the exact column names where possible.

## Required Post-Save Validation

Run every check after reopening the output workbook:

- Formula/function error check:
  - Fail if a cell value is one of `#DIV/0!`, `#N/A`, `#NAME?`, `#NULL!`, `#NUM!`, `#REF!`, `#VALUE!`.
- Broken formula check:
  - Fail if required formula cells are missing formulas.
  - Fail if formula text contains broken references (for example, `#REF!`).
- Blank-cell check:
  - Define business-critical required ranges first.
  - Fail if required cells are empty (`None` or empty string after trim).
- Table integrity check:
  - Fail if expected tables are missing.
  - Fail if `table_guide` is missing.
  - Fail if any table in workbook lacks a matching `table_guide` row.
  - Fail if `description` is blank in `table_guide`.
  - For interpretation workbooks, fail if the expected sheet-level guide labels (for example `purpose`, `key columns`, `example`) are missing on important sheets.
- Record a validation summary:
  - workbook path, sheet/range scanned, issue counts, pass/fail.

- Label safety check (xlwings write path):
  - Fail if any intended plain-label string starts with `=`.
  - Fix by rewriting label text to avoid a leading `=` before writing to cells.
- Engine disclosure check:
  - In WSL/headless environments, record that `openpyxl` was the default engine.
  - If `xlwings` was not used because desktop Excel automation was unavailable, say so explicitly.
  - Record which validation steps were still executed and which Excel UI checks were skipped.

## Validation Snippet (openpyxl default)

```python
from openpyxl import load_workbook

ERROR_TOKENS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}

def is_blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")

def validate_book(path, required_ranges):
    issues = {"errors": [], "blanks": [], "tables": []}
    wb = load_workbook(path)
    try:
        for sheet_name, addr in required_ranges:
            sheet = wb[sheet_name]
            for row in sheet[addr]:
                for cell in row:
                    value = cell.value
                    if isinstance(value, str) and value in ERROR_TOKENS:
                        issues["errors"].append((sheet_name, cell.coordinate, value))
                    if is_blank(value):
                        issues["blanks"].append((sheet_name, cell.coordinate))

        if "table_guide" not in wb.sheetnames:
            issues["tables"].append(("table_guide", "missing"))
    finally:
        wb.close()
    return issues
```

## Formatting Snippet: Force Text Format for Plain-Text Columns (openpyxl)

Use this when you are writing IDs/codes/labels (not formulas and not numeric analytics columns).

```python
def write_text_cell(cell, value):
    cell.number_format = "@"
    cell.value = "" if value is None else str(value)
```

## Command Templates (PowerShell/cmd)

NOTE: `scripts/excel_job.py` is a placeholder example path (this repo may not include that file). Replace it with your actual Excel-generation script under `scripts/`.

PowerShell:
- `conda run -n cuda python -c "import sys; print(sys.executable)"`
- `conda run -n cuda python .\scripts\excel_job.py --input ".\input.xlsx" --output ".\output.xlsx"`
- `Start-Process ".\output.xlsx"`

cmd:
- `conda run -n cuda python -c "import sys; print(sys.executable)"`
- `conda run -n cuda python scripts\excel_job.py --input ".\input.xlsx" --output ".\output.xlsx"`
- `start "" ".\output.xlsx"`

## Incident Playbook: xlwings Label Treated as Formula

- Symptom: `pywintypes.com_error` when writing a string label to a cell, often with code `-2146827284` (Excel `0x800A03EC`).
- Typical trigger: label text starts with `=` such as `=== section ===`.
- Root cause: Excel formula parser is invoked for the label string.
- Fix:
  1. Change label text so the first character is not `=`.
  2. Re-run workbook generation and reopen workbook to verify the target sheet is populated.
  3. Keep this as a pre-write checklist item for all xlwings label writes.

## Completion Report Checklist

- Include workbook output path and touched sheets/ranges.
- Include sheet minimization result (final sheet count and rationale if >2).
- Include created table names and whether each has `table_guide` description.
- Include whether each important sheet has its own guide block and Korean worked example.
- Include formula/function error check result.
- Include blank-cell check result for required ranges.
- Confirm the saved file was reopened, and state whether Excel UI visual QA was completed or skipped due to environment limits.
