# Duplicate Assignment Audit for compare_Cheung

## 1) Executive summary

Ambiguities / missing:
- Source review did not find a within-trial forced-reassignment call in `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`, and the executed raw outputs still contain duplicates, so the path behaves as unconstrained in practice.
- This audit intentionally uses the checked-in compare_Cheung runtime overrides `--kmeans-restarts 10 --gap-ref-n 5 --gap-ref-restarts 3` because the committed `analysis/compare_Cheung,2021/report.md` was generated that way, while the script defaults remain `1000/500/100`.

실제 duplicate는 `analysis/compare_Cheung,2021`의 paper-like unconstrained 경로에서 존재한다. raw group-specific label 기준 전체 `duplicate_unit_rate`는 28/125 = 0.224, `excess_duplicate_ratio`는 `30/503 = 0.060`, `duplicate_pair_rate`는 `30/852 = 0.035`였다.

forced reassignment는 이번 source-of-truth 코드 경로에는 없다. source review에서 within-trial/session uniqueness constraint를 강제하는 후처리 호출을 찾지 못했고, 실행된 raw output에도 duplicate가 `28/125 = 0.224` 남아 있어 이 경로가 실질적으로 unconstrained임을 확인했다.

이 문제가 downstream biological interpretation을 흔드는 정도는 raw label 기준 duplicate가 얼마나 자주 나타나는지에 달려 있다. duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다. duplicate pair의 평균 cosine similarity가 non-duplicate보다 높아서, 일부 중복은 실제로 꽤 비슷한 synergy가 같은 cluster에 함께 들어간 사례에 가깝다.

## 2) Actual pipeline map

`analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py` 기준 실행 순서:
- `load_baseline_inputs()` -> `select_trials_from_manifest()` -> `build_trial_matrix_dict()`로 selected trial set을 확정한다.
- `_collect_trial_results()`가 각 trial의 EMG matrix에 대해 `run_paper_nmf_for_trial()`을 호출한다.
- `run_paper_nmf_for_trial()`은 multiplicative-update NMF를 rank search로 반복하고, `structures`를 row-wise L2 norm으로 정규화한 `normalized_structures`를 만든다.
- `_build_vector_rows()`가 trial 내부 각 synergy를 독립 sample로 펼쳐 `vector` column을 만든다.
- `compute_cheung_gap_statistic()`이 candidate `K`별 ordinary pooled k-means를 평가하고, `_best_plain_kmeans_solution()`의 SSE를 사용해 gap statistic을 계산한다.
- 최종 selected `K`의 label은 raw group-specific label space를 이룬다.
- `identify_common_clusters()`가 subject-invariant centroid를 정의하고, `match_cluster_centroids()`가 step/nonstep centroid를 Hungarian matching으로 연결해 downstream canonical label space를 만든다.
- forced reassignment / deduplication / unique matching은 cluster membership assignment 단계에는 개입하지 않는다. `linear_sum_assignment()`는 centroid matching에만 사용된다.

핵심 파라미터:
- NMF unit: trial
- clustering input unit: trial 내부 각 synergy vector
- normalization: `run_paper_nmf_for_trial()`의 `normalized_structures = structures / ||structures||_2`
- distance metric: squared Euclidean objective (`_objective()`)
- centroid initialization: data-point sampling (`_sample_initial_centroids()`)
- KMeans engine: `sklearn.cluster.KMeans(..., algorithm="lloyd", n_init=1)`
- observed-data restarts: `10`
- gap reference datasets: `5`
- reference-dataset restarts: `3`
- final K rule: 첫 `k`에 대해 `gap(k) >= gap(k+1) - sd(k+1)`를 만족하면 그 `k`를 선택, 없으면 최대 `K`

## 3) Final K and sensitivity

selected K는 `global_step=11`, `global_nonstep=6`였다. 전체 K 후보에 대한 gap statistic, duplicate rate, SSE는 아래 표와 `results/k_sensitivity.csv`, `results/plots/`에서 재현 가능하다.

