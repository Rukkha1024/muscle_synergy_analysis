# Replace split step/nonstep clustering with pooled clustering in the main EMG pipeline / 메인 EMG 파이프라인의 step/nonstep 분리 clustering을 pooled clustering으로 교체

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `.agents/PLANS.md`. The English and Korean versions below describe the same plan and must be kept synchronized whenever the plan is revised.

## English Version

## Purpose / Big Picture

After this change, the main EMG pipeline will stop creating two separate clustering spaces, one for `step` trials and one for `nonstep` trials. Instead, for each enabled analysis mode, the pipeline will place all selected synergy feature rows into one pooled K-means search space and assign a single `group_id` of `pooled_step_nonstep`.

From the user’s perspective, this means the production pipeline will finally answer the same scientific question as `analysis/pooled_shared_specific_synergy`: whether step and nonstep trials occupy the same cluster vocabulary when they are clustered together, rather than after two independent clustering runs. A novice will be able to see the change working by running `main.py` with the fixture config and observing that each analysis mode emits exactly one clustering group, that the group identifier is `pooled_step_nonstep`, that representative `W/H` artifacts still exist, and that the old cross-group comparison files are gone.

## Progress

- [x] (2026-03-18 00:00Z) Read `.agents/AGENTS.md`, `.agents/PLANS.md`, and the relevant repository skills before authoring this plan.
- [x] (2026-03-18 00:05Z) Confirmed the user wants a full semantic replacement, not an optional configuration toggle.
- [x] (2026-03-18 00:10Z) Scoped the current split behavior to the main pipeline clustering stage and the downstream export and rerender layers that assume `global_step` plus `global_nonstep`.
- [x] (2026-03-18 00:15Z) Defined the target output contract: one pooled group per analysis mode, preserved core `all_*` artifacts, removed cross-group comparison artifacts, and added a simple pooled strategy-composition summary.
- [x] (2026-03-18 03:05Z) Replaced the split grouping wrapper in `scripts/emg/04_cluster_synergies.py` with one pooled clustering pass per analysis mode using `group_id="pooled_step_nonstep"`.
- [x] (2026-03-18 03:20Z) Updated `src/synergy_stats/artifacts.py`, `src/synergy_stats/figure_rerender.py`, `src/synergy_stats/figures.py`, and workbook wording so pooled runs export one discovered group figure, skip cross-group files, and write `pooled_cluster_strategy_summary.csv`.
- [x] (2026-03-18 03:30Z) Updated contract tests and helper fixtures for the pooled output contract; targeted `pytest` coverage now passes for clustering, artifacts, figure rerender, MD5 comparison, and end-to-end mode exports.
- [x] (2026-03-18 03:45Z) Ran the real fixture pipeline in `conda run -n cuda`, confirmed pooled-only mode artifacts, captured the expected MD5 mismatch versus the split-era reference, and confirmed reproducibility with a second pooled run plus passing MD5 comparison.
- [x] (2026-03-18 03:50Z) Committed the main pooled-clustering refactor with a Korean commit message of at least five lines.
- [x] (2026-03-18 03:55Z) Reviewer found one rerender regression for legacy split runs with missing cross-group CSVs; restored fail-fast behavior and added a regression test for the incomplete split artifact set.
- [ ] Complete the final review pass after the rerender regression fix.

## Surprises & Discoveries

- Observation: the low-level clustering engine is already generic enough to support pooled clustering. The step/nonstep split is introduced by the pipeline wrapper, not by the K-means engine itself.
  Evidence: the existing design already has a reusable clustering function that accepts a list of feature rows plus a `group_id`, while the main pipeline currently calls it once per split group.

- Observation: the export layer is the real second half of the refactor. Even if clustering becomes pooled, the current artifact-writing path still assumes the fixed pair `global_step` and `global_nonstep`.
  Evidence: mode-level export and figure rerender logic are based on fixed group-name assumptions and on the existence of cross-group comparison files.

- Observation: the analysis prototype should be treated as behavioral reference, not as code to import directly into the pipeline.
  Evidence: the repository architecture explicitly separates `scripts/` pipeline code from `analysis/` code, and the analysis folder is supposed to consume final outputs rather than become a runtime dependency of the pipeline.

