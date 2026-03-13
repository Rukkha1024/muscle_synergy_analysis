# Duplicate Assignment Audit Summary

## 1) Executive summary

Ambiguities / missing:
- Paper-like audit used the checked-in `compare_Cheung` runtime overrides `--kmeans-restarts 10 --gap-ref-n 5 --gap-ref-restarts 3` because the committed `report.md` was generated that way, while the code defaults remain `1000/500/100`.
- Production baseline clustering has no downstream canonical relabeling stage for member assignments; duplicate checks beyond raw group labels are therefore only meaningful in the paper-like path where step-vs-nonstep centroid matching exists.

실제 duplicate는 paper-like unconstrained 경로에서 존재한다. `duplicate_unit_rate`는 28/125 = 0.224, `excess_duplicate_ratio`는 `30/503 = 0.060`이고, `duplicate_pair_rate`는 `30/852 = 0.035`이다. 이 수치는 `analysis/compare_Cheung,2021`의 실제 현재 코드 경로를 audit script에서 재실행해 얻었고, checked-in report와 같은 override runtime을 사용했다.

forced reassignment는 repo에 실제로 존재한다. production 경로에서는 `src/synergy_stats/clustering.py::cluster_feature_group()`가 `_fit_kmeans()` 직후 `_enforce_unique_trial_labels()`를 호출하고, 그 뒤 `_duplicate_trials()`로 duplicate를 다시 검사한다. post-force 기준 전체 duplicate는 0/125 = 0.000였고, pre-force 기준 전체 duplicate는 35/125 = 0.280였다.

이 문제가 downstream interpretation을 얼마나 흔드는지는 “paper-like unconstrained label을 biological module identity처럼 바로 읽느냐”에 달려 있다. duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다. 다만 duplicate pair의 평균 cosine similarity가 non-duplicate보다 뚜렷하게 높아, 일부 중복은 거의 같은 synergy가 같은 cluster로 들어간 사례에 가깝다.

## 2) Actual pipeline map

Production path:
- `main.py` -> `scripts/emg/03_extract_synergy_nmf.py::run()` -> `src/synergy_stats/nmf.py::extract_trial_features()` -> `src/synergy_stats/nmf.py::_normalize_components()` -> `scripts/emg/04_cluster_synergies.py::run()` -> `src/synergy_stats/clustering.py::cluster_feature_group()` -> `src/synergy_stats/clustering.py::_fit_kmeans()` -> `src/synergy_stats/clustering.py::_enforce_unique_trial_labels()` -> `src/synergy_stats/clustering.py::_duplicate_trials()` -> `src/synergy_stats/artifacts.py::export_results()`.
- NMF unit: trial.
- Clustering input vector: L2-normalized `W_muscle[:, component_index]`.
- K rule: `k_min = max(2, subject_hmax)` to `k_max = min(max_clusters, n_components)`, then return the first post-force zero-duplicate `K`.
- K-means details: `configs/synergy_stats_config.yaml` sets `algorithm=cuml_kmeans` with sklearn fallback, `repeats=25`, `random_state=42`, `max_iter=300`, and squared-Euclidean inertia.
- Config source: `configs/synergy_stats_config.yaml`.

Paper-like path:
- `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py::main()` -> `_collect_trial_results()` -> `run_paper_nmf_for_trial()` -> `_build_vector_rows()` -> `_run_group_clustering()` -> `compute_gap_statistic()` -> `identify_common_clusters()` -> `match_cluster_centroids()`.
- NMF unit: trial.
- Clustering input vector: row-wise L2-normalized `normalized_structures`.
- K rule: plain k-means for `K = 2..20`, then gap statistic chooses the first `K` satisfying `Gap(k) >= Gap(k+1) - s(k+1)`.
- K-means details: `_plain_kmeans_once()` uses `sklearn.cluster.KMeans(..., n_init=1, algorithm="lloyd")` after `_sample_initial_centroids()` chooses centroid seeds from observed vectors, and `_best_plain_kmeans_solution()` repeats that `10` times per `K` in this audit run.
- This path has no active within-trial duplicate reassignment.

Label-space distinction:
- Raw group-specific label: actual `cluster_id` emitted by k-means inside each group.
- Downstream canonical label: derived only for the paper-like path from actual step-vs-nonstep Hungarian matching. Stored member labels are not rewritten by repo code; the audit computed this canonical space explicitly to test whether duplicate counts change after matching.
- Result: paper-like raw and canonical duplicate counts were `28/125` vs `28/125` at the unit level, so downstream matching did not remove duplicates.

## 3) Final K and sensitivity

Paper-like selected K from the checked-in runtime:
- `global_step`: `11`
- `global_nonstep`: `6`

Production selected K from the actual uniqueness-enforced search:
- `global_step`: `7`
- `global_nonstep`: `5`

