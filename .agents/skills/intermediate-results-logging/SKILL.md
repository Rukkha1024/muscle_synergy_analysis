---
name: intermediate-results-logging
description: Add or improve structured console and run-log output for data analysis, ETL, modeling, clustering, and other long-running batch workflows where users need meaningful intermediate results to verify progress and data quality without opening output files. Use when the task is logging-focused, behavior-preserving, and should surface per-step summaries such as row counts, missingness, group splits, model-selection metrics, and export counts.
---

# Intermediate Results Logging

## Overview

Expose meaningful intermediate results while a data workflow runs. Keep the computational logic and final artifacts unchanged; improve only the visibility of progress, data state, and result quality.

## Core Contract

- Treat this as a logging-only refactor unless the user explicitly asks for analysis changes.
- Prefer summaries that help a human decide whether the current step looks healthy.
- Log one visible line at a time so console output and log files stay grep-friendly.
- Keep the signal high. Do not dump full tables, per-row values, or large object reprs.
- Validate that added logs did not change the workflow outputs.

## Rich Integration

When the target is a Python script with human-facing console output, use `python-rich-console` as the default companion skill.

- For most non-trivial Python scripts, prefer Rich-based console output over raw `print()` formatting.
- Reach for `Console`, `Table`, `Panel`, `track`, or `RichHandler` before inventing custom spacing or ASCII layouts for human-facing console summaries.
- Keep the same logging contract: one visible line at a time, high-signal summaries, and behavior-preserving changes.
- Treat very small one-off scripts as the exception, not the default.
- Keep file logs and grep-oriented timestamped logs line-based even when the interactive console view uses Rich renderables.

Skip or soften the Rich requirement only when:
- the script is truly tiny and throwaway
- stdout must remain machine-readable or is parsed by another program
- the user explicitly asks for plain-text-only output
- the runtime environment cannot support Rich cleanly

## Workflow

1. Identify the execution path.
   Find the entrypoint, the ordered steps, and the existing logging sink. Confirm whether the workflow writes only to the console, only to a file, or to both.

2. Decide what a user needs to verify at each step.
   Pick a small set of metrics that answer: "Did this step run?", "Did it process the expected amount of data?", and "Did it produce plausible intermediate results?"

3. Add a consistent structure.
   Use step banners for major phases, section headers for step-local summaries, and aligned key-value rows for metrics. In Python scripts, prefer Rich primitives for this structure. If several files need the same formatting, add a tiny shared helper instead of repeating formatting code.

4. Log intermediate results, not implementation noise.
   Report the values that explain the analysis state. Avoid debug traces unless the user asked for diagnostics.

5. Re-run and compare.
   Execute the workflow, inspect the visible log shape, and compare outputs against a baseline with the strongest available repository-native check.

## What To Log

Choose metrics that let a user judge progress and quality quickly.

- Input/loading steps: row count, column count, subject/group coverage, time span, missing-value ratio, min/max sanity checks.
- Filtering/preprocessing steps: records kept vs dropped, group splits, window counts, feature availability, duplicate counts.
- Modeling/extraction steps: runtime backend, sample count, rank or hyperparameter distribution, score range, mean/std summaries, failure count.
- Grouping/clustering/statistics steps: selected parameter values, selection status, cluster sizes, duplicate exclusions, test counts, effect-size or fit summaries.
- Export/finalization steps: output path, file counts by type, workbook/table count, figure count, validation status.

When selecting fields, prefer quantities a user can compare against expectation or prior runs.

## Formatting Rules

- Use short, stable section titles.
- Keep labels explicit and user-facing.
- Format numeric summaries consistently within a section.
- Show units when they matter.
- Prefer a compact list preview over a full category dump.
- Use `n/a` for unavailable values rather than omitting the field silently.

## Safe Patterns

- Add a small helper module when multiple files need the same banner or key-value rendering.
- Derive step totals from the real step list instead of hardcoding them.
- Compute summary statistics from data already produced by the workflow.
- Leave domain logic, model fitting, and export behavior unchanged.

## Anti-Patterns

- Rewriting the analysis just to make logging easier.
- Logging entire DataFrames, arrays, or workbook contents.
- Mixing multiple lines into one logging call when each visible line needs its own timestamp prefix.
- Emitting noisy per-item logs inside large loops unless the user asked for trace-level output.
- Claiming output stability without a real rerun and comparison.

## Validation

- Run the workflow before changes if a clean baseline is needed.
- Run the workflow again after adding logs.
- Inspect the console or run log to confirm that each major step now exposes meaningful intermediate results.
- Compare outputs with the best repository-native method available.
  Prefer MD5 or checksum comparison when the repository already uses it.
  Otherwise compare curated files, row counts, and key summary statistics.
- If outputs differ, treat that as a behavior regression until proven otherwise.

## References

- Read `references/example-patterns.md` for generic examples of what to log in common analysis stages.
- Read `references/repo-example-emg-pipeline.md` only when you want a concrete repository example of this pattern.