- Observation: the fixture pipeline validation cannot be completed in the `module` environment because the fixture config resolves to the Torch NMF backend.
  Evidence: `main.py --config tests/fixtures/global_config.yaml` failed in `conda run -n module` with `ModuleNotFoundError: PyTorch is required for the Torch NMF backend`, while the same command succeeded in `conda run -n cuda`.

- Observation: the curated MD5 reference mismatch was narrower than the full behavioral refactor might suggest.
  Evidence: against `tests/reference_outputs/reference_baseline`, the MD5 helper reported only one missing stable file, `pooled_cluster_strategy_summary.csv`, because the existing stable-file set does not include split-only cross-group artifacts.

## Decision Log

- Decision: replace the default main-pipeline clustering behavior outright instead of adding a new YAML option.
  Rationale: the user explicitly asked to replace the existing split clustering with pooled clustering. A toggle would preserve an old behavior the user asked to retire and would expand the test matrix unnecessarily.
  Date/Author: 2026-03-18 / GPT-5.4 Pro

- Decision: keep the low-level K-means and K-search logic unchanged and only change how feature rows are grouped before clustering.
  Rationale: the scientific change is about pooling rows into one cluster space, not about changing the clustering algorithm, gap statistic, or duplicate-trial safeguards.
  Date/Author: 2026-03-18 / GPT-5.4 Pro

- Decision: use `pooled_step_nonstep` as the canonical pooled `group_id` everywhere in the main pipeline.
  Rationale: this matches the established naming in `analysis/pooled_shared_specific_synergy`, minimizes semantic drift, and makes output files self-explanatory.
  Date/Author: 2026-03-18 / GPT-5.4 Pro

- Decision: keep core output families such as `all_cluster_labels.csv`, representative `W/H`, minimal-unit exports, and trial metadata, but remove split-only cross-group comparison artifacts.
  Rationale: downstream analysis still needs the core artifacts and provenance columns, but cross-group cosine comparison is no longer meaningful when only one cluster space exists.
  Date/Author: 2026-03-18 / GPT-5.4 Pro

- Decision: add one small pooled summary artifact that reports, per pooled cluster, how many rows came from `step` and how many came from `nonstep`.
  Rationale: once the split comparison files disappear, users still need a direct, human-readable way to see the strategy composition of each pooled cluster without recomputing it manually from the label table.
  Date/Author: 2026-03-18 / GPT-5.4 Pro

## Outcomes & Retrospective

Implementation replaced the legacy split clustering wrapper with one pooled clustering pass per enabled analysis mode and kept the low-level clustering engine unchanged. The production output contract now shows `pooled_step_nonstep` in summaries, labels, representative artifacts, minimal-unit exports, and rerendered figures, while split-only cross-group comparison files are absent. A new `pooled_cluster_strategy_summary.csv` provides the direct step/nonstep composition audit that pooled runs need.

The most important downstream fix was making artifact export and figure rerender logic discover present `group_id` values instead of indexing a fixed `global_step` plus `global_nonstep` pair. Validation confirmed that targeted pooled tests pass, the fixture pipeline succeeds in the `cuda` environment, the split-era reference mismatch is intentional and limited to the new pooled summary file, and two pooled fixture runs match under the curated MD5 comparison.

## Context and Orientation

The repository has a strict separation between pipeline code and analysis code. In this repository, `scripts/` contains production pipeline stages that are orchestrated by `main.py`, while `analysis/` contains standalone statistical or exploratory workflows that consume pipeline outputs. The user asked to bring the clustering behavior of the pooled analysis into the main pipeline, but not to break the architecture by importing analysis code into pipeline runtime.

The current pipeline order remains unchanged. `main.py` runs a numbered sequence of scripts, including `scripts/emg/04_cluster_synergies.py` and `scripts/emg/05_export_artifacts.py`. The clustering stage receives synergy feature rows produced earlier in the pipeline. A “feature row” in this plan means one clustering input record that contains the synergy `W` weights plus metadata such as subject, velocity, trial number, analysis mode, and step/nonstep label.

An “analysis mode” in this plan means one arrangement of clustering inputs such as `trialwise` or `concatenated`. Pooling must happen inside each analysis mode, not across modes. If both modes are enabled, the pipeline must run one pooled clustering pass for `trialwise` and one pooled clustering pass for `concatenated`.

