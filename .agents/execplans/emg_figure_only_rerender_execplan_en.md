# Add a Figure-Only Rerender Script for Existing EMG Pipeline Outputs

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository contains `.agents/PLANS.md`, and this document must be maintained in accordance with that file. This plan is written for a novice who only has the current working tree and this file.

## Purpose / Big Picture

After this change, a user will be able to regenerate every EMG figure without rerunning `main.py` or recomputing NMF and clustering. The new workflow will reuse the CSV artifacts that already exist inside `outputs/runs/<run_id>`, then rebuild group figures, cross-group figures, and every trial-level NMF figure in place.

The user-visible behavior is simple. Running one dedicated script against an existing run directory must recreate the full `figures/` tree. The user must not have to run `main.py`, any earlier numbered script, or any separate preparation command first. The script must overwrite old figures by default, fail immediately when any required figure source file is missing, and leave non-figure outputs unchanged. A user must be able to prove that the new script works by rerendering figures for an existing run, checking that the expected figure files exist, and confirming that curated stable CSV files keep the same MD5 values as before.

## Progress

- [x] (2026-03-16 08:35Z) Requirements brief completed with the user: rerender all figure families, take a run directory as the primary input, overwrite existing figures by default, and fail immediately on missing required source files.
- [x] (2026-03-16 08:35Z) Repository orientation completed for the current figure path in `main.py`, `scripts/emg/05_export_artifacts.py`, `src/synergy_stats/artifacts.py`, and `src/synergy_stats/figures.py`.
- [x] (2026-03-16 08:35Z) Existing reusable run artifacts confirmed: representative `W/H`, minimal-unit `W/H`, cluster labels, trial window metadata, and cross-group decision tables already exist in `outputs/runs/<run_id>`.
- [x] (2026-03-16 08:35Z) Design direction locked: create a separate script and a shared disk-backed rendering helper instead of adding a `main.py --figures-only` mode.
- [x] (2026-03-16 09:00Z) Implemented `src/synergy_stats/figure_rerender.py` with run-directory validation, Polars-backed CSV loading, temp-directory rendering, and safe `figures/` replacement.
- [x] (2026-03-16 09:02Z) Added `scripts/emg/06_render_figures_only.py` as a dedicated figure-only CLI and updated it so direct script execution resolves the repository root on `sys.path`.
- [x] (2026-03-16 09:04Z) Replaced direct in-memory figure rendering inside `src/synergy_stats/artifacts.py` with the shared disk-backed helper after artifact CSVs are written.
- [x] (2026-03-16 09:06Z) Added focused rerender tests, updated the workbook-export tests to patch the shared helper, and extended the MD5 contract to prove figure-only differences are ignored.
- [x] (2026-03-16 09:08Z) Validated the standalone rerender path on `outputs/runs/default_run`: the script regenerated 131 figures, the six top-level figure files were recreated, the `nmf_trials` count matched `all_trial_window_metadata.csv`, and the curated stable MD5 comparison passed.
- [ ] (2026-03-16 09:10Z) `conda run -n cuda python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q` still fails on the pre-existing expectation that `global_step/cluster_labels.csv` and `global_nonstep/clustering_metadata.csv` exist under the run directory. That mismatch is outside the figure-only rerender scope and remains unresolved in this plan.

## Surprises & Discoveries

- Observation: The repository already persists every figure input needed for rerendering inside the run directory, so a figure-only script can stay lightweight and avoid recomputing NMF or clustering.
  Evidence: `outputs/runs/default_run` already contains `all_representative_W_posthoc.csv`, `all_representative_H_posthoc_long.csv`, `all_minimal_units_W.csv`, `all_minimal_units_H_long.csv`, `all_cluster_labels.csv`, `all_trial_window_metadata.csv`, `cross_group_w_pairwise_cosine.csv`, and `cross_group_w_cluster_decision.csv`.

- Observation: `run_manifest.json` stores a config hash, but not the original config path, so the figure-only script still needs a config input policy.
  Evidence: `src/emg_pipeline/config.py` writes `config_sha256` and runtime metadata only.

