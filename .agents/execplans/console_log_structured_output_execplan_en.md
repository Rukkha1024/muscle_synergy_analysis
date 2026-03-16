# Enhance `main.py` Console Logs with Structured Intermediate Results

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository contains `.agents/PLANS.md`, and this document must be maintained in accordance with that file. This plan is written for a novice who only has the current working tree and this file.

## Purpose / Big Picture

The EMG synergy pipeline already writes a run log, but the console output is still too sparse to help a user confirm that each stage is behaving normally while `python main.py` is running. A user can see that a step started, but cannot quickly confirm whether the merged EMG table has the expected size, whether trial extraction produced the right number of slices, whether NMF selected plausible ranks and VAF values, or whether clustering/export finished with the expected summaries.

After this change, `python main.py --overwrite --out outputs/runs/console_log_structured` will still produce the same computational artifacts, but the console and run log will show each pipeline step as a clearly separated block with short, aligned key-value summaries. A user will be able to watch the run and verify the intermediate state without opening notebooks, CSV files, or Excel workbooks during execution.

## Progress

- [x] (2026-03-16 09:30Z) Reviewed the current pipeline entrypoint and confirmed that `main.py` executes 5 sequential steps, not 6.
- [x] (2026-03-16 09:40Z) Reviewed the current logging calls in `main.py` and `scripts/emg/01_load_emg_table.py` through `scripts/emg/05_export_artifacts.py`.
- [x] (2026-03-16 09:50Z) Confirmed that `scripts/emg/06_render_figures_only.py` exists as a separate utility CLI and is not part of the main pipeline run.
- [x] (2026-03-16 10:00Z) Identified reusable metadata already present in `bundle.meta`, `cluster_result`, and exported artifact paths, so the feature can remain logging-only.
- [ ] Capture a clean baseline run in a dedicated output directory before editing code.
- [ ] Create `src/emg_pipeline/log_utils.py` with shared formatting helpers for banners and key-value sections.
- [ ] Update `main.py` so step banners and completion timing derive from `STEP_FILES`.
- [ ] Replace one-line step summaries in `scripts/emg/01_load_emg_table.py` through `scripts/emg/05_export_artifacts.py` with structured sections.
- [ ] Re-run the pipeline into a second clean output directory and compare stable outputs with `scripts/emg/99_md5_compare_outputs.py`.
- [ ] Update this English plan and the Korean companion plan with the final implementation evidence, decisions, and outcomes.

## Surprises & Discoveries

- Observation: The active pipeline currently contains 5 steps in `main.py`, while `scripts/emg/06_render_figures_only.py` is a separate rerender utility and should not appear in step-count banners.
  Evidence: `main.py` defines `STEP_FILES` with five `scripts/emg/01_*.py` to `05_*.py` entries, and `06_render_figures_only.py` is a standalone CLI with its own argument parser.

- Observation: Passing one multiline string to `logging.info()` prefixes only the first line with the timestamp and logger metadata.
  Evidence: This is the standard behavior of Python's `logging` formatter. Per-line logging keeps every displayed line grep-friendly in both console and `run.log`.

- Observation: Step 3 already stores `n_components`, `vaf`, `extractor_backend`, `extractor_torch_device`, `extractor_torch_dtype`, and `extractor_metric_elapsed_sec` in each feature bundle.
  Evidence: `src/synergy_stats/nmf.py` writes these keys into `FeatureBundle.meta` inside `extract_trial_features()`.

- Observation: Step 4 clustering results already include `selection_status`, `k_gap_raw`, `k_selected`, `duplicate_trials`, `algorithm_used`, and `inertia`.
  Evidence: `src/synergy_stats/clustering.py` returns those fields from `cluster_feature_group()`.

- Observation: Step 5 already emits workbook-path and workbook-validation logs from library code inside `src/synergy_stats/artifacts.py`.
  Evidence: `export_results()` logs workbook save locations and validation summaries before returning control to `scripts/emg/05_export_artifacts.py`.

## Decision Log

- Decision: Rewrite the plan around the actual 5-step pipeline and treat `scripts/emg/06_render_figures_only.py` as out of scope.
  Rationale: The ExecPlan must match the current repository state so a novice can execute it without resolving contradictions.
  Date/Author: 2026-03-16 / Codex

- Decision: Keep the implementation logging-only. Do not modify the numerical logic of loading, trial slicing, NMF, clustering, or artifact export.
  Rationale: The user-visible goal is richer progress visibility during `main.py` execution, not a behavior change in the pipeline outputs.
  Date/Author: 2026-03-16 / Codex

- Decision: Use only the standard `logging` module and add a small helper module at `src/emg_pipeline/log_utils.py`.
  Rationale: The existing logging configuration already mirrors console and file output. A helper keeps formatting consistent without introducing dependencies.
  Date/Author: 2026-03-16 / Codex

