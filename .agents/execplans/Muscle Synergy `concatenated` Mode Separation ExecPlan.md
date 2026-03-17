# Muscle Synergy `concatenated` Mode Separation ExecPlan (EN)

After this change, a user can run the same main pipeline with `trialwise`, `concatenated`, or `both`. When `both` is selected, the two analyses run independently and write independent result bundles so they do not overwrite each other. The new `concatenated` mode does not stack all trials from all subjects into one global matrix. Instead, it concatenates resampled trials within each `subject × velocity × step_class(step/nonstep)` group, runs NMF on that subject-level super-trial, then splits the resulting `H` back into the original trial segments and averages them to produce a subject-level `H`. A user can verify success by checking `outputs/runs/<run_id>/trialwise/`, `outputs/runs/<run_id>/concatenated/`, the combined root `final.parquet`, and the synthetic `trial_num` values `concat_step` and `concat_nonstep`.

## Progress

- [x] (2026-03-17 11:55 UTC) The requirements brief is locked. `concatenated` must use subject-wise concatenation, must still support clustering, must write separated mode outputs, and must expose selectable execution modes `trialwise | concatenated | both`.
- [ ] Add the mode selection contract and runtime alias paths in `main.py` and `src/emg_pipeline/config.py`.
- [ ] Implement `src/synergy_stats/concatenated.py` as a subject-wise concatenation builder with `H` split-and-average logic.
- [ ] Convert `scripts/emg/03_extract_synergy_nmf.py` into a mode-aware stage that collects `trialwise` and `concatenated` rows independently in the same run.
- [ ] Update `scripts/emg/04_cluster_synergies.py` so that `concatenated` uses the normal clustering path and the identity special case is removed.
- [ ] Extend `src/synergy_stats/artifacts.py` and `scripts/emg/05_export_artifacts.py` so they write both mode-specific subdirectories and combined root artifacts.
- [ ] Add or update tests to lock the `H` split-average logic, concatenated clustering, and the combined root artifact contract.
- [ ] Update README and config examples to match the new mode contract.
- [ ] Validate the pipeline and tests inside the `module` conda environment.
- [ ] Implement only after approval. This document is a design plan; code changes have not started yet.

## Surprises & Discoveries

- Observation: The current artifact contract assumes trial-level extraction and fixed filenames.
  Evidence: the main workflow is split into `03_extract_synergy_nmf.py`, `04_cluster_synergies.py`, and `05_export_artifacts.py`, and the exporter uses fixed names such as `final_summary.csv`, `all_*.csv`, and `final.parquet`. This means `both` requires explicit mode-aware path separation to avoid file collisions.

- Observation: `build_group_exports()` can already tolerate string `trial_num` values.
  Evidence: it builds `trial_id` with string interpolation and does not rely on integer-only logic. This allows `concat_step` and `concat_nonstep` to pass through the current serializer shape with minimal churn.

- Observation: Some working trees may already contain a draft concatenated helper.
  Evidence: if such a helper stacks all selected trials across all subjects into one matrix, or bypasses clustering through an identity path, it does not satisfy the locked requirements and must be replaced.

## Decision Log

- Decision: The user-facing execution modes are exactly `trialwise`, `concatenated`, and `both`.
  Rationale: the user specified these exact values, and keeping older names such as `trial_clustered` would blur the difference between an analysis mode and an internal method label.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: A concatenated analysis unit is `subject × velocity × step_class`.
  Rationale: the repository’s base key is `subject-velocity-trial`, and the scientific comparison still lives within a subject and a fixed velocity, so dropping velocity would weaken provenance.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: The synthetic `trial_num` for concatenated units is `concat_step` or `concat_nonstep`.
  Rationale: this keeps the existing serializer shape mostly intact while making the row type obvious at a glance.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: Concatenated `H` is not exported on the stitched timeline. It is split back into source trial segments and averaged into a subject-level `H`.
  Rationale: the user explicitly locked this behavior because the input trials are already resampled.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: `concatenated` uses the same clustering path as `trialwise`. The identity clustering special case is removed.
  Rationale: the user explicitly stated that subject-wise concatenation still supports clustering.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: The exporter writes both mode-specific subdirectory artifacts and combined root artifacts.
  Rationale: results must remain separated by mode, and the old root filenames must still exist in a meaningful way when `both` is used.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: Root `final.parquet` becomes a combined parquet, and `final_trialwise.parquet` plus `final_concatenated.parquet` are added as explicit aliases.
  Rationale: the user locked that the existing root file contract must be modified rather than abandoned.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: Cross-group similarity remains only within each mode’s `step vs nonstep` comparison. No `trialwise ↔ concatenated` cross-mode similarity is added.
  Rationale: the user explicitly stated that the two modes are fundamentally different and do not need cross-mode similarity.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