A “group_id” in this repository is a text label for a clustering space. It is carried through summaries, label tables, representative `W/H` tables, minimal-unit exports, and figures. Today the main pipeline uses two group IDs, `global_step` and `global_nonstep`. After this change, each mode must instead expose one group ID, `pooled_step_nonstep`.

A “cross-group artifact” means a file that compares the outputs of two independently clustered spaces, for example pairwise cosine similarity or a step-to-nonstep matching decision file. Those files become invalid after pooling because there is no longer a pair of separate spaces to compare.

The key files for this plan are as follows. `scripts/emg/04_cluster_synergies.py` is where the current split into step and nonstep groups is introduced. `src/synergy_stats/clustering.py` contains the low-level clustering engine and should remain mostly unchanged. `src/synergy_stats/artifacts.py` writes mode-level CSV and parquet outputs and currently assumes the two split groups. `src/synergy_stats/figure_rerender.py` and, if necessary, `src/synergy_stats/figures.py` render figures and also need to stop assuming the fixed split pair. `tests/test_synergy_stats/test_clustering_contract.py`, `tests/test_synergy_stats/test_end_to_end_contract.py`, and possibly `tests/test_synergy_stats/test_artifacts.py` must be updated to reflect the new behavior. `scripts/emg/99_md5_compare_outputs.py` must still be used for verification, but any wording or expectations tied to split clustering must be updated.

## Plan of Work

The first milestone is to replace the grouping logic in the clustering stage while preserving all earlier preprocessing and later orchestration. In `scripts/emg/04_cluster_synergies.py`, keep the validation that each selected trial has a clear strategy label, because the metadata remains scientifically important. However, stop building separate `global_step` and `global_nonstep` feature-row collections. For each analysis mode, gather all selected feature rows into one list, preserve each row’s `step_TF` or equivalent strategy metadata, and call the existing clustering engine one time with `group_id="pooled_step_nonstep"`. The returned context structure should stay backward-compatible at the outer level, meaning `analysis_mode_cluster_group_results[mode]` remains a dictionary keyed by group ID, but the only key now present is `pooled_step_nonstep`.

The second milestone is to make export logic dynamic rather than hard-coded to the split pair. In `src/synergy_stats/artifacts.py`, replace any iteration over a fixed tuple like `("global_step", "global_nonstep")` with iteration over the group IDs actually present in the clustering results for that mode. Preserve the existing core output families so downstream code still receives cluster labels, representative `W/H`, minimal units, clustering metadata, and trial window metadata. At the same time, gate cross-group comparison generation behind an explicit condition that both old split groups are present. For the new pooled default, those artifacts must not be written. Add one new additive CSV, tentatively named `pooled_cluster_strategy_summary.csv`, that reports per mode and per pooled cluster the count and fraction of rows coming from `step` versus `nonstep`. Build this from trial-level label metadata so the artifact remains simple and auditable.

The third milestone is to update figure generation so one arbitrary group ID is enough. In `src/synergy_stats/figure_rerender.py`, detect available groups from the actual exported CSV files rather than from a fixed expected pair. Render one cluster figure for each discovered group ID. For pooled runs, that means creating `figures/pooled_step_nonstep_clusters.png` and skipping any rerender attempt that requires cross-group CSV inputs. If `src/synergy_stats/figures.py` contains helpers that are parameterized by group name already, keep them and only change the caller. If there are helpers with fixed filenames or captions that mention split groups, generalize those strings so the pooled run produces correct titles and file paths.

The fourth milestone is to update tests and verification. In `tests/test_synergy_stats/test_clustering_contract.py`, update the contract so the clustering stage is expected to return exactly one group per mode and that group is `pooled_step_nonstep`. In `tests/test_synergy_stats/test_end_to_end_contract.py`, update expected files and summaries so cross-group artifacts are absent and the pooled group figure and pooled strategy summary are present. If `tests/test_synergy_stats/test_artifacts.py` encodes old file expectations, update it too. Keep tests behavior-focused: they should assert what a user can observe in the output tree rather than internal implementation details. For the MD5 helper, first run it against the existing split-era references to capture intentional diffs, then refresh or add the pooled reference outputs if the repository maintains curated fixtures, and finally rerun the comparison against the new pooled reference tree.

