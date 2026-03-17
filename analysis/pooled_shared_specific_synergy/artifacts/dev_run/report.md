# Pooled Shared/Specific Synergy Report

## Research Question

This analysis asks whether step and nonstep synergies occupy the same pooled cluster space when all trial-level `W` vectors are clustered together, and how strongly each shared cluster is dominated by one condition or balanced across both conditions.

## Inputs

- Config: `configs/global_config.yaml`
- Baseline run: `outputs/runs/default_run`
- EMG parquet: `/mnt/c/Users/Alice/OneDrive - 청주대학교/근전도 분석 코드/shared_files/output/03_post_processed_min_max_only/min-max_norm_only.parquet`
- Event workbook: `/mnt/c/Users/Alice/OneDrive - 청주대학교/연구실 자료/연구실_노인균형프로토콜/데이터 정리-설문, 신체계측, 기타 데이터/perturb_inform.xlsm`

## Methodology

- Selected trials were reconstructed from the event workbook and required to match baseline keys exactly (`n_trials=125`, `n_subjects=24`).
- Trial-level NMF was re-extracted per selected trial with the pipeline-aligned VAF threshold rule (`VAF >= 0.90`).
- Effective NMF backend: `torchnmf`.
- Effective clustering backend: `torch_kmeans`.
- Pooled clustering used `k_lb=7`, `k_gap_raw=16`, and `k_selected=17` with a zero-duplicate constraint.
- Final pooled component count: `493`.

## Results

- Duplicate trial count at selected `K`: `0`.
- Unique step subjects represented in pooled members: `21`.
- Unique nonstep subjects represented in pooled members: `24`.

### Cluster Occupancy Summary

| cluster_id | n_members_total | n_members_step | n_members_nonstep | subject_coverage_step | subject_coverage_nonstep | step_nonstep_subcentroid_cosine |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 37 | 18 | 19 | 13 | 11 | 0.987 |
| 1 | 35 | 17 | 18 | 10 | 11 | 0.987 |
| 2 | 23 | 12 | 11 | 6 | 8 | 0.948 |
| 3 | 22 | 14 | 8 | 11 | 7 | 0.970 |
| 4 | 13 | 7 | 6 | 5 | 6 | 0.953 |
| 5 | 44 | 17 | 27 | 9 | 11 | 0.992 |
| 6 | 26 | 10 | 16 | 7 | 11 | 0.947 |
| 7 | 21 | 9 | 12 | 8 | 8 | 0.986 |
| 8 | 21 | 8 | 13 | 7 | 10 | 0.981 |
| 9 | 36 | 26 | 10 | 15 | 6 | 0.967 |
| 10 | 33 | 17 | 16 | 9 | 11 | 0.982 |
| 11 | 26 | 9 | 17 | 5 | 13 | 0.988 |
| 12 | 15 | 5 | 10 | 5 | 6 | 0.914 |
| 13 | 63 | 23 | 40 | 11 | 18 | 0.995 |
| 14 | 28 | 14 | 14 | 7 | 9 | 0.973 |
| 15 | 18 | 7 | 11 | 6 | 7 | 0.973 |
| 16 | 32 | 15 | 17 | 8 | 8 | 0.990 |

### High Sub-centroid Similarity Clusters

| cluster_id | step_nonstep_subcentroid_cosine | n_members_step | n_members_nonstep |
| --- | --- | --- | --- |
| 13 | 0.995 | 23 | 40 |
| 5 | 0.992 | 17 | 27 |
| 16 | 0.990 | 15 | 17 |
| 11 | 0.988 | 9 | 17 |
| 0 | 0.987 | 18 | 19 |
| 1 | 0.987 | 17 | 18 |
| 7 | 0.986 | 9 | 12 |
| 10 | 0.982 | 17 | 16 |
| 8 | 0.981 | 8 | 13 |
| 14 | 0.973 | 14 | 14 |
| 15 | 0.973 | 7 | 11 |
| 3 | 0.970 | 14 | 8 |
| 9 | 0.967 | 26 | 10 |
| 4 | 0.953 | 7 | 6 |
| 2 | 0.948 | 12 | 11 |
| 6 | 0.947 | 10 | 16 |
| 12 | 0.914 | 5 | 10 |

## Figure Guide

- `pooled_clusters.png`: shows each pooled centroid with its pooled representative `H`, so we can see the shared cluster vocabulary at a glance.
- `step_vs_nonstep_W.png`: compares step-only and nonstep-only sub-centroids within each cluster, highlighting whether muscle composition is shared or condition-specific.
- `step_vs_nonstep_H.png`: overlays step and nonstep representative activations within each cluster, exposing timing or magnitude shifts even when `W` stays similar.
- `occupancy_summary.png`: separates raw member counts from subject-normalized occupancy, reducing the risk of over-interpreting clusters dominated by a few subjects.
- `k_selection_diagnostic.png`: shows how the gap-statistic recommendation and the zero-duplicate feasibility rule jointly determined the final `K`.
- `subcentroid_similarity_heatmap.png`: summarizes cross-cluster cosine similarity between step and nonstep sub-centroids, making diagonal or off-diagonal matches easy to spot.

## Generated Files

- `figures/pooled_clusters.png`
- `figures/step_vs_nonstep_W.png`
- `figures/step_vs_nonstep_H.png`
- `figures/occupancy_summary.png`
- `figures/k_selection_diagnostic.png`
- `figures/subcentroid_similarity_heatmap.png`
- `pooled_cluster_members.csv`
- `pooled_cluster_summary.csv`
- `pooled_representative_W.csv`
- `pooled_representative_H_long.csv`
- `checksums.md5`

## Reproduction

Run from the repository root:

```bash
conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
  --config configs/global_config.yaml \
  --baseline-run outputs/runs/default_run \
  --outdir analysis/pooled_shared_specific_synergy/artifacts/<run_name> \
  --overwrite
```
