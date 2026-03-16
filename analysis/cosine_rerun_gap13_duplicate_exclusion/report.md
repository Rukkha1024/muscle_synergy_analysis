# K=13 duplicate-component exclusion rerun report

## Research Question

`default_run`의 baseline cross-group figure는 step 그룹에서 `K=13`이 아닌 `K=16`을 사용한다.  
step 그룹을 gap statistic 원래 값인 `K=13`으로 고정하고, duplicate가 된 step component만 제외한 뒤 다시 cosine similarity를 계산하면 결과가 어떻게 달라지는가?

## Data Summary

- baseline input bundle: `outputs/runs/default_run/`
- step baseline status: `k_gap_raw=13`, `k_selected=16`, `selection_status=success_gap_escalated_unique`
- nonstep baseline status: `k_gap_raw=14`, `k_selected=14`
- fixed rerun target: `global_step` only, `K=13`
- reconstructed step trials/components: `53 trials`, `229 components`

## Analysis Methodology

- **Step clustering rule**: `global_step` minimal W export를 사용해 fixed `K=13`을 다시 계산하되, baseline uniqueness search와 같은 방식으로 `K=13` 후보 1000개 중 duplicate trial 수가 가장 적은 candidate를 선택했다.
- **Observed objective check**: baseline metadata의 `observed_objective_by_k_json["13"] = 49.9510498046875`와 rerun의 fixed-`K=13` observed objective를 비교하되, GPU/환경 차이를 고려해 `--objective-atol` 허용 오차 안에서 일치 여부를 기록했다.
- **Duplicate handling**: min-duplicate candidate에서 같은 trial 안에 같은 cluster로 2개 이상 배정된 step component가 있으면, 해당 trial-cluster pair 내부에서 centroid cosine similarity가 가장 높은 component 1개만 남기고 나머지 component를 제외했다.
- **Nonstep reference**: baseline `global_nonstep` representative W를 그대로 사용했다.
- **Cross-group similarity**: baseline과 동일하게 representative W row를 L2-normalize한 뒤 cosine similarity와 Hungarian assignment(`linear_sum_assignment`)를 적용했다.
- **Threshold**: `0.8`
- **Coordinate & sign conventions**:
  - Axis & Direction Sign

    | Axis | Positive (+) | Negative (-) | 대표 변수 |
    |------|---------------|---------------|-----------|
    | AP (X) | 해당 없음 | 해당 없음 | N/A |
    | ML (Y) | 해당 없음 | 해당 없음 | N/A |
    | Vertical (Z) | 해당 없음 | 해당 없음 | N/A |

  - Signed Metrics Interpretation

    | Metric | (+) meaning | (-) meaning | 판정 기준/참조 |
    |--------|--------------|--------------|----------------|
    | cosine similarity | 더 유사함 | 반대 방향 패턴 | representative W 간 cosine |

  - Joint/Force/Torque Sign Conventions

    | Variable group | (+)/(-) meaning | 추가 규칙 |
    |----------------|------------------|-----------|
    | EMG synergy W weights | 부호 해석 없음 | NMF W는 nonnegative 가중치로 취급 |

## Results

### 1. `K=13` candidate와 duplicate-component exclusion

- fixed `K=13` observed objective: `49.951050`
- baseline expected objective: `49.951050`
- absolute difference: `0.000000` (`objective_atol=0.05` 이내)
- min-duplicate candidate objective: `54.276535`
- min-duplicate candidate seed / restart: `1300973` / `931`
- baseline audit과 일치한 duplicate trial:
  - `유병한_v110.0_T6`
  - `조민석_v30.0_T2`
- 실제 제외된 duplicate component:
  - `유병한_v110.0_T6`: cluster `6`, component `5` 제외
  - `조민석_v30.0_T2`: cluster `0`, component `2` 제외

### 2. Cross-group decision 결과

| Group | same_synergy | group_specific_synergy |
|------|--------------:|-----------------------:|
| step | 11 | 2 |
| nonstep | 11 | 3 |

추가로, rerun 이후 step cluster 수는 `13`, nonstep reference cluster 수는 `14`였다.

### 3. Baseline `default_run`과의 비교

baseline `default_run`의 decision summary는 다음과 같았다.

| Group | same_synergy | group_specific_synergy |
|------|--------------:|-----------------------:|
| step | 11 | 5 |
| nonstep | 11 | 3 |

이번 rerun에서는 `same_synergy` **개수**가 baseline과 동일하게 `11쌍`이었고, step group-specific cluster가 `5 -> 2`로 줄었다.  
즉, `K=16`으로 올려서 얻었던 추가 step-specific 분할 일부는 `K=13` 구조를 유지한 상태에서도 duplicate component 제거만으로 흡수될 수 있음을 시사한다.

### 4. Figure checksum 비교