- Decision: The repository default config uses `both`, and the CLI `--mode` flag can force `trialwise` or `concatenated`.
  Rationale: the primary purpose of this feature is to produce both result families in normal runs, while single-mode runs remain available as explicit overrides.
  Date/Author: 2026-03-17 / GPT-5.4 Pro

## Outcomes & Retrospective

Implementation has not started yet. Success is defined by observable behavior: one run can execute two independent analysis families, write two independent artifact trees, and also write a combined root artifact family with preserved mode provenance. Failure has three main forms. First, `both` still causes overwrites. Second, `concatenated` still collapses into one all-subject matrix or an identity clustering shortcut. Third, the combined `final.parquet` loses the information needed to tell trialwise rows from concatenated rows.

## Context and Orientation

The repository uses a root `main.py` orchestrator that calls thin wrapper scripts in an explicit order. The three key stages for this task are `scripts/emg/03_extract_synergy_nmf.py`, which extracts NMF features from each analysis unit, `scripts/emg/04_cluster_synergies.py`, which clusters extracted components into `global_step` and `global_nonstep`, and `scripts/emg/05_export_artifacts.py` plus `src/synergy_stats/artifacts.py`, which write CSV, workbook, figure, and parquet outputs.

This document fixes the terminology so a novice can implement the change without guessing. `trialwise` means the current behavior where each selected trial produces one NMF result. `concatenated` means that trials are first vertically stacked within the same `subject × velocity × step_class`, then one NMF run is performed on that subject-level super-trial. An `analysis unit` is the unit treated as a single row source by clustering and exporting. In `trialwise`, the analysis unit is one real trial. In `concatenated`, the analysis unit is one subject-level super-trial. `step_class` means either `step` or `nonstep`, while the clustering/export grouping keys remain `global_step` and `global_nonstep`. A `combined root artifact` is a root-level file that merges rows from all executed modes and includes a mode provenance column.

This task does not change the numerical optimization algorithms. The NMF backend, the gap-statistic selection logic, and the k-means objective remain as they are. The change is about how analysis units are constructed, how modes are routed, how outputs are laid out, and how concatenated `H` is post-processed. That boundary keeps the change surgical.

## Plan of Work

### 1. Redefine config and CLI around a `mode` contract.

Add `--mode {trialwise,concatenated,both}` to `main.py`. Extend `src/emg_pipeline/config.py` so the CLI can override `synergy_analysis.mode` in YAML. Set `synergy_analysis.mode: both` in `configs/synergy_stats_config.yaml`. If the current configuration surface still exposes `enabled_methods` or `trial_clustered`, remove those from the user-facing contract or keep them only as undocumented compatibility aliases. The run manifest must record the selected mode, the actual executed mode list, the combined parquet path, and the per-mode parquet alias paths.

The key goal in this step is to make “mode” the user contract. Some legacy internal helper names can remain temporarily if that reduces churn, but logs, manifests, paths, and config keys visible to users must say `trialwise`, not `trial_clustered`.

### 2. Implement `src/synergy_stats/concatenated.py` as a subject-wise concatenation builder.

This module must build concatenated analysis units from `trial_records`, `muscle_names`, and `cfg`. It first keeps only selected trials, then determines whether each trial belongs to `step` or `nonstep` from the existing metadata flags. It groups those trials by `(subject, velocity, step_class)`. Inside each group, it sorts by `trial_num`, vertically stacks the resampled EMG matrices, and runs the existing `extract_trial_features()` once on the stacked matrix.