- Observation: The plotting functions already live in `src/synergy_stats/figures.py`, but the current export path still builds figure inputs from in-memory objects inside `src/synergy_stats/artifacts.py`.
  Evidence: `export_results()` calls `save_group_cluster_figure()`, `save_trial_nmf_figure()`, `save_cross_group_heatmap()`, `save_cross_group_matched_w()`, `save_cross_group_matched_h()`, and `save_cross_group_decision_summary()` directly.

- Observation: The project runtime assumes `conda run -n cuda python`; plain `python` is not available in the current environment.
  Evidence: shell check returned `/bin/bash: line 1: python: command not found`.

- Observation: Running `scripts/emg/06_render_figures_only.py` directly required explicitly adding the repository root to `sys.path`; the import path that works inside `main.py` step modules is not sufficient for a standalone script inside `scripts/emg/`.
  Evidence: the first CLI test failed with `ModuleNotFoundError: No module named 'src'` until the script inserted `Path(__file__).resolve().parents[2]` into `sys.path`.

- Observation: The conda-backed end-to-end contract now reaches the new shared rendering path successfully, but still fails later on a pre-existing assertion about `global_step/` and `global_nonstep/` subdirectories that are not created by the current export flow.
  Evidence: `tests/test_synergy_stats/test_end_to_end_contract.py` failed at `assert step_labels.exists()` even after the pipeline finished, wrote aggregate CSVs, and produced the rerendered figure tree.

## Decision Log

- Decision: Add a new script at `scripts/emg/06_render_figures_only.py` instead of extending `main.py`.
  Rationale: The user explicitly asked for a separate figure-only path so that `main.py` does not have to run for every figure refresh.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: The standalone user contract is one command: run the figure-only script itself, and it must perform the entire rerender flow.
  Rationale: The user explicitly clarified that figure generation must be possible by executing the script alone, without running any other script first.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Use `outputs/runs/<run_id>` as the main input and keep `--config` as an optional override with default `configs/global_config.yaml`.
  Rationale: The run directory is the user-approved primary input, but the script still needs figure config and muscle order. A default config path keeps the common path short while preserving reproducibility for custom configs.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Rerender every current figure family: group cluster figures, cross-group figures, and per-trial NMF figures.
  Rationale: The user explicitly requested full figure regeneration, not a partial subset.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Overwrite is the default behavior and missing source files are fatal errors.
  Rationale: These were explicit user decisions. The implementation must therefore prefer predictable full refresh over partial best-effort output.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: The main pipeline and the new figure-only script must share one disk-backed rendering path.
  Rationale: Reusing one rendering helper prevents drift between the figures produced during a normal pipeline run and the figures produced later from saved artifacts.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Read CSVs with Polars first and convert to pandas only where the existing matplotlib functions already require pandas.
  Rationale: The repository rule says to use Polars before pandas. The current plotting functions already accept pandas DataFrames, so conversion should happen only at the final interface boundary.
  Date/Author: 2026-03-16 / ChatGPT

## Outcomes & Retrospective

Implementation is complete for the figure-only rerender feature itself. The repository now has one shared disk-backed rendering path in `src/synergy_stats/figure_rerender.py`, the normal pipeline uses that helper after artifact CSV export, and `scripts/emg/06_render_figures_only.py` can rebuild figures from an existing run directory without rerunning NMF or clustering.

The most important validation result is user-visible and concrete: `conda run -n cuda python scripts/emg/06_render_figures_only.py --run-dir outputs/runs/default_run` regenerated 131 figures in place, restored the full top-level figure set, preserved the `nmf_trials` count, and left the curated non-figure CSV MD5 values unchanged. The only remaining gap captured here is a pre-existing end-to-end test expectation about `global_step/` and `global_nonstep/` subdirectories that this feature did not introduce.

## Context and Orientation

The repository entrypoint is `main.py`. It loads YAML config through `src/emg_pipeline/config.py`, prepares a run directory under `outputs/runs/<run_id>`, and executes these wrapper steps in order:

    scripts/emg/01_load_emg_table.py
    scripts/emg/02_extract_trials.py
    scripts/emg/03_extract_synergy_nmf.py
    scripts/emg/04_cluster_synergies.py
    scripts/emg/05_export_artifacts.py