| group_id | K | gap | SSE | duplicate_unit_rate | excess_duplicate_ratio | units_with_Nsyn_gt_K |
| --- | --- | --- | --- | --- | --- | --- |
| global_nonstep | 2 | 0.797 | 122.980 | 0.972 | 0.493 | 65 |
| global_nonstep | 3 | 0.900 | 106.027 | 0.806 | 0.307 | 41 |
| global_nonstep | 4 | 0.986 | 93.004 | 0.556 | 0.185 | 17 |
| global_nonstep | 5 | 1.015 | 87.063 | 0.403 | 0.119 | 3 |
| global_nonstep | 6 | 1.042 | 82.660 | 0.347 | 0.100 | 0 |
| global_nonstep | 7 | 1.064 | 78.538 | 0.125 | 0.033 | 0 |
| global_nonstep | 8 | 1.094 | 74.103 | 0.097 | 0.026 | 0 |
| global_nonstep | 9 | 1.133 | 70.103 | 0.083 | 0.022 | 0 |
| global_nonstep | 10 | 1.147 | 67.505 | 0.083 | 0.022 | 0 |
| global_nonstep | 11 | 1.170 | 64.876 | 0.042 | 0.011 | 0 |
| global_nonstep | 12 | 1.197 | 62.471 | 0.069 | 0.019 | 0 |
| global_nonstep | 13 | 1.218 | 60.115 | 0.028 | 0.007 | 0 |
| global_nonstep | 14 | 1.244 | 57.566 | 0.028 | 0.007 | 0 |
| global_nonstep | 15 | 1.265 | 55.203 | 0.014 | 0.004 | 0 |
| global_nonstep | 16 | 1.259 | 54.306 | 0.014 | 0.004 | 0 |
| global_nonstep | 17 | 1.261 | 53.351 | 0.042 | 0.011 | 0 |
| global_nonstep | 18 | 1.295 | 51.336 | 0.000 | 0.000 | 0 |
| global_nonstep | 19 | 1.309 | 50.105 | 0.000 | 0.000 | 0 |
| global_nonstep | 20 | 1.314 | 49.656 | 0.014 | 0.004 | 0 |
| global_step | 2 | 0.665 | 120.813 | 0.943 | 0.549 | 49 |
| global_step | 3 | 0.774 | 103.524 | 0.792 | 0.361 | 38 |
| global_step | 4 | 0.843 | 92.081 | 0.679 | 0.253 | 26 |
| global_step | 5 | 0.899 | 83.639 | 0.509 | 0.189 | 10 |
| global_step | 6 | 0.973 | 75.619 | 0.377 | 0.129 | 3 |
| global_step | 7 | 1.039 | 68.414 | 0.302 | 0.094 | 1 |
| global_step | 8 | 1.082 | 64.450 | 0.283 | 0.077 | 0 |
| global_step | 9 | 1.121 | 60.314 | 0.132 | 0.039 | 0 |
| global_step | 10 | 1.156 | 56.469 | 0.038 | 0.013 | 0 |
| global_step | 11 | 1.209 | 52.982 | 0.057 | 0.013 | 0 |
| global_step | 12 | 1.212 | 51.708 | 0.075 | 0.017 | 0 |
| global_step | 13 | 1.255 | 49.222 | 0.019 | 0.004 | 0 |
| global_step | 14 | 1.259 | 48.557 | 0.000 | 0.000 | 0 |
| global_step | 15 | 1.267 | 46.604 | 0.038 | 0.009 | 0 |
| global_step | 16 | 1.275 | 45.470 | 0.019 | 0.004 | 0 |
| global_step | 17 | 1.275 | 44.482 | 0.019 | 0.004 | 0 |
| global_step | 18 | 1.305 | 43.215 | 0.000 | 0.000 | 0 |
| global_step | 19 | 1.304 | 42.540 | 0.019 | 0.004 | 0 |
| global_step | 20 | 1.328 | 41.594 | 0.000 | 0.000 | 0 |

## 4) Main numbers