The next part is the core scientific requirement. The returned `bundle.H_time` is defined on the stitched concatenated axis, so it must not be exported directly. The code must split that `H_time` back into source trial segments using the source frame lengths, then average those segments component-wise to create a subject-level `H_time`. Because the upstream contract says the input trials are already resampled, the code must raise an error if segment lengths differ inside one analysis unit instead of silently re-interpolating them at this stage. The final bundle stores the averaged `H_time`. Its metadata must include `aggregation_mode=concatenated`, `analysis_unit_id`, `source_trial_nums_csv`, `analysis_source_trial_count`, `analysis_selected_group`, `analysis_is_step`, `analysis_is_nonstep`, and `analysis_step_class`. The `SubjectFeatureResult` wrapper keeps the real `subject`, the real `velocity`, and the synthetic `trial_num` value `concat_step` or `concat_nonstep`.

This builder should not require every subject to have both classes present. The whole run must only guarantee that `global_step` and `global_nonstep` are both non-empty by the time stage 04 runs.

### 3. Make `scripts/emg/03_extract_synergy_nmf.py` mode-aware.

If the current file has a trial-level extraction helper, rename it or document it so it clearly means “trialwise.” This stage must call the mode resolver and build a dictionary such as `analysis_mode_feature_rows`. If `trialwise` is enabled, it runs the existing per-trial extraction path. If `concatenated` is enabled, it runs the new subject-wise builder. If `both` is enabled, it does both in the same run.

The stage must pass `context["analysis_modes"]` and `context["analysis_mode_feature_rows"]` forward. If legacy fallback behavior is still needed, `context["feature_rows"]` may store only the primary mode’s rows, but all new logic and all new tests must treat the per-mode dictionary as the authoritative interface.

### 4. Make `scripts/emg/04_cluster_synergies.py` use the normal clustering path for concatenated rows.

This stage keeps the current contract that each selected trial or analysis unit must map to exactly one global group. The important change is that `concatenated` no longer takes an identity clustering shortcut. Both `trialwise` and `concatenated` use `group_feature_rows_by_global_group()` to form `global_step` and `global_nonstep`, and both modes call `cluster_feature_group()`.

Any helper such as `identity_cluster_feature_group()` or any branching that suppresses clustering for concatenated mode must be removed. The cluster results stay mode-keyed. If a “primary mode” concept remains, it should only choose legacy aliases and not alter the scientific meaning of clustering.

### 5. Extend `src/synergy_stats/artifacts.py` into a two-layer exporter.

This module becomes the largest change. If it currently writes fixed filenames into one output directory, split that behavior into two layers. The first layer is a mode-specific writer. It writes the existing filenames under `run_dir/trialwise/` and `run_dir/concatenated/`. The second layer is a combined root writer. It concatenates the aggregate tables from all executed modes and rewrites the root `final_summary.csv`, `all_cluster_labels.csv`, `all_representative_W_posthoc.csv`, `all_representative_H_posthoc_long.csv`, `all_minimal_units_W.csv`, `all_minimal_units_H_long.csv`, and `all_trial_window_metadata.csv`. Every combined table must include an `aggregation_mode` column.

The root parquet follows the same rule. `run_dir/final.parquet` and the repository-level alias `outputs/final.parquet` become the combined minimal-W parquet. At the same time, add `outputs/final_trialwise.parquet` and `outputs/final_concatenated.parquet` for direct per-mode access. Keep `final.parquet` inside each mode-specific subdirectory as well.

Remove helpers such as `_hide_trial_level_exports_for_identity_mode()`. Concatenated mode now produces real labels, real clustered representative `W`, and real representative `H`. Therefore `cluster_labels.csv`, `all_cluster_labels.csv`, and the H tables must not be empty for concatenated mode. Because concatenated rows represent analysis units rather than raw trials, provenance columns must be explicit. Propagate `analysis_unit_id` and `source_trial_nums_csv` into the aggregate tables.

The root workbook behavior must also change. Keep `clustering_audit.xlsx` and `results_interpretation.xlsx` inside each mode subdirectory. In addition, regenerate combined root workbooks from the combined tables. Each relevant sheet must include `aggregation_mode`. These combined root workbooks are not another mode; they are merged reports. Do not create combined root figures. Figures stay mode-specific so their semantics do not collide.