- Decision: Emit one `logging.info()` call per visible log line rather than composing multiline payloads.
  Rationale: Every visible line should keep the timestamp prefix in both the console and `outputs/runs/<run_id>/logs/run.log`.
  Date/Author: 2026-03-16 / Codex

- Decision: Make the banner total derive from `len(STEP_FILES)` instead of a hardcoded number.
  Rationale: This avoids another drift if the pipeline step list changes later.
  Date/Author: 2026-03-16 / Codex

- Decision: Keep the existing workbook logs from `src/synergy_stats/artifacts.py` and add a structured export summary in the step script instead of replacing library-level logs.
  Rationale: Those workbook logs already communicate useful validation information and are outside the repetitive step-wrapper pattern this plan is cleaning up.
  Date/Author: 2026-03-16 / Codex

- Decision: Validate output stability with the repository's curated comparator `scripts/emg/99_md5_compare_outputs.py` instead of ad hoc hashing of only two files.
  Rationale: The comparator already encodes the stable artifact set and produces a clearer pass/fail result for a logging-only change.
  Date/Author: 2026-03-16 / Codex

## Outcomes & Retrospective

Implementation has not started yet. This revision corrects the ExecPlan so it matches the current repository state and gives an implementer a reproducible baseline-and-compare workflow.

## Context and Orientation

This repository contains an EMG (electromyography) synergy extraction pipeline. The main entrypoint is `main.py`. It loads YAML configuration, prepares a run directory, configures logging, and then executes the following five scripts in order:

    scripts/emg/01_load_emg_table.py
        Load the EMG parquet file, load event metadata from the workbook, and merge them into one EMG table.

    scripts/emg/02_extract_trials.py
        Slice the merged EMG table into one record per `subject-velocity-trial` window.

    scripts/emg/03_extract_synergy_nmf.py
        Run NMF (Non-negative Matrix Factorization) on each trial to produce `W` muscle-weight matrices and `H` time-activation matrices.

    scripts/emg/04_cluster_synergies.py
        Group the extracted synergy components into global `step` and `nonstep` clusters with gap-statistic-based clustering.

    scripts/emg/05_export_artifacts.py
        Export the final CSV, parquet, Excel, and figure artifacts for the run.

`scripts/emg/06_render_figures_only.py` also exists, but it is a separate utility command that rerenders figures from an existing run directory. It is not executed by `main.py` and is out of scope for this plan.

The current logging configuration lives in `main.py`. It uses `logging.basicConfig()` with an INFO-level formatter, one `FileHandler`, and one `StreamHandler`. That means every `logging.info()` call appears both on the console and in `outputs/runs/<run_id>/logs/run.log`.

The current user problem is not that the pipeline fails. The problem is that the visible logs are too compressed. Today, `main.py` prints a "Running step" line, and each script usually prints one short summary line. That is not enough for a user to verify data volume, selected trial counts, NMF summary quality, clustering selections, or export scope while the run is still in progress.

Terms used in this plan:

`NMF`: Non-negative Matrix Factorization. In this repository it decomposes each trial's EMG matrix into synergy weights `W_muscle` and time activations `H_time`.

`VAF`: Variance Accounted For. It is a number between 0 and 1 that describes how well the NMF reconstruction explains the original EMG data. Higher is better.

`Rank`: The number of synergy components chosen for one trial. In the code this is stored as `n_components`.

`Gap statistic`: A method for selecting the number of clusters `K` by comparing observed clustering quality to random reference data.

`Stable outputs`: The exported files that `scripts/emg/99_md5_compare_outputs.py` compares. These are the files expected to remain byte-for-byte unchanged by a logging-only modification.

## Plan of Work

Start by capturing a baseline run before editing code. Use a dedicated output directory such as `outputs/runs/console_log_baseline` and run the existing pipeline with `--overwrite` so the exported file counts and MD5 comparison are based on a clean directory. This baseline is the reference for proving that the implementation changes only logging behavior.

Create a new helper module at `src/emg_pipeline/log_utils.py`. This file should define a small set of formatting functions that call `logging.info()` internally. The helper should not own any run state. It should only emit a blank line, a divider, a title line, or aligned key-value rows. The goal is to keep formatting identical across the five pipeline scripts and `main.py`.

Update `main.py` next. Add a mapping from the five step filenames to human-readable step titles such as `Load EMG Table`, `Extract Trials`, `Extract Synergy (NMF)`, `Cluster Synergies`, and `Export Artifacts`. Replace the current `Running step: ...` line with a banner call that uses the current step number and `len(STEP_FILES)`. Measure elapsed wall-clock time around each `run_step(context)` call and print a completion line after each step. Keep the existing configuration, manifest, dry-run, and success/failure behavior unchanged.