raw group-specific label:
- overall `duplicate_unit_rate`: 28/125 = 0.224
- overall `excess_duplicate_ratio`: `30/503 = 0.060`
- overall `duplicate_pair_rate`: `30/852 = 0.035`
- overall `units_with_Nsyn_gt_K`: `0/125 = 0.000`
- `global_step duplicate_unit_rate`: 3/53 = 0.057
- `global_nonstep duplicate_unit_rate`: 25/72 = 0.347

downstream canonical label:
- overall `duplicate_unit_rate`: 28/125 = 0.224
- `global_step duplicate_unit_rate`: 3/53 = 0.057
- `global_nonstep duplicate_unit_rate`: 25/72 = 0.347
- canonical label은 raw duplicate를 줄이는 단계가 아니라 matched/unmatched centroid naming 단계이므로, duplicate가 생기거나 사라지는지는 label collapse 여부와 common-centroid mapping에 의해 해석해야 한다.

subject-level 편차 상위 5개:
- 권유영: 1/1 = 1.000
- 유병한: 4/5 = 0.800
- 조민석: 4/7 = 0.571
- 김유민: 4/8 = 0.500
- 이인섭: 2/4 = 0.500

## 5) Forced reassignment findings

이번 감사의 source-of-truth인 `analysis/compare_Cheung,2021` 코드 경로에는 forced reassignment가 없다.
- State 1: 존재함. ordinary k-means + gap statistic selected K 결과.
- State 2: 없음. forced reassignment 직전 상태를 따로 정의할 수 없다.
- State 3: 없음. forced reassignment 후 상태를 따로 정의할 수 없다.

따라서 assignment cost 증가량, reassigned synergy count, transition table은 이번 analysis scope에서는 해당 사항이 없다. `results/`에도 `reassignment_stats.csv`를 생성하지 않았다.

## 6) Interpretation

- raw label 기준 해석: duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다.
- similarity 비교: duplicate cosine mean `0.452` vs non-duplicate cosine mean `0.295`. duplicate scalar-product mean `0.452`, non-duplicate scalar-product mean `0.295`.
- 정규화 기준: clustering 입력 vector가 이미 L2-normalized이므로 cosine similarity와 scalar product는 수치적으로 거의 같다.
- cross-group matching 이후 canonical label 기준 duplicate는 overall `28/125 = 0.224`로 raw label과 분리해서 읽어야 한다.

worst duplicate units:
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

실행:

```bash
conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py
```

검증:

```bash
conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py
```

산출물:
- report: `analysis/duplicate_assignment_audit/report.md`
- reproducible artifacts: `analysis/duplicate_assignment_audit/results/`

Q1. paper-like unconstrained pipeline에서 같은 trial/session 내 duplicate assignment는 실제로 얼마나 발생하는가?
A1. raw group-specific label 기준 `duplicate_unit_rate`는 28/125 = 0.224, `excess_duplicate_ratio`는 `30/503 = 0.060`, `duplicate_pair_rate`는 `30/852 = 0.035`였다.

Q2. forced reassignment는 repo에 실제로 존재하는가? 존재하면 정확히 어디서 개입하는가?
A2. `analysis/compare_Cheung,2021` 코드 경로 안에는 존재하지 않는다. source review에서 within-trial uniqueness를 강제하는 reassignment 호출을 찾지 못했고, 실행된 raw output에도 duplicate가 `28/125 = 0.224` 남아 있어 ordinary k-means assignment가 그대로 유지된다고 판단했다.

Q3. forced reassignment는 duplicate를 없애는 대신 assignment cost를 얼마나 증가시키는가?
A3. 이번 source-of-truth 경로에는 forced reassignment 단계 자체가 없어서 해당 사항이 없다. 따라서 증가한 assignment cost도 `n/a`다.

Q4. 이 duplicate 문제는 biological interpretation을 실제로 흔드는 수준인가?
A4. duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다. duplicate pair의 평균 cosine similarity가 non-duplicate보다 높아서, 일부 중복은 실제로 꽤 비슷한 synergy가 같은 cluster에 함께 들어간 사례에 가깝다. 따라서 최종 권고는 `B`에 해당한다.