### 6. Audit `src/synergy_stats/figures.py` and any figure re-render logic.

If figure filenames or titles assume that `trial_num` is numeric, update them so string values such as `concat_step` and `concat_nonstep` are handled safely. Concatenated mode should still be able to render analysis-unit figures, so any file naming logic under `figures/nmf_trials/` must accept string `trial_num` values without breaking. This is a safety audit, not a redesign of figure style.

### 7. Lock the new contract with tests.

Add a deterministic unit test for the concatenated `H` split-and-average helper. Use a synthetic `H` matrix and explicit segment lengths so the expected average can be calculated by hand. This test must avoid NMF randomness entirely.

Update the clustering contract tests so concatenated mode is expected to use normal clustering rather than an identity shortcut. Update the end-to-end contract tests so a `both` run must create `trialwise/` and `concatenated/` subdirectories, each with `final.parquet`, fixed CSV outputs, and workbooks. The root combined `final.parquet` and `final_summary.csv` must also exist and must include `aggregation_mode`. Concatenated final parquet rows must keep the real `subject` and `velocity` while using `trial_num=concat_step|concat_nonstep`. `concatenated/all_cluster_labels.csv` must be non-empty. Cross-group similarity files must live only inside each mode subdirectory, and there must be no root artifact that directly compares `trialwise` to `concatenated`.

### 8. Update the documentation.

Update `README.md` and the config example so the new contract is obvious. A user must be able to see that `--mode both` or `synergy_analysis.mode: both` produces two independent result bundles plus a combined root artifact family. The documentation must also explain `concatenated` in plain language. It is not “stack every subject into one matrix.” It is “stack step or nonstep trials within each subject and velocity to form a subject-level super-trial.”

## Concrete Steps

Run all commands from the repository root. Always use the `module` conda environment.

First, inspect the CLI surface.

    conda run -n module python main.py --help

After the change, the help text must include this argument.

    --mode {trialwise,concatenated,both}

Then lock the tests step by step.

    conda run -n module python -m pytest tests/test_synergy_stats/test_concatenated_mode.py -q
    conda run -n module python -m pytest tests/test_synergy_stats/test_clustering_contract.py -q
    conda run -n module python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q

The expected outcome is that the new concatenated helper test passes, and both the clustering contract and the end-to-end contract pass as well. Suitable new test names include:

    test_both_mode_writes_trialwise_and_concatenated_outputs
    test_concatenated_h_is_split_by_trial_and_averaged

Run smoke checks for all three modes.

    conda run -n module python main.py --config configs/global_config.yaml --mode trialwise --out outputs/runs/contract_trialwise --overwrite
    conda run -n module python main.py --config configs/global_config.yaml --mode concatenated --out outputs/runs/contract_concatenated --overwrite
    conda run -n module python main.py --config configs/global_config.yaml --mode both --out outputs/runs/contract_both --overwrite

After the `both` smoke run, at least these paths must exist.

    outputs/runs/contract_both/trialwise/final.parquet
    outputs/runs/contract_both/concatenated/final.parquet
    outputs/runs/contract_both/final.parquet
    outputs/final.parquet
    outputs/final_trialwise.parquet
    outputs/final_concatenated.parquet

A minimal combined parquet schema should look like this.

    aggregation_mode, group_id, subject, velocity, trial_num, analysis_unit_id, source_trial_nums_csv, muscle, W_value

## Validation and Acceptance

Acceptance is defined by behavior, not by a diff.

The CLI contract is correct if `main.py --help` exposes `--mode {trialwise,concatenated,both}`. Mode separation is correct if `--mode both` creates both `run_dir/trialwise/` and `run_dir/concatenated/`, and each directory contains its own `final.parquet` plus the fixed CSV and workbook outputs. The combined root contract is correct if `run_dir/final.parquet` and `outputs/final.parquet` exist and contain `aggregation_mode` values `{trialwise, concatenated}`. Subject-wise concatenated clustering is correct if `concatenated/all_cluster_labels.csv` is non-empty and its `trial_num` values are `concat_step` or `concat_nonstep`. Similarity boundaries are correct if there is no cross-mode similarity artifact, while each mode subdirectory still contains its own `cross_group_*` artifacts for `step vs nonstep`.