Across the paper-like `K` range, gap statistic, `duplicate_unit_rate`, and `excess_duplicate_ratio` are stored in `k_sensitivity.csv` and plotted in `plots/`. The main practical question was whether slightly larger `K` values sharply reduce duplicate frequency, and this audit records the full observed curve rather than just the final selected `K`.

## 4) Main numbers

Paper-like overall:
- `duplicate_unit_rate`: 28/125 = 0.224
- `excess_duplicate_ratio`: `30/503 = 0.060`
- `duplicate_pair_rate`: `30/852 = 0.035`
- `units_with_Nsyn_gt_K`: `0/125 = 0.000`
- `global_step duplicate_unit_rate`: 3/53 = 0.057
- `global_nonstep duplicate_unit_rate`: 25/72 = 0.347
- top subject-level duplicate_unit_rate:
- 권유영: 1/1 = 1.000
- 유병한: 4/5 = 0.800
- 조민석: 4/7 = 0.571
- 김유민: 4/8 = 0.500
- 이인섭: 2/4 = 0.500

Production selected-K overall:
- pre-force `duplicate_unit_rate`: 35/125 = 0.280
- post-force `duplicate_unit_rate`: 0/125 = 0.000
- post-force `units_with_Nsyn_gt_K`: `0/125 = 0.000`
- `global_step` post-force `duplicate_unit_rate`: 0/53 = 0.000
- `global_nonstep` post-force `duplicate_unit_rate`: 0/72 = 0.000

## 5) Forced reassignment findings

forced reassignment 유무:
- 있음. 정확한 개입 위치는 `src/synergy_stats/clustering.py::_enforce_unique_trial_labels()`.
- 호출 순서는 `cluster_feature_group()` inside `for n_clusters ...` -> `_fit_kmeans()` -> `_enforce_unique_trial_labels()` -> `_duplicate_trials()`이다.

pre/post duplicate 변화:
- pre-force overall `duplicate_unit_rate`: 35/125 = 0.280
- post-force overall `duplicate_unit_rate`: 0/125 = 0.000

reassignment cost 증가량:
- reassigned synergies: `44/486 = 0.091`
- fixed raw-centroid squared assignment cost delta: `10.846`
- fixed raw-centroid assignment distance delta: `7.065`
- recomputed clustering inertia delta: `8.503`

남은 예외 사례:
- post-force duplicate units: `0`
- `Nsyn > K` post-force units: `0`
- production post-force duplicate가 남아 있으면 `reassignment_stats.csv`의 `summary_*`와 `component` row, 그리고 `per_unit_metrics.csv`에서 바로 추적할 수 있다.

## 6) Interpretation

- 같은 unit 내부 duplicate가 드물어서 해석에 큰 영향이 없는지: duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다.
- 같은 unit 내부 duplicate가 자주 발생해서 cluster를 biological module identity처럼 읽기 어려운지: paper-like unconstrained 경로 기준 `duplicate_unit_rate=0.224`, `duplicate_pair_rate=0.035`이므로, 해석 강도는 이 수치와 함께 읽어야 한다.
- 문제가 특정 group/subject/K에 국한되는지: group별 값은 `global_step=0.057`, `global_nonstep=0.347`이고, worst-case unit 10개는 아래 표에 정리했다.

Duplicate similarity summary:
- duplicate pair cosine mean: `0.452` from `30` pair(s)
- non-duplicate pair cosine mean: `0.295` from `822` pair(s)
- duplicate pair scalar-product mean: `0.452`
- non-duplicate pair scalar-product mean: `0.295`
- Because clustering vectors are already L2-normalized before clustering in both paths, cosine similarity and scalar product are numerically the same up to floating-point noise.