The fifth milestone is to verify, commit, and clean up. Run the fixture pipeline in the `module` conda environment, inspect the output tree, ensure only pooled grouping appears in summaries, and ensure cross-group files are absent. Then create at least one Git commit with a Korean commit message of five lines or more that reflects the user’s intent. Remove disposable temporary output folders that are not needed for checked-in references.

## Concrete Steps

Run all commands from the repository root.

1. Inspect the clustering stage and confirm where split grouping is introduced.

    conda run -n module python - <<'PY'
    from pathlib import Path
    path = Path("scripts/emg/04_cluster_synergies.py")
    print(path)
    print(path.read_text(encoding="utf-8-sig")[:2000])
    PY

   The reader should see code that gathers feature rows and assigns them to split group IDs before calling the clustering engine.

2. Inspect the low-level clustering engine and confirm it already accepts arbitrary `group_id` values.

    conda run -n module python - <<'PY'
    from pathlib import Path
    path = Path("src/synergy_stats/clustering.py")
    text = path.read_text(encoding="utf-8-sig")
    for needle in ["def cluster_feature_group", "group_id"]:
        print(f"{needle}: ", needle in text)
    PY

   The expected output is that both strings are present. This proves the engine is reusable.

3. Edit `scripts/emg/04_cluster_synergies.py` so each enabled analysis mode calls the clustering engine once with `group_id="pooled_step_nonstep"` and passes all selected rows together.

4. Edit `src/synergy_stats/artifacts.py` so it iterates over present group IDs, writes existing core outputs for each group that exists, skips cross-group outputs unless both split groups exist, and writes `pooled_cluster_strategy_summary.csv` for pooled runs.

5. Edit `src/synergy_stats/figure_rerender.py` and, if required, `src/synergy_stats/figures.py` so figures are rendered for discovered group IDs and pooled runs no longer require cross-group inputs.

6. Update tests.

    conda run -n module python -m pytest tests/test_synergy_stats/test_clustering_contract.py -q
    conda run -n module python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q

   Before the code change, one or more tests should fail if they are updated first. After implementation, the full selected test set should pass.

7. Run the fixture pipeline and inspect the output tree.

    conda run -n module python main.py --config tests/fixtures/global_config.yaml --out outputs/runs/fixture_pooled --overwrite

    find outputs/runs/fixture_pooled -maxdepth 3 -type f | sort

   The expected tree should include, for each enabled analysis mode, files such as `final_summary.csv`, `all_cluster_labels.csv`, `all_clustering_metadata.csv`, representative `W/H` exports, minimal-unit exports, `all_trial_window_metadata.csv`, `pooled_cluster_strategy_summary.csv`, and `figures/pooled_step_nonstep_clusters.png`. It should not include split-only cross-group comparison files.

8. Run MD5 comparison. If the repository still stores old split references, capture that the first comparison shows intentional differences. Then refresh pooled references if that is part of the repo’s fixture maintenance and rerun the comparison.

    conda run -n module python scripts/emg/99_md5_compare_outputs.py --base <reference_dir> --new outputs/runs/fixture_pooled

9. Commit with a Korean message of at least five lines.

    git status
    git add scripts/emg/04_cluster_synergies.py src/synergy_stats/artifacts.py src/synergy_stats/figure_rerender.py src/synergy_stats/figures.py tests/test_synergy_stats/test_clustering_contract.py tests/test_synergy_stats/test_end_to_end_contract.py tests/test_synergy_stats/test_artifacts.py scripts/emg/99_md5_compare_outputs.py
    git commit

   The commit message body must clearly state that the main pipeline now performs pooled clustering instead of split step/nonstep clustering and that exporters and tests were updated accordingly.

## Validation and Acceptance

Acceptance is entirely behavioral.

After running the fixture pipeline, every enabled analysis mode must show exactly one clustering group in the mode-level summaries. That one group must be identified as `pooled_step_nonstep`. The core output families must still exist so downstream users can inspect labels, representative `W/H`, minimal units, and trial metadata. The mode’s figure directory must include `pooled_step_nonstep_clusters.png`. The mode directory must also include `pooled_cluster_strategy_summary.csv`, and that file must show both strategy counts using metadata derived from the pooled labels.