From the test perspective, the new unit test `test_concatenated_h_is_split_by_trial_and_averaged` should not exist or should fail before the change, and should pass after the change. The end-to-end test `test_both_mode_writes_trialwise_and_concatenated_outputs` should fail before the change and pass after the change. The relevant `synergy_stats` test suite must pass in full.

## Idempotence and Recovery

Runs with `--overwrite` must remain safe to repeat. The mode-specific subdirectories and the combined root artifacts all use deterministic paths, so rerunning the same config should recreate the same layout. If a step fails, rerun with the same `--out` path and `--overwrite` rather than manually deleting individual files. Input data files must remain untouched.

The most failure-prone point is the combined exporter schema merge because the two modes can carry slightly different columns. The combined root writer must therefore use a union-of-columns concat strategy and must add `aggregation_mode` explicitly. If recovery is needed after a schema mismatch, inspect `analysis_methods_manifest.json` and each mode-specific `all_*.csv` first to identify which mode is missing which column. Do not roll back unrelated files.

## Artifacts and Notes

The final run tree should look like this.

    outputs/runs/<run_id>/
      final_summary.csv
      all_cluster_labels.csv
      all_clustering_metadata.csv
      all_representative_W_posthoc.csv
      all_representative_H_posthoc_long.csv
      all_minimal_units_W.csv
      all_minimal_units_H_long.csv
      all_trial_window_metadata.csv
      final.parquet
      clustering_audit.xlsx
      results_interpretation.xlsx
      analysis_methods_manifest.json
      trialwise/
        final.parquet
        final_summary.csv
        ...
      concatenated/
        final.parquet
        final_summary.csv
        ...

A typical concatenated minimal row should look like this.

    aggregation_mode=concatenated
    group_id=global_step
    subject=S01
    velocity=60
    trial_num=concat_step
    analysis_unit_id=S01_v60_step_concat
    source_trial_nums_csv=1|3
    component_index=0
    muscle=TA
    W_value=...

A typical combined root summary row should look like this.

    aggregation_mode, group_id, n_trials, n_components, n_clusters, selection_method, selection_status

Here `n_trials` means the number of analysis units within that mode. In `trialwise`, that is the number of real trials. In `concatenated`, that is the number of subject-level concatenated units. This semantic difference is intentional.

## Interfaces and Dependencies

At the end of the change, the following interfaces must exist.

In `src/synergy_stats/concatenated.py`:

    def build_concatenated_feature_rows(
        trial_records: list[TrialRecord],
        muscle_names: list[str],
        cfg: dict[str, Any],
    ) -> list[SubjectFeatureResult]:
        ...

    def split_and_average_h_by_trial(
        concatenated_h: np.ndarray,
        segment_lengths: list[int],
    ) -> np.ndarray:
        ...

The first function returns subject-wise concatenated analysis units. The second function splits concatenated `H_time` by source trial boundaries and returns the averaged `H_time`. That second function must be deterministic and unit-testable.

In `src/synergy_stats/methods.py`, there must be a mode resolver. The function may be newly named `resolve_analysis_modes()` or may keep the existing `resolve_analysis_methods()` name, but the returned payload must understand the user-facing values `trialwise`, `concatenated`, and `both`. If any temporary compatibility aliases remain, they must not leak into artifact paths, manifests, logs, or user-visible config.

In `src/synergy_stats/artifacts.py`, the exporter must support both per-mode export and combined root export. At minimum it must return each mode’s output directory, each mode’s parquet path, and the combined parquet path. The current pandas-based writer does not need to be rewritten from scratch. Extend it, but handle union-of-columns concatenation and `aggregation_mode` injection explicitly.

The numerical backends stay unchanged. Keep the existing NMF solver, torch or k-means clustering backend, and gap-statistic logic. This task only needs changes to analysis-unit construction, routing, and export behavior.

## Revision Note

This is the initial draft written immediately after the requirements were locked with the user. The defining changes are subject-wise concatenation, `H` split-and-average reconstruction, mode-specific subdirectories plus combined root artifacts, synthetic `trial_num=concat_step|concat_nonstep`, and the explicit removal of cross-mode similarity.