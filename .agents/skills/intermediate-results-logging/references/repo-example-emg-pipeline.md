# Repository Example: EMG Synergy Pipeline

This repository already contains one concrete implementation of the pattern.

## Goal

Improve console and `run.log` readability for a long-running analysis pipeline without changing the numerical outputs.

## Reference Inputs

- ExecPlan: `.agents/execplans/console_log_structured_output_execplan_en.md`
- Commit: `4c4de22ab97fb122f30607fa9ec2bcbaac03ec7d`
- Shared helper: `src/emg_pipeline/log_utils.py`

## Pattern Used

- Add a shared banner and key-value section helper.
- Print one visible log line per `logging.info()` call.
- Show step banners from the real step list.
- Surface analysis summaries instead of debug internals.
- Re-run the pipeline and compare stable outputs with the repository MD5 checker.

## Step-Level Examples

- Load step: merged rows, columns, subject coverage, velocity coverage, missing ratio, value range.
- Trial extraction step: extracted trial count, duration range, subject coverage, velocity coverage.
- NMF step: backend, device, dtype, rank distribution, VAF range, mean, std, total components.
- Clustering step: algorithm, raw and selected `K`, selection status, duplicate-trial count, inertia.
- Export step: output path, file counts by type, final validation logs.

## Why It Matters

The visible logs let a user confirm that the analysis is healthy while it is still running, instead of waiting for the final files and opening them manually.
