# Issue 008: Concatenated Source-Trial Window Provenance Manifest

**Status**: Done
**Created**: 2026-03-18

## Background

The current `concatenated` mode already preserves analysis-unit provenance such as `analysis_unit_id`, `source_trial_nums_csv`, and `analysis_source_trial_count`. However, the exported `all_trial_window_metadata.csv` still looks like true trial-window provenance even though, in `concatenated` mode, each row is really an analysis-unit-level summary with synthetic `trial_num=concat_step|concat_nonstep`.

This is a semantic mismatch for users. They can see which source trials were used, but they cannot directly inspect the per-source-trial analysis-window provenance from a dedicated CSV. The approved revision plan adds a new additive artifact, `all_concatenated_source_trial_windows.csv`, so users can inspect one source-trial window per row without breaking the existing `all_trial_window_metadata.csv` contract.

## Acceptance Criteria

- [x] `src/synergy_stats/concatenated.py` preserves `source_trial_details` inside concatenated analysis-unit metadata.
- [x] The exporter writes `all_concatenated_source_trial_windows.csv` under `outputs/runs/<run_id>/concatenated/`.
- [x] A `both` run also writes `outputs/runs/<run_id>/all_concatenated_source_trial_windows.csv` with only concatenated rows.
- [x] A `trialwise`-only run does not create `trialwise/all_concatenated_source_trial_windows.csv`.
- [x] The new CSV contains one row per source trial and includes `analysis_unit_id`, `trial_num`, `source_trial_num`, and `analysis_window_*` provenance columns.
- [x] Existing `all_trial_window_metadata.csv` behavior remains intact.
- [x] Validation includes targeted tests, smoke runs in the `module` conda environment, and reviewer-style diff inspection before close-out.

## Tasks

- [x] 1. Add source-trial detail payloads to concatenated analysis-unit metadata.
- [x] 2. Expand the payload into export-ready source-trial manifest rows.
- [x] 3. Write the new CSV in concatenated mode output and root combined output.
- [x] 4. Update tests for payload shape and artifact/file-contract behavior.
- [x] 5. Update `README.md` so users understand the old file versus the new concatenated provenance file.
- [x] 6. Run validation in the `module` environment and record the outcome.
- [x] 7. Commit with a Korean five-line message that references `issue008`.

## Notes

- Source plan: `.agents/execplans/Concatenated Source-Trial Window Provenance Revision ExecPlan.md`
- Scope boundary: additive pipeline change only. Keep `all_trial_window_metadata.csv` unchanged and add a new CSV instead of redefining the old file.
- Target artifact names:
  - `outputs/runs/<run_id>/concatenated/all_concatenated_source_trial_windows.csv`
  - `outputs/runs/<run_id>/all_concatenated_source_trial_windows.csv`
- Expected row meaning:
  - one row = one source trial window
  - `trial_num` = synthetic parent analysis unit key
  - `source_trial_num` = real original trial number
- Validation summary:
  - `conda run -n module python -m pytest tests/test_synergy_stats/test_concatenated_mode.py -q`
  - `conda run -n module python -m pytest tests/test_synergy_stats/test_artifacts.py -q`
  - `conda run -n module python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q`
  - `conda run -n module python main.py --config /tmp/codex_provenance_validation/global_config.yaml --mode concatenated --out /tmp/codex_provenance_validation/concat_run --overwrite`
  - `conda run -n module python main.py --config /tmp/codex_provenance_validation/global_config.yaml --mode both --out /tmp/codex_provenance_validation/both_run1 --overwrite`
  - `conda run -n module python main.py --config /tmp/codex_provenance_validation/global_config.yaml --mode both --out /tmp/codex_provenance_validation/both_run2 --overwrite`
- Validation observations:
  - The new source-trial provenance CSV had identical MD5 values across both reruns.
  - The curated MD5 script still reported a tiny rerun diff in `all_clustering_metadata.csv`, driven by a minute floating-point change inside `gap_sd_by_k_json`, not by the new provenance file.