Then replace the one-line summaries in each of the five step scripts with structured sections.

In `scripts/emg/01_load_emg_table.py`, log two sections. The first section should summarize the merged EMG table with row count, column count, selected subject count and names, velocity values, muscle channel count, missing-value count and ratio across the configured muscle columns, and the minimum/maximum EMG values across those same muscle columns. The second section should summarize the event metadata and selection columns already attached to the merged table. Include at least the event row count, the selected trial count, the split between selected step and selected nonstep trials, and the count of selected rows using surrogate window ends versus actual window ends.

In `scripts/emg/02_extract_trials.py`, log one section summarizing the extracted `trial_records`. Include the number of trials, the minimum and maximum duration in device frames, the number and names of represented subjects, and the velocity values represented in the extracted records.

In `scripts/emg/03_extract_synergy_nmf.py`, keep the run per-trial work unchanged, but replace the existing runtime and summary lines with structured sections. The runtime section should show the requested backend, resolved Torch device, and resolved Torch dtype. The summary section should aggregate the finished `feature_rows` and include trial count, rank distribution, VAF range, VAF mean and standard deviation, total extracted components, average extraction time per trial, and the set of actual backends used.

In `scripts/emg/04_cluster_synergies.py`, replace the runtime line and per-group result line with structured sections. The runtime section should show the clustering algorithm, Torch device, Torch dtype, restart batch size, and gap-reference batch size. Then log one section for each group in `context["cluster_group_results"]`. Each group section should show `k_gap_raw`, `k_selected`, `selection_status`, duplicate-trial count, inertia, and the algorithm actually used.

In `scripts/emg/05_export_artifacts.py`, keep `export_results(context)` intact. After it returns, add one structured summary section that counts files in the run directory on a clean `--overwrite` run. Include the output directory path, CSV count, Excel workbook count, parquet count, and figure count. Leave the workbook-path and workbook-validation logs emitted by `src/synergy_stats/artifacts.py` unchanged.

Finally, run the modified pipeline into a second clean output directory such as `outputs/runs/console_log_structured`, confirm that the new console/log-file format is visible, and compare the stable outputs against the baseline directory with the repository's MD5 comparison script. Update this plan and the Korean companion file with the implementation evidence and final notes before considering the task complete.

## Concrete Steps

Working directory:

    /home/alice/workspace/26-03-synergy-analysis

Create the baseline run before editing:

    python main.py --overwrite --out outputs/runs/console_log_baseline

Expected behavior:

    The command finishes successfully.
    The directory `outputs/runs/console_log_baseline` is created.
    The log file `outputs/runs/console_log_baseline/logs/run.log` contains the current short-form logging output.

Implement the logging helper and script updates in this order:

    1. Create `src/emg_pipeline/log_utils.py`.
    2. Modify `main.py`.
    3. Modify `scripts/emg/01_load_emg_table.py`.
    4. Modify `scripts/emg/02_extract_trials.py`.
    5. Modify `scripts/emg/03_extract_synergy_nmf.py`.
    6. Modify `scripts/emg/04_cluster_synergies.py`.
    7. Modify `scripts/emg/05_export_artifacts.py`.

Run the modified pipeline into a separate clean output directory:

    python main.py --overwrite --out outputs/runs/console_log_structured

Expected visible console shape:

    2026-03-16 18:00:00,000 INFO root: Loaded config from configs/global_config.yaml
    2026-03-16 18:00:00,001 INFO root: Run output directory: outputs/runs/console_log_structured
    2026-03-16 18:00:00,002 INFO root:
    2026-03-16 18:00:00,002 INFO root: ══════════════════════════════════════════════════════════
    2026-03-16 18:00:00,002 INFO root:   Step 1/5 : Load EMG Table
    2026-03-16 18:00:00,002 INFO root: ══════════════════════════════════════════════════════════
    2026-03-16 18:00:01,500 INFO root: [EMG Data]
    2026-03-16 18:00:01,500 INFO root:         Rows             : 474500
    2026-03-16 18:00:01,500 INFO root:         Columns          : 83
    2026-03-16 18:00:01,500 INFO root:         Subjects         : 5 (A, B, C, ...)
    2026-03-16 18:00:01,501 INFO root: [Event Metadata]
    2026-03-16 18:00:01,501 INFO root:         Selected trials  : 125 (step=63, nonstep=62)
    2026-03-16 18:00:01,501 INFO root: Step 1 done (1.50s)
    ...
    2026-03-16 18:07:30,000 INFO root: [Export Summary]
    2026-03-16 18:07:30,000 INFO root:         CSV files        : 8
    2026-03-16 18:07:30,000 INFO root:         Excel workbooks  : 2
    2026-03-16 18:07:30,000 INFO root:         Parquet files    : 1
    2026-03-16 18:07:30,000 INFO root:         Figures          : 131
    2026-03-16 18:07:30,000 INFO root: Step 5 done (120.00s)
    2026-03-16 18:07:30,001 INFO root: Pipeline completed successfully.