The current figure generation happens inside `src/synergy_stats/artifacts.py` during `export_results()`. That function currently writes CSV artifacts and renders figures from in-memory objects created earlier in the pipeline. The plotting functions themselves already exist in `src/synergy_stats/figures.py`.

In this repository, “group figures” are `global_step_clusters` and `global_nonstep_clusters`. “Cross-group figures” are `cross_group_cosine_heatmap`, `cross_group_matched_w`, `cross_group_matched_h`, and `cross_group_decision_summary`. “Trial-level NMF figures” are the files under `figures/nmf_trials/`, one file per trial in `all_trial_window_metadata.csv`.

The figure-only script must use these existing run artifacts:

    all_representative_W_posthoc.csv
    all_representative_H_posthoc_long.csv
    all_minimal_units_W.csv
    all_minimal_units_H_long.csv
    all_cluster_labels.csv
    all_trial_window_metadata.csv
    cross_group_w_pairwise_cosine.csv
    cross_group_w_cluster_decision.csv

Do not fall back to rerunning NMF, clustering, or `main.py` when any of these files are missing. The user wants immediate failure in that situation.

The most relevant files for this change are:

    main.py
    configs/global_config.yaml
    configs/synergy_stats_config.yaml
    scripts/emg/05_export_artifacts.py
    src/emg_pipeline/config.py
    src/synergy_stats/artifacts.py
    src/synergy_stats/figures.py
    tests/test_synergy_stats/test_end_to_end_contract.py
    tests/test_synergy_stats/test_figures_headless_backend.py
    tests/test_synergy_stats/test_md5_compare_outputs.py

Create one new module and one new script:

    src/synergy_stats/figure_rerender.py
    scripts/emg/06_render_figures_only.py

If README usage examples are updated, edit only the parts that explain how to rerender figures from an existing run. Do not rewrite unrelated setup or theory sections.

## Plan of Work

### 1. Create one shared rerender helper

Create `src/synergy_stats/figure_rerender.py`. This module must own the disk-backed path for figure generation. Its job is to validate the run directory, load required CSV files, rebuild the DataFrames that `src/synergy_stats/figures.py` expects, and write the figure tree.

Define a small public surface with stable names:

    required_figure_artifacts(run_dir: Path) -> dict[str, Path]
    load_figure_artifacts(run_dir: Path) -> dict[str, object]
    render_figures_from_run_dir(run_dir: Path, cfg: dict[str, Any]) -> dict[str, list[str]]

`required_figure_artifacts()` must resolve the required file paths and raise a clear `FileNotFoundError` if any input is missing. Validate all required inputs before touching the existing `figures/` directory.

`load_figure_artifacts()` must read CSVs with Polars, then convert to pandas only for the plotting functions. Preserve `utf-8-sig` compatibility when reading and writing. Use current config values for muscle order, figure DPI, and figure extension.

`render_figures_from_run_dir()` must rebuild all figure families from saved artifacts only. It must:

1. Render `global_step_clusters` and `global_nonstep_clusters` from representative `W/H`, cluster labels, and trial metadata.
2. Render every trial-level NMF figure from `all_minimal_units_W.csv`, `all_minimal_units_H_long.csv`, and the saved trial metadata columns.
3. Render all cross-group figures from the saved cross-group CSVs plus representative/minimal-unit inputs already in the run directory.

Write figures into a temporary directory under the run root, such as `figures.__tmp__`, and only replace `figures/` after all plots succeed. This keeps overwrite-by-default behavior safe and avoids leaving a half-written figure tree behind.

### 2. Route the main pipeline through the same helper

Edit `src/synergy_stats/artifacts.py` so that `export_results()` stops rendering figures directly from in-memory structures. Keep CSV, parquet, and workbook generation where they already belong. After all figure source artifacts are written successfully, call `render_figures_from_run_dir(output_dir, cfg)`.

