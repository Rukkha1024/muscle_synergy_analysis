# Gap-Free First Zero-Duplicate K Analysis ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows `.agents/PLANS.md`. It is written for a novice who only has the current repository checkout and this file. The implementation described here must stay inside `analysis/` and must not add a new menu, flag, or selection mode to `main.py` or the main pipeline.

## Purpose / Big Picture

After this change, a user can answer a very specific question without changing the main pipeline: "What K would we get if we ignore the gap statistic and instead choose the first K that has zero duplicate trials?" The analysis runs from a pipeline final parquet file, reconstructs the pooled clustering input offline, and reports the first zero-duplicate K. For the current user question, the expected observable outcome is that the rerun reports `k_selected=13` for the relevant bundle instead of the gap-driven value `15`.

The easiest way to see the behavior is to run one analysis script under `analysis/`, point it at a single final parquet file such as `outputs/final_trialwise.parquet`, and confirm that the script prints a K scan summary, writes a small artifact bundle under its own analysis folder, and states that it did not call the gap-statistic path.

## Progress

- [x] (2026-03-19 01:05Z) Confirmed the user wants an analysis-only rerun and explicitly does not want a new main-pipeline menu or CLI option.
- [x] (2026-03-19 01:10Z) Confirmed the selection rule: choose the first K whose clustering result has zero duplicate trials.
- [x] (2026-03-19 01:16Z) Confirmed documentation scope: write README content only inside the new analysis folder, not in the repository root README.
- [x] (2026-03-19 01:28Z) Created `analysis/first_zero_duplicate_k_rerun/README.md`, `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`, and `analysis/first_zero_duplicate_k_rerun/report.md`.
- [x] (2026-03-19 01:33Z) Implemented the offline rerun so it reads one final parquet bundle, reconstructs pooled vectors, scans K without calling `compute_gap_statistic`, and records the first zero-duplicate solution.
- [x] (2026-03-19 01:34Z) Added `tests/test_analysis/test_first_zero_duplicate_k_rerun.py` and verified the synthetic contract path with `2 passed`.
- [x] (2026-03-19 01:15Z) Ran `--dry-run` against `outputs/final_concatenated.parquet` and confirmed the live bundle metadata `k_gap_raw=15`, `k_selected=15`, `k_min_unique=13`.
- [x] (2026-03-19 01:16Z) Ran two full reruns against `outputs/final_concatenated.parquet`; both reported `k_selected_first_zero_duplicate=13`.
- [x] (2026-03-19 01:17Z) Verified reproducibility by matching MD5 for `summary.json`, `k_scan.json`, and `k_duplicate_burden.png` across `default_run` and `recheck_run`.

## Surprises & Discoveries

- Observation: The main clustering module already has most of the duplicate-feasibility machinery needed for this analysis.
  Evidence: `src/synergy_stats/clustering.py` already exposes internal helpers such as `_fit_best_kmeans_result` and `_search_zero_duplicate_candidate_at_k`, even though the public path still hard-requires `gap_statistic`.

- Observation: A clean analysis-only implementation can depend on the final parquet bundle rather than rerunning raw EMG preprocessing or NMF.
  Evidence: `src/synergy_stats/single_parquet.py` restores `minimal_W`, `minimal_H_long`, `labels`, and `trial_windows` from one parquet source, which is enough to reconstruct pooled clustering inputs offline.

- Observation: The existing `analysis/cosine_rerun_gap13_duplicate_exclusion/` folder is related but not the same problem.
  Evidence: That analysis starts from a legacy cross-group baseline bundle and studies fixed-`K=13` component exclusion after clustering, while the current request is to rerun K selection itself without gap statistic.

- Observation: The live `concatenated` bundle, not the `trialwise` bundle, matches the user's stated `13 vs 15` concern.
  Evidence: `outputs/final_concatenated.parquet` metadata reports `k_gap_raw=15`, `k_selected=15`, and `k_min_unique=13`, while the current `trialwise` bundle reports `k_gap_raw=17` and `k_selected=21`.

- Observation: Concatenated analysis units do not always use numeric `trial_num` values.
  Evidence: The first live run failed because concatenated rows used strings such as `concat_nonstep`, so reconstruction and JSON export had to preserve raw trial keys instead of forcing integers.