Compare stable outputs after the implementation:

    python scripts/emg/99_md5_compare_outputs.py \
        --base outputs/runs/console_log_baseline \
        --new outputs/runs/console_log_structured

Expected comparison result:

    MD5 comparison passed for curated stable files.

If the MD5 comparison reports `MISSING` or `DIFF`, stop and inspect the modified scripts before changing this plan's `Progress` section to completed.

## Validation and Acceptance

The change is accepted when all of the following are true.

Running `python main.py --overwrite --out outputs/runs/console_log_structured` succeeds without changing the numerical behavior of the pipeline. The console shows five step banners, one for each file in `STEP_FILES`, and each banner uses the current `len(STEP_FILES)` total so the visible output reads `Step 1/5` through `Step 5/5` in the current repository state.

Step 1 logs a structured EMG data summary and a structured event metadata summary. Step 2 logs a structured trial-extraction summary. Step 3 logs a structured NMF runtime summary and a structured NMF aggregate summary. Step 4 logs a structured clustering runtime summary and one structured result section per global group. Step 5 logs a structured export summary after `export_results(context)` finishes. The existing workbook save/validation logs emitted from `src/synergy_stats/artifacts.py` still appear.

The run log at `outputs/runs/console_log_structured/logs/run.log` contains the same structured content as the console because both outputs come from the same `logging` handlers.

The command

    python scripts/emg/99_md5_compare_outputs.py \
        --base outputs/runs/console_log_baseline \
        --new outputs/runs/console_log_structured

prints `MD5 comparison passed for curated stable files.`. This is the proof that the logging enhancement did not alter the stable pipeline artifacts.

## Idempotence and Recovery

All implementation steps in this plan are safe to repeat. The helper module and logging calls are additive code edits. The baseline and candidate runs use different output directories, so rerunning them does not destroy the comparison evidence as long as you keep the directory names distinct.

Use `--overwrite` whenever you regenerate either run directory. That keeps file-count logging deterministic by clearing any stale artifacts from prior attempts. If you need to retry after a partial edit, rerun the baseline and candidate commands with `--overwrite` in their own directories, then rerun the MD5 comparison.

If the implementation causes unexpected output changes, revert only the logging-related edits in `main.py`, `src/emg_pipeline/log_utils.py`, and `scripts/emg/01_load_emg_table.py` through `scripts/emg/05_export_artifacts.py`. Do not revert unrelated repository changes.

## Artifacts and Notes

Files to create or modify:

    src/emg_pipeline/log_utils.py
    main.py
    scripts/emg/01_load_emg_table.py
    scripts/emg/02_extract_trials.py
    scripts/emg/03_extract_synergy_nmf.py
    scripts/emg/04_cluster_synergies.py
    scripts/emg/05_export_artifacts.py
    .agents/execplans/console_log_structured_output_execplan_en.md
    .agents/execplans/console_log_structured_output_execplan_ko.md

Files explicitly out of scope:

    scripts/emg/06_render_figures_only.py
    src/synergy_stats/figure_rerender.py
    src/synergy_stats/artifacts.py

The workbook-path and workbook-validation logs from `src/synergy_stats/artifacts.py` are expected to remain as they are today. This plan adds a higher-level structured summary around them rather than removing them.

## Interfaces and Dependencies

Create `src/emg_pipeline/log_utils.py` with functions equivalent to the following signatures:

    def step_banner(step_num: int, total_steps: int, title: str) -> None:
        """Log a blank line plus a divider/title/divider banner."""

    def log_section(header: str, pairs: list[tuple[str, object]]) -> None:
        """Log one section header and aligned key-value rows."""

    def step_done(step_num: int, elapsed_seconds: float) -> None:
        """Log a one-line step completion summary."""

`main.py` must import `step_banner` and `step_done`, compute `total_steps = len(STEP_FILES)`, and map each step path in `STEP_FILES` to a visible title.

Each step script from `scripts/emg/01_load_emg_table.py` through `scripts/emg/05_export_artifacts.py` must import and use `log_section`. The helper should accept values that are already formatted as strings or can be converted with `str()`. The helper does not need to know pandas internals or configuration details.

No new third-party dependencies are required. Use the existing standard-library `logging` module plus already-installed project dependencies such as pandas, NumPy, and `collections.Counter` where those are useful for formatting summary statistics.

## Revision Note

2026-03-16: Rewrote this ExecPlan to match the current 5-step pipeline, removed the stale Step 6/posthoc references, synchronized the intended scope with the Korean companion plan, and replaced the weak two-file hash check with the repository's curated MD5 comparison workflow.