This is the crucial de-duplication step. The main pipeline must still emit the same figure files after a normal run, but it should do so by reusing the new disk-backed helper. That ensures the new standalone script and the existing pipeline stay behaviorally aligned.

Do not change how clustering, NMF extraction, or cross-group tables are computed. This feature is a rendering-path refactor plus a new entrypoint, not a numerical logic change.

### 3. Add a dedicated CLI script

Create `scripts/emg/06_render_figures_only.py`. Keep the script thin. It must:

1. Parse `--run-dir` as a required argument.
2. Parse `--config` with default `configs/global_config.yaml`.
3. Load config through the existing `load_pipeline_config()` helper in `src/emg_pipeline/config.py`.
4. Resolve the run directory without rewriting manifests or non-figure artifacts.
5. Call `render_figures_from_run_dir()`.
6. Exit with code `0` on success and nonzero on any validation or rendering failure.

Do not add fallback flags such as `--skip-missing` or `--partial`. The user explicitly rejected partial generation.
The user-facing execution contract is that this one script command is sufficient. Internal imports are fine, but no separate setup script, no chained shell command, and no requirement to invoke `main.py` or `scripts/emg/05_export_artifacts.py` beforehand is allowed.

### 4. Add focused tests

Add `tests/test_synergy_stats/test_figure_rerender.py`. This file should cover the new helper and the new CLI contract with lightweight fixture data.

The minimum useful tests are:

1. A failure-path test showing that one missing required CSV causes the script or helper to fail before replacing the existing `figures/` directory.
2. A success-path test showing that rerendering from saved CSV artifacts recreates the expected top-level figure files and the expected number of trial figures.
3. A test showing that rerendering uses saved run artifacts only and does not require the earlier pipeline context objects.

Extend `tests/test_synergy_stats/test_end_to_end_contract.py` so the existing fixture run still proves that `main.py` writes the full figure tree through the shared helper. Add assertions for all four cross-group figures and keep the current trial-figure-count contract.

If an existing MD5-oriented test is the natural place for non-figure stability checks, extend that file rather than duplicating similar assertions elsewhere.

### 5. Update minimal user-facing documentation

Update `README.md` only where it explains how to regenerate figures from an existing run. Keep the change surgical. The new command example should look like this:

    conda run -n cuda python scripts/emg/06_render_figures_only.py --run-dir outputs/runs/default_run

Document that the command overwrites the `figures/` tree by default and fails if required figure source CSVs are missing.

## Concrete Steps

Run all commands from the repository root:

    cd /home/alice/workspace/26-03-synergy-analysis

Before changing code, inspect the current behavior:

    conda run -n cuda python main.py --help
    conda run -n cuda python scripts/emg/06_render_figures_only.py --help

Expected result after implementation: the new script help exists and `main.py` remains the full pipeline entrypoint.

Prepare a non-figure snapshot for MD5 comparison:

    tmp_before="$(mktemp -d)"
    cp -R outputs/runs/default_run "$tmp_before/default_run_before"

Run the figure-only script:

    conda run -n cuda python scripts/emg/06_render_figures_only.py --run-dir outputs/runs/default_run

Expected terminal outcome: a success message that names the run directory and the number of figures written. No NMF or clustering steps should run.
This single command must be sufficient. No additional script invocation should be needed before or after it.

Verify the figure tree:

    find outputs/runs/default_run/figures -maxdepth 1 -type f | sort
    find outputs/runs/default_run/figures/nmf_trials -type f | wc -l

Expected result: the top-level directory contains these six files:

    cross_group_cosine_heatmap.png
    cross_group_decision_summary.png
    cross_group_matched_h.png
    cross_group_matched_w.png
    global_nonstep_clusters.png
    global_step_clusters.png

and the `nmf_trials` count matches the number of unique trials in `all_trial_window_metadata.csv`.

Run tests:

    conda run -n cuda pytest tests/test_synergy_stats/test_figure_rerender.py -q
    conda run -n cuda pytest tests/test_synergy_stats/test_end_to_end_contract.py -q

Compare curated non-figure outputs against the snapshot:

    conda run -n cuda python scripts/emg/99_md5_compare_outputs.py \
      --base "$tmp_before/default_run_before" \
      --new outputs/runs/default_run