Worst cases:
| subject_id | group | trial_id | Nsyn | chosen K | synergy_indexes | assigned cluster | centroid distance | pairwise similarity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 김유민 | global_nonstep | 김유민_v70.0_T9 | 5 | 6 | `[0, 1, 2, 3, 4]` | `["3", "1", "3", "0", "1"]` | `{"0": 0.549013, "1": 0.659589, "2": 0.696915, "3": 0.448748, "4": 0.433426}` | `[{"cluster": "3", "cosine_similarity": 0.481788, "pair": [0, 2], "scalar_product": 0.481788}, {"cluster": "1", "cosine_similarity": 0.533472, "pair": [1, 4], "scalar_product": 0.533472}]` |
| 조민석 | global_nonstep | 조민석_v30.0_T6 | 5 | 6 | `[0, 1, 2, 3, 4]` | `["0", "0", "1", "1", "3"]` | `{"0": 0.565239, "1": 0.925013, "2": 0.579333, "3": 0.614243, "4": 0.588598}` | `[{"cluster": "0", "cosine_similarity": 0.196322, "pair": [0, 1], "scalar_product": 0.196322}, {"cluster": "1", "cosine_similarity": 0.434751, "pair": [2, 3], "scalar_product": 0.434751}]` |
| 김민정 | global_nonstep | 김민정_v20.0_T3 | 4 | 6 | `[0, 1, 2, 3]` | `["1", "1", "5", "3"]` | `{"0": 0.454914, "1": 0.454716, "2": 0.720381, "3": 0.669785}` | `[{"cluster": "1", "cosine_similarity": 0.73177, "pair": [0, 1], "scalar_product": 0.73177}]` |
| 가윤호 | global_nonstep | 가윤호_v60.0_T9 | 3 | 6 | `[0, 1, 2]` | `["1", "4", "1"]` | `{"0": 0.323493, "1": 0.588441, "2": 0.649658}` | `[{"cluster": "1", "cosine_similarity": 0.714216, "pair": [0, 2], "scalar_product": 0.714216}]` |
| 정혜진 | global_nonstep | 정혜진_v20.0_T4 | 4 | 6 | `[0, 1, 2, 3]` | `["1", "2", "4", "1"]` | `{"0": 0.465879, "1": 0.53682, "2": 0.728463, "3": 0.487855}` | `[{"cluster": "1", "cosine_similarity": 0.662716, "pair": [0, 3], "scalar_product": 0.662716}]` |
| 유병한 | global_nonstep | 유병한_v110.0_T2 | 6 | 6 | `[0, 1, 2, 3, 4, 5]` | `["4", "0", "3", "2", "1", "1"]` | `{"0": 0.49295, "1": 0.79157, "2": 0.550342, "3": 0.449829, "4": 0.674005, "5": 0.358327}` | `[{"cluster": "1", "cosine_similarity": 0.611275, "pair": [4, 5], "scalar_product": 0.611275}]` |
| 유병한 | global_step | 유병한_v110.0_T3 | 7 | 11 | `[0, 1, 2, 3, 4, 5, 6]` | `["0", "8", "2", "5", "3", "7", "7"]` | `{"0": 0.634427, "1": 0.335207, "2": 0.364941, "3": 0.511485, "4": 0.537029, "5": 0.796314, "6": 0.324879}` | `[{"cluster": "7", "cosine_similarity": 0.578179, "pair": [5, 6], "scalar_product": 0.578179}]` |
| 최지유 | global_nonstep | 최지유_v35.0_T6 | 3 | 6 | `[0, 1, 2]` | `["2", "1", "1"]` | `{"0": 0.566655, "1": 0.556662, "2": 0.574376}` | `[{"cluster": "1", "cosine_similarity": 0.554427, "pair": [1, 2], "scalar_product": 0.554427}]` |
| 조민석 | global_nonstep | 조민석_v30.0_T7 | 5 | 6 | `[0, 1, 2, 3, 4]` | `["0", "3", "2", "1", "1"]` | `{"0": 0.462972, "1": 0.571084, "2": 0.655922, "3": 0.50694, "4": 0.602145}` | `[{"cluster": "1", "cosine_similarity": 0.549994, "pair": [3, 4], "scalar_product": 0.549994}]` |
| 이인섭 | global_nonstep | 이인섭_v30.0_T5 | 2 | 6 | `[0, 1]` | `["1", "1"]` | `{"0": 0.657147, "1": 0.545373}` | `[{"cluster": "1", "cosine_similarity": 0.54602, "pair": [0, 1], "scalar_product": 0.54602}]` |


## 7) Recommendation

B: 결과는 쓸 수 있으나 duplicate caveat를 반드시 명시해야 함

## Reproduction

Run from repo root:

```bash
conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py
```

Q1. paper-like unconstrained pipeline에서 같은 trial/session 내 duplicate assignment는 실제로 얼마나 발생하는가?
A1. `duplicate_unit_rate`는 28/125 = 0.224, `excess_duplicate_ratio`는 `30/503 = 0.060`, `duplicate_pair_rate`는 `30/852 = 0.035`였다.

Q2. forced reassignment는 repo에 실제로 존재하는가? 존재하면 정확히 어디서 개입하는가?
A2. 존재한다. `src/synergy_stats/clustering.py::cluster_feature_group()`가 `_fit_kmeans()` 직후 `src/synergy_stats/clustering.py::_enforce_unique_trial_labels()`를 호출해서 같은 trial 내부 duplicate label을 줄이거나 제거하려고 개입한다.

Q3. forced reassignment는 duplicate를 없애는 대신 assignment cost를 얼마나 증가시키는가?
A3. selected production K 기준 전체 reassigned synergies는 `44/486 = 0.091`였고, fixed raw-centroid squared assignment cost는 `10.846`, fixed raw-centroid distance sum은 `7.065`, recomputed inertia는 `8.503`만큼 증가했다.

Q4. 이 duplicate 문제는 biological interpretation을 실제로 흔드는 수준인가?
A4. duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다. 다만 duplicate pair의 평균 cosine similarity가 non-duplicate보다 뚜렷하게 높아, 일부 중복은 거의 같은 synergy가 같은 cluster로 들어간 사례에 가깝다. 따라서 최종 권고는 `B`에 해당한다.