- Observation: Output reproducibility initially failed only because `summary.json` stored an absolute figure path.
  Evidence: The first MD5 comparison showed `k_scan.json` and the figure bytes matched, while `summary.json` differed only at `figure_path`; switching that field to the filename made all three files match.

## Decision Log

- Decision: The new work will live in `analysis/first_zero_duplicate_k_rerun/`.
  Rationale: The user asked for a new analysis folder rather than extending the main pipeline, and a new folder keeps this question separate from older cosine-rerun work.
  Date/Author: 2026-03-19 / Codex

- Decision: The script will read a single final parquet bundle such as `outputs/final_trialwise.parquet` instead of raw EMG inputs.
  Rationale: This follows the repository architecture rule that `analysis/` should depend on pipeline outputs, not on pipeline-side raw preprocessing steps.
  Date/Author: 2026-03-19 / Codex

- Decision: The no-gap rule is defined as "scan K from `k_min` upward and stop at the first K whose best searched candidate has zero duplicate trials."
  Rationale: This is the user-approved interpretation of "gap statistic 적용 안함," and it directly tests the claim that the relevant answer should be `13`.
  Date/Author: 2026-03-19 / Codex

- Decision: The implementation must not add any `main.py` flag, config knob, or new selection mode to the production pipeline.
  Rationale: The user explicitly rejected adding a menu to the main pipeline.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

The plan is now implemented for the requested analysis-only scope. The repository has a self-contained folder `analysis/first_zero_duplicate_k_rerun/` with a runnable script, a README, a report, and reproducible artifacts. When run against `outputs/final_concatenated.parquet`, the analysis reports `k_selected_first_zero_duplicate=13`, while the pipeline metadata still reports the gap-driven value `15`. This directly answers the user's current `13 vs 15` question without changing `main.py` or the production pipeline.

## Context and Orientation

The main pipeline entrypoint is `main.py`, but this plan must not modify it. The relevant production output for this analysis is the single-parquet bundle written by `src/synergy_stats/single_parquet.py`. That module stores analysis frames such as `minimal_W`, `minimal_H_long`, `labels`, `metadata`, and `trial_windows` in one parquet table keyed by `artifact_kind`. The new analysis should load one of those bundle files, usually `outputs/final_trialwise.parquet` for a trialwise rerun or `outputs/final_concatenated.parquet` for a concatenated rerun.

The clustering logic that matters lives in `src/synergy_stats/clustering.py`. In plain language, a "duplicate trial" means one trial contributes more than one component to the same cluster label. The production path currently uses the gap statistic to choose a structure-first K and then escalates upward until it finds a zero-duplicate solution. This plan intentionally skips that first step. It should reconstruct the pooled vectors and look for the first K that is already zero-duplicate, without computing gap values.

Relevant reference files are:

- `src/synergy_stats/single_parquet.py` for loading the final parquet bundle.
- `src/synergy_stats/clustering.py` for duplicate checking and candidate search behavior.
- `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py` for an example of an analysis script that reuses pipeline logic while staying outside `main.py`.
- `analysis/cosine_rerun_gap13_duplicate_exclusion/README.md` for nearby analysis-folder conventions, but not for the exact selection rule.

## Plan of Work

Create a new folder `analysis/first_zero_duplicate_k_rerun/` with three top-level files. `README.md` explains why the folder exists, states that it is an analysis-only rerun, names the expected input parquet file, and shows the exact dry-run and full-run commands. `analyze_first_zero_duplicate_k_rerun.py` is the single entry point. `report.md` is the human-readable analysis report and must be updated after the first full validation run.

The script should accept one pipeline final parquet input path, an output directory, and a `--dry-run` flag. The default input should be `outputs/final_trialwise.parquet` because the current user question is about a concrete observed K mismatch in the default rerun context. The script should use `src.synergy_stats.single_parquet.load_single_parquet_bundle()` to restore the bundle, then reconstruct one pooled clustering table from the `minimal_W` frame. It must filter to the selected pooled group, preserve trial identity fields such as `subject`, `velocity`, `trial_num`, and `component_index`, and build the same vector order that the clustering path expects.

