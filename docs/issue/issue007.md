# Issue 007: Pooled Shared-Specific Synergy Analysis Workflow

**Status**: Done
**Created**: 2026-03-15

## Background

The current EMG synergy pipeline clusters `global_step` and `global_nonstep` separately, so the same `cluster_id` cannot be interpreted as a shared condition-level identity. The approved ExecPlan in `.agents/execplans/onet_cluster.md` defines an analysis-only workflow that re-extracts trial synergies, pools all step and nonstep structure vectors into one shared clustering space, and exports cluster-level summaries, figures, and a human-readable report without changing the baseline pipeline.

This work is needed so the user can inspect whether a pooled cluster is shared across conditions, how strongly each condition occupies that cluster, how many subjects contribute to it, and how step and nonstep representative `H` profiles differ inside the same cluster.

## Acceptance Criteria

- [x] `analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py` exists and supports `--dry-run`, `--baseline-run`, `--outdir`, and `--overwrite`.
- [x] The analysis validates exact agreement between baseline `all_trial_window_metadata.csv` and event-derived trial keys and step/nonstep labels before clustering.
- [x] The pooled clustering search uses gap statistic plus the zero-duplicate constraint and records `k_lb`, `k_gap_raw`, and `k_selected`.
- [x] The run writes `pooled_cluster_members.csv`, `pooled_cluster_summary.csv`, `pooled_representative_W.csv`, and `pooled_representative_H_long.csv`.
- [x] The run writes the 6 planned figures under `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/`.
- [x] The run writes a human-readable artifact report at `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/report.md`.
- [x] Validation includes dry-run, full execution, output schema/file checks, reviewer pass, and deterministic MD5 comparison of rerun outputs for the required deliverables (all user-facing artifacts matched; only `run_metadata.json` kept tiny floating-point drift).

## Tasks

- [x] 1. Create the analysis-only folder `analysis/pooled_shared_specific_synergy/` with the main entry script and folder-level report.
- [x] 2. Rebuild the selected trial table from config inputs and validate it against `outputs/runs/default_run/all_trial_window_metadata.csv`.
- [x] 3. Re-extract trial-level NMF features and pool all step/nonstep structure vectors into one clustering table.
- [x] 4. Run pooled clustering with gap-statistic selection and zero-duplicate enforcement.
- [x] 5. Export pooled member, summary, representative `W`, and representative `H` artifacts.
- [x] 6. Generate the 6 planned figures and the artifact `report.md`.
- [x] 7. Run dry-run/full validation, rerun MD5 comparison, reviewer checks, and commit with a Korean five-line message.

## Notes

- Source plan: `.agents/execplans/onet_cluster.md`
- Scope boundary: analysis-only. Do not modify `scripts/emg/*` or overwrite `outputs/runs/default_run/*`.
- Expected output root:
  - `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/`
- Primary outputs:
  - `pooled_cluster_members.csv`
  - `pooled_cluster_summary.csv`
  - `pooled_representative_W.csv`
  - `pooled_representative_H_long.csv`
  - `figures/pooled_clusters.png`
  - `figures/step_vs_nonstep_W.png`
  - `figures/step_vs_nonstep_H.png`
  - `figures/occupancy_summary.png`
  - `figures/k_selection_diagnostic.png`
  - `figures/subcentroid_similarity_heatmap.png`
  - `report.md`
- Validation run used the following practical overrides to keep turnaround reasonable in the `module` environment while preserving the pooled logic: `--nmf-backend sklearn_nmf --clustering-algorithm sklearn_kmeans --repeats 40 --gap-ref-n 20 --gap-ref-restarts 10 --uniqueness-candidate-restarts 80`.
- Observed validation result: dry-run passed with `125` selected trials and `24` selected subjects; full run produced `486` pooled components with `k_lb=7`, `k_gap_raw=13`, `k_selected=16`, and zero duplicates at the selected `K`.