Expected result:

    MD5 comparison passed for curated stable files.

## Validation and Acceptance

The change is accepted only if all of the following are true:

1. `scripts/emg/06_render_figures_only.py --run-dir <existing_run>` recreates the full `figures/` tree without invoking the earlier pipeline stages.
2. The figure rerender path is user-complete in one command. The user does not need to run any second script or manual preparation command.
3. The script overwrites an existing `figures/` tree by default.
4. If any required CSV input is missing, the script exits nonzero before replacing the existing `figures/` tree.
5. `main.py` still produces the same figure families during a normal pipeline run because it now uses the same helper after writing CSV artifacts.
6. `scripts/emg/99_md5_compare_outputs.py` passes when comparing a pre-rerender snapshot against the post-rerender run directory, proving that curated non-figure outputs stayed unchanged.

## Idempotence and Recovery

The rerender path must be idempotent. Running the new script multiple times against the same run directory should simply replace the figure tree with the same set of files.

The safe recovery path is:

1. Validate all required inputs first.
2. Render into a temporary sibling directory.
3. Replace `figures/` only after successful completion.

If rendering fails, keep the previous `figures/` directory unchanged and report the first blocking missing file or rendering exception clearly.

## Artifacts and Notes

The saved run directory already contains enough information to drive figure regeneration. The implementation should treat this file set as the source of truth:

    outputs/runs/default_run/all_representative_W_posthoc.csv
    outputs/runs/default_run/all_representative_H_posthoc_long.csv
    outputs/runs/default_run/all_minimal_units_W.csv
    outputs/runs/default_run/all_minimal_units_H_long.csv
    outputs/runs/default_run/all_cluster_labels.csv
    outputs/runs/default_run/all_trial_window_metadata.csv
    outputs/runs/default_run/cross_group_w_pairwise_cosine.csv
    outputs/runs/default_run/cross_group_w_cluster_decision.csv

The expected regenerated top-level figure tree is:

    outputs/runs/<run_id>/figures/global_step_clusters.<ext>
    outputs/runs/<run_id>/figures/global_nonstep_clusters.<ext>
    outputs/runs/<run_id>/figures/cross_group_cosine_heatmap.<ext>
    outputs/runs/<run_id>/figures/cross_group_matched_w.<ext>
    outputs/runs/<run_id>/figures/cross_group_matched_h.<ext>
    outputs/runs/<run_id>/figures/cross_group_decision_summary.<ext>
    outputs/runs/<run_id>/figures/nmf_trials/*.<ext>

Replace `<ext>` with the configured figure suffix from `configs/synergy_stats_config.yaml`.

## Interfaces and Dependencies

In `src/synergy_stats/figure_rerender.py`, define:

    def required_figure_artifacts(run_dir: Path, *, include_cross_group: bool = True) -> dict[str, Path]:
        ...

    def load_figure_artifacts(run_dir: Path, *, include_cross_group: bool = True) -> dict[str, object]:
        ...

    def render_figures_from_run_dir(run_dir: Path, cfg: dict[str, Any]) -> dict[str, list[str]]:
        ...

`load_figure_artifacts()` should decode CSVs with `utf-8-sig`, parse them with Polars, and convert only the final tables needed by `src/synergy_stats/figures.py` to pandas DataFrames. The optional `include_cross_group` keyword allows the shared helper to stay compatible with configs that disable cross-group figure output.

In `scripts/emg/06_render_figures_only.py`, define:

    def main() -> int:
        ...

and load config with:

    from src.emg_pipeline.config import load_pipeline_config

In `src/synergy_stats/artifacts.py`, replace direct plot calls with:

    from .figure_rerender import render_figures_from_run_dir

    ...
    render_figures_from_run_dir(output_dir, cfg)

Plan Change Note: Updated after implementation to record the finished shared rerender path, the direct-script import-path fix, the successful `default_run` validation (`131` figures rerendered, curated MD5 unchanged), and the remaining pre-existing end-to-end contract mismatch on `global_step/` and `global_nonstep/` subdirectory assertions.