At the same time, the mode directory must not include split-only cross-group artifacts such as `cross_group_w_pairwise_cosine.csv`, `cross_group_w_cluster_decision.csv`, or any figure whose logic depends on matching one split group to the other. If such a file still appears in a pooled run, the refactor is incomplete.

The clustering metadata and label outputs must preserve provenance columns that downstream analysis relies on. At minimum, the pooled outputs must still carry analysis mode, `group_id`, subject, velocity, trial number, and strategy label metadata so users can trace cluster membership back to original trials.

The selected test suite must pass in `conda run -n module`. If the repository maintains pooled fixture references, the MD5 comparison against those references must also pass. If split-era references are still present during transition, the comparison output must be recorded as intentional evidence rather than ignored silently.

## Idempotence and Recovery

This refactor is source-only and can be implemented incrementally. It is safe to rerun tests and fixture pipeline commands as many times as needed. Always use disposable output directories under `outputs/runs/` together with `--overwrite` so reruns replace prior artifacts cleanly.

Do not import runtime code from `analysis/`. That would violate the repository architecture and would make later recovery harder. If a change breaks the exporter or rerender path midway through implementation, stop editing unrelated files, fix the failing path, and rerun the same fixture command. Do not restore or modify files that are outside the scope of this plan.

If MD5 comparison fails against old split references, treat that as expected evidence during the transition. Refresh the curated reference outputs only after the pooled output contract is stable and the updated tests already pass.

## Artifacts and Notes

The most important behavioral evidence after implementation should look like this.

    outputs/runs/fixture_pooled/
      trialwise/
        final_summary.csv
        all_cluster_labels.csv
        all_clustering_metadata.csv
        all_representative_W_posthoc.csv
        all_representative_H_posthoc_long.csv
        all_minimal_units_W.csv
        all_minimal_units_H_long.csv
        all_trial_window_metadata.csv
        pooled_cluster_strategy_summary.csv
        figures/pooled_step_nonstep_clusters.png
      concatenated/
        final_summary.csv
        all_cluster_labels.csv
        all_clustering_metadata.csv
        all_representative_W_posthoc.csv
        all_representative_H_posthoc_long.csv
        all_minimal_units_W.csv
        all_minimal_units_H_long.csv
        all_trial_window_metadata.csv
        pooled_cluster_strategy_summary.csv
        figures/pooled_step_nonstep_clusters.png

The most important absence evidence should be this.

    outputs/runs/fixture_pooled/<mode>/cross_group_w_pairwise_cosine.csv   # absent
    outputs/runs/fixture_pooled/<mode>/cross_group_w_cluster_decision.csv   # absent
    outputs/runs/fixture_pooled/<mode>/figures/*cross_group*                # absent

The new pooled strategy summary should be a simple audit table, for example with columns such as `analysis_mode`, `group_id`, `cluster_id`, `strategy_label`, `n_rows`, and `fraction_within_cluster`. The exact names may vary, but the file must be easy for a human to read and to recompute from `all_cluster_labels.csv`.

## Interfaces and Dependencies

Keep `main.py` unchanged in its role as the orchestrator. The execution order of pipeline stages must not change.

In `scripts/emg/04_cluster_synergies.py`, preserve the public entry point:

    def run(context: dict) -> dict:

The returned context must still include the clustering results under the existing outer keys so later stages do not need a new orchestration contract. The required semantic change is that `analysis_mode_cluster_group_results[mode]` now contains one key, `pooled_step_nonstep`, rather than two split keys.

In `src/synergy_stats/clustering.py`, reuse the existing clustering engine rather than replacing it. If helper refactoring is needed for readability, keep it internal and do not change the scientific behavior of K-range search, gap-statistic selection, or duplicate-trial safeguards.

In `src/synergy_stats/artifacts.py`, preserve the public export entry point and make it accept arbitrary group IDs present in the clustering result payload. Use `polars` first when adding any new summary builder unless an existing downstream API requires `pandas`.

In `src/synergy_stats/figure_rerender.py`, preserve the public rerender entry point and make it discover group IDs from real artifacts. Cross-group figure rendering must become conditional on the simultaneous presence of both old split groups.

In the tests, assert user-visible behavior. Do not write tests that only prove an internal refactor happened. Each updated test should demonstrate that pooled clustering is what the user sees in the output tree and summaries.