For K selection, the script should not call `compute_gap_statistic`. Instead, it should derive `k_min` from the reconstructed pooled rows, derive `k_max` from the available component count and an explicit CLI or config-backed ceiling, and scan K upward. At each K, it should use the same restart behavior as the production clustering code and record at least these fields: candidate K, whether a zero-duplicate solution exists, duplicate-trial count for the best searched candidate, searched restart count, and objective value of the best zero-duplicate candidate when it exists. The script should stop at the first K with zero duplicate trials and report that as `k_selected_first_zero_duplicate`.

The output must remain analysis-scoped. Write artifacts under `analysis/first_zero_duplicate_k_rerun/artifacts/<run_name>/`. Keep the artifact set small and reproducible: a `summary.json`, a `k_scan.json`, a `checksums.md5`, and optionally one diagnostic figure such as `k_duplicate_burden.png`. Do not write Excel or CSV files. Update `report.md` so it explains the research question, the offline reconstruction method, the exact no-gap selection rule, the observed K scan, and the final answer for the current bundle.

## Concrete Steps

Work from the repository root.

First create the analysis folder and script skeleton:

    mkdir -p analysis/first_zero_duplicate_k_rerun/artifacts

Then implement the script and documentation described above. After implementation, run a dry-run first:

    conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
      --source-parquet outputs/final_trialwise.parquet \
      --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run \
      --dry-run

Expected dry-run observations:

    The script prints the restored bundle keys.
    The script prints the pooled vector count and resolved K range.
    The script exits without writing the full artifact set.

Then run the full analysis:

    conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
      --source-parquet outputs/final_trialwise.parquet \
      --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run \
      --overwrite

Expected full-run observations for the user's current question:

    The script states that gap statistic was not used.
    The script prints duplicate-trial counts for successive K values.
    The script reports the first zero-duplicate K.
    For the intended bundle, the observed answer should be `k_selected_first_zero_duplicate=13`.

## Validation and Acceptance

Acceptance is behavioral, not structural. A user should be able to run one analysis script from `analysis/`, point it at an existing final parquet file, and get a clear statement of the no-gap answer. The script must succeed in `--dry-run` mode and in full-run mode. The output folder must contain analysis-scoped artifacts only. `report.md` must agree with the numbers printed by the script.

The key acceptance check for the current request is this: when run against the intended parquet bundle, the script shows a K scan where the first K with zero duplicate trials is `13`, while the main pipeline had previously reported the gap-driven result `15`. If the observed answer differs, the report must say so plainly rather than forcing the expected value.

## Idempotence and Recovery

The analysis writes only under its own `analysis/first_zero_duplicate_k_rerun/artifacts/` tree, so it is safe to rerun. Use `--overwrite` to replace a prior artifact directory. If a run fails halfway, delete only that analysis artifact subdirectory or rerun with `--overwrite`; do not modify `outputs/final*.parquet` and do not touch the main pipeline outputs.

## Artifacts and Notes

Expected artifact layout after implementation:

    analysis/first_zero_duplicate_k_rerun/
      README.md
      analyze_first_zero_duplicate_k_rerun.py
      report.md
      artifacts/default_run/
        summary.json
        k_scan.json
        checksums.md5
        k_duplicate_burden.png

Expected summary fields:

    source_parquet
    group_id
    vector_count
    k_min
    k_max
    selection_method = first_zero_duplicate
    gap_statistic_used = false
    k_selected_first_zero_duplicate
    duplicate_trial_count_by_k

## Interfaces and Dependencies

The script should use `polars` first when reading or reshaping tabular data from the restored bundle, and only use `pandas` where an existing helper or plotting path requires it. Use `src.synergy_stats.single_parquet.load_single_parquet_bundle` to restore the source bundle. Reuse the clustering module's duplicate-search semantics rather than inventing a new duplicate definition. If a helper from `src/synergy_stats/clustering.py` is imported even though its name starts with `_`, document that choice in the script docstring or inline comments so future readers know the analysis intentionally mirrors production search behavior without changing the production API.

Change note: This plan was added after the user clarified three scope constraints: create a new analysis folder, define the no-gap rule as the first zero-duplicate K, and keep all README changes inside the analysis folder only.
