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
- Effective NMF backend: `sklearn_nmf`.
- Effective clustering backend: `sklearn_kmeans`.
- Pooled clustering used `k_lb=7`, `k_gap_raw=13`, and `k_selected=16` with a zero-duplicate constraint.
- Final pooled component count: `486`.

## Results

- Duplicate trial count at selected `K`: `0`.
- Unique step subjects represented in pooled members: `21`.
- Unique nonstep subjects represented in pooled members: `24`.

### Cluster Occupancy Summary

| cluster_id | n_members_total | n_members_step | n_members_nonstep | subject_coverage_step | subject_coverage_nonstep | step_nonstep_subcentroid_cosine |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 32 | 14 | 18 | 10 | 10 | 0.978 |
| 1 | 22 | 9 | 13 | 6 | 8 | 0.968 |
| 2 | 38 | 14 | 24 | 9 | 12 | 0.991 |
| 3 | 21 | 8 | 13 | 6 | 7 | 0.975 |
| 4 | 54 | 25 | 29 | 13 | 13 | 0.994 |
| 5 | 27 | 16 | 11 | 11 | 9 | 0.949 |
| 6 | 27 | 13 | 14 | 9 | 10 | 0.970 |
| 7 | 29 | 9 | 20 | 5 | 13 | 0.985 |
| 8 | 31 | 16 | 15 | 9 | 8 | 0.990 |
| 9 | 34 | 22 | 12 | 14 | 7 | 0.955 |
| 10 | 37 | 12 | 25 | 7 | 12 | 0.986 |
| 11 | 23 | 13 | 10 | 9 | 6 | 0.867 |
| 12 | 22 | 9 | 13 | 7 | 12 | 0.941 |
| 13 | 24 | 13 | 11 | 7 | 8 | 0.957 |
| 14 | 25 | 14 | 11 | 9 | 7 | 0.983 |
| 15 | 40 | 19 | 21 | 12 | 12 | 0.998 |

### High Sub-centroid Similarity Clusters

| cluster_id | step_nonstep_subcentroid_cosine | n_members_step | n_members_nonstep |
| --- | --- | --- | --- |
| 15 | 0.998 | 19 | 21 |
| 4 | 0.994 | 25 | 29 |
| 2 | 0.991 | 14 | 24 |
| 8 | 0.990 | 16 | 15 |
| 10 | 0.986 | 12 | 25 |
| 7 | 0.985 | 9 | 20 |
| 14 | 0.983 | 14 | 11 |
| 0 | 0.978 | 14 | 18 |
| 3 | 0.975 | 8 | 13 |
| 6 | 0.970 | 13 | 14 |
| 1 | 0.968 | 9 | 13 |
| 13 | 0.957 | 13 | 11 |
| 9 | 0.955 | 22 | 12 |
| 5 | 0.949 | 16 | 11 |
| 12 | 0.941 | 9 | 13 |
| 11 | 0.867 | 13 | 10 |

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
