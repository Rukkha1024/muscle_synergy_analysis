---
name: pingouin-excel-stat-analysis
description: >-
  Build statistical analysis workflows with pingouin and deliver results as
  Excel Tables in minimal-sheet workbooks. Use when users ask for hypothesis
  testing output they plan to review in Excel. In `analysis/` statistical or
  aggregation exploration workflows, prefer `.ipynb` for exploration and use
  `.py` for final Excel generation.
---

# Pingouin Excel Statistical Analysis

## Trigger

- Use for statistical analysis tasks (hypothesis tests, post-hoc tests, and summary tables) where the final deliverable is an Excel workbook.
- Trigger for requests mentioning either `pingouin` or typo variants like `pinguoin`.
- In `analysis/`, if users want to try statistical analysis or aggregation directly, treat notebook-first exploration plus Python-script Excel generation as the preferred pattern.
- For `step` vs `nonstep` EMG rank interpretation workflows in `analysis/`, co-use `analysis-step-nonstep-rank-report` and let that skill drive folder/report structure while this skill owns tests and Excel table rules.
- In this repository, for statistical ranking/hypothesis-result requests (even when users do not explicitly say "Excel"), default deliverables should include:
  - reproducible `.py` analysis code, and
  - an `.xlsx` workbook (`tables` + `table_guide`) for review/validation.

## Non-Negotiable Rules

- Use `pingouin` for statistical testing (`friedman`, `anova`, `pairwise_tests`, and related functions).
- Prefer `polars` for data preparation, then convert to `pandas` only when a statistics API requires it.
- Write Excel outputs with `xlwings` in Windows PowerShell or cmd.
- Use `.xlsx` as the default output format (use `.xlsm` only when macro requirements are explicitly requested).
- For `analysis/` statistical or aggregation tasks, prefer:
  - `.ipynb` for exploratory aggregation/statistical iteration.
  - `.py` for final Excel workbook generation.
  - This is a preferred workflow, not a global hard requirement for every task.
- Save user-facing results as Excel Tables (`ListObject`), not loose ranges.
- Keep sheet count minimal. Default layout:
  - `tables`: all result tables.
  - `table_guide`: metadata and explanation for each table.
- Every output table must have a matching `table_guide` row with a non-empty `description`.

## Table Guide Schema

- `table_name`
- `sheet_name`
- `table_range`
- `description`
- `key_columns`
- `filters_or_notes`

## Workflow

1. Define hypotheses and required output tables before coding.
2. In `analysis/` statistical or aggregation exploration, iterate in `.ipynb` first when useful.
3. Load and clean data in `polars`.
4. Convert only required frames to `pandas`.
5. Compute statistics with `pingouin`.
6. Move final Excel-generation logic into a `.py` script.
7. Write each result block to `tables` and convert ranges to Excel Tables.
8. Populate `table_guide` with interpretation notes.
9. Reopen workbook and validate errors, blanks, and table-guide integrity.

## Validation

- Fail if any cell contains `#DIV/0!`, `#N/A`, `#NAME?`, `#NULL!`, `#NUM!`, `#REF!`, or `#VALUE!`.
- Fail if expected tables are missing.
- Fail if `table_guide` is missing or has blank `description` values.
- Fail if business-critical required ranges are blank.

## Command Templates

NOTE: `scripts/run_stats_report.py` is a placeholder example path (this repo may not include that file). Replace it with your actual stats-report script under `scripts/`.

PowerShell:

- `conda run -n module python -c "import pingouin, xlwings; print('ok')"`
- `conda run -n module python .\scripts\run_stats_report.py`

cmd:

- `conda run -n module python -c "import pingouin, xlwings; print('ok')"`
- `conda run -n module python scripts\run_stats_report.py`

## Completion Checklist

- Report workbook path.
- Report final sheet count and rationale if more than two sheets.
- List created table names.
- Confirm `table_guide` descriptions were added for all tables.
- Report validation results.