- `cross_group_cosine_heatmap.png`: baseline과 MD5 불일치
- `cross_group_decision_summary.png`: baseline과 MD5 불일치
- `cross_group_matched_w.png`: baseline과 MD5 불일치

세 figure 모두 checksum이 달라서, rerun 결과가 baseline과 다른 이미지 바이트로 저장되었음을 확인했다.  
다만 이 값은 폰트/렌더링 환경에도 영향을 받을 수 있으므로, 분석 변화의 직접 근거는 decision table의 cluster count 변화와 함께 해석해야 한다.

### 5. SPM 1D H-curve comparison (step vs nonstep)

W가 유사한 same_synergy 11쌍에서 H(activation timing)가 step/nonstep 간 어디서 다른지를 SPM 1D two-sample t-test로 검정했다.

- **모수 검정**: `spm1d.stats.ttest2` (Welch, equal_var=False), α=0.05
- **비모수 검정**: `spm1d.stats.nonparam.ttest2`, 10,000 permutations, α=0.05
- **다중비교 보정**: 11쌍의 cluster-level p-value에 BH-FDR 보정 적용

| match_id | step_cluster | nonstep_cluster | n_step | n_nonstep | p_param | p_corr_param | p_nonparam | p_corr_nonparam | sig |
|----------|-------------|-----------------|--------|-----------|---------|-------------|------------|----------------|-----|
| same_synergy_01 | 0 | 5 | 20 | 21 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_02 | 1 | 10 | 19 | 18 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_03 | 2 | 7 | 22 | 22 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_04 | 3 | 12 | 10 | 13 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_05 | 4 | 13 | 21 | 17 | 1.0000 | 1.0000 | 0.0415 | 0.2283 | n.s. |
| same_synergy_06 | 5 | 2 | 28 | 21 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_07 | 6 | 4 | 12 | 18 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_08 | 7 | 9 | 13 | 15 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_09 | 9 | 8 | 22 | 36 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |
| same_synergy_10 | 11 | 11 | 12 | 23 | 0.0283 | 0.3115 | 0.0117 | 0.1287 | n.s. |
| same_synergy_11 | 12 | 6 | 15 | 15 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | n.s. |

BH-FDR 보정 후 11쌍 모두 유의하지 않았다. same_synergy_10 (step cluster 11 ↔ nonstep cluster 11)만 보정 전 비모수 p=0.0117로 경향성을 보였으나, FDR 보정 후 p=0.1287로 유의 수준 미달이었다.

이는 W가 유사하게 매칭된 쌍에서 H(activation timing)도 step/nonstep 간에 통계적으로 구분되지 않음을 시사한다.

## Interpretation

이 rerun은 “gap statistic이 제안한 구조 K=13”을 완전히 포기하지 않아도, duplicate component를 국소적으로 제거하는 방식으로 cross-group similarity를 다시 볼 수 있음을 보여준다.

중요한 점은 `same_synergy` **쌍 수**가 baseline과 동일하게 `11`로 유지되었다는 것이다.  
다만 이번 분석은 쌍의 **개수**를 비교한 것이지, baseline `K=16` 결과와 rerun `K=13` 결과의 correspondence identity를 일대일로 정렬해 검증한 것은 아니다. 따라서 “같은 수의 대응쌍이 남는다”까지는 말할 수 있지만, “같은 대응쌍이 그대로 유지된다”까지 단정하지는 않는다.

반면 step group-specific cluster 수는 `5`에서 `2`로 줄었다. 따라서 baseline에서 `K=16`으로 올리며 생긴 step-specific 분화 일부는, 엄밀한 의미의 새로운 시너지라기보다 duplicate avoidance 때문에 더 잘게 나뉜 결과일 가능성을 함께 고려해야 한다.

이번 분석은 “step K를 16으로 올려야만 cross-group matching이 성립한다”기보다, **`K=13 + duplicate-component exclusion`만으로도 matching count 수준의 큰 틀은 유지된다**는 해석을 뒷받침한다.

SPM 1D 분석에서는 W가 유사하게 매칭된 11쌍 모두에서 H curve의 step/nonstep 간 유의차가 없었다 (BH-FDR 보정 후 전체 n.s.). 이는 cross-group W matching으로 짝지은 시너지 쌍이 activation timing 측면에서도 그룹 간 차이가 없음을 추가적으로 확인해 준다.

## Reproduction

```bash
# Cross-group cosine rerun
conda run --no-capture-output -n cuda python \
  analysis/cosine_rerun_gap13_duplicate_exclusion/analyze_cosine_rerun_gap13_duplicate_exclusion.py \
  --overwrite

# SPM 1D H-curve comparison
conda run --no-capture-output -n cuda python \
  analysis/cosine_rerun_gap13_duplicate_exclusion/analyze_spm1d_h_comparison.py \
  --overwrite
```
