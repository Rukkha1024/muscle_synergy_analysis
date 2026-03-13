# Issue 002: Implement Cheung 2021-style step vs nonstep synergy comparison analysis

**Status**: In Progress
**Created**: 2026-03-13

## Background

`analysis/compare_Cheung,2021/` currently contains the reference paper PDF and an ExecPlan, but it does not yet provide a runnable analysis workflow. The goal is to build a self-contained analysis that re-extracts trial-level muscle synergies with a Cheung-style NMF rule, compares step and nonstep structure on the current perturbation dataset, generates academic-style figures, and writes a prior-study-oriented report without modifying the production pipeline outputs.

## Acceptance Criteria

- [x] A single-entry script exists under `analysis/compare_Cheung,2021/` and supports `--dry-run`.
- [x] The analysis reuses `outputs/runs/default_run` trial metadata and the configured normalized EMG parquet to rebuild selected trials.
- [x] The workflow produces paper-style comparison metrics, pipeline-style cluster figures, and a complete `report.md`.
- [x] The analysis is executed and the resulting outputs are validated in the current environment.

## Tasks

- [x] 1. Update the ExecPlan so it matches the actual folder, inputs, and implementation decisions.
- [x] 2. Implement the analysis script for NMF, clustering, matching, cross-fit, and structural metrics.
- [x] 3. Generate pipeline-style cluster figures and write the prior-study comparison report.
- [x] 4. Run dry-run and full validation, then record checksums and review findings.

## Notes

- Implemented `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py` as the single entry point.
- Confirmed that the baseline truth comes from `outputs/runs/default_run/all_trial_window_metadata.csv`, while the re-analysis time-series input must come from the config-linked normalized EMG parquet.
- Validated `--dry-run`, `--prototype`, and repeated full runs in the `module` conda environment.
- Updated the cluster figures to reuse the pipeline renderer in `src/synergy_stats/figures.py` so the output style matches `default_run`.
- Repeated full execution and verified stable MD5 checksums for `report.md` and all retained PNG outputs.
