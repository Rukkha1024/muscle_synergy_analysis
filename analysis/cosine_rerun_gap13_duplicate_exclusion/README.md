# gap13 duplicate-component exclusion cosine rerun

이 폴더는 `default_run`의 cross-group cosine similarity 결과를 그대로 받아들이지 않고, **step 그룹만 gap statistic 원래 값인 K=13으로 다시 보고 싶다**는 질문에 답하기 위해 만들었다.

현재 baseline 파이프라인은 step 그룹에서 `K=13`일 때 within-trial duplicate가 남아서, zero-duplicate 조건을 만족하는 첫 K인 `16`으로 올라간 뒤 cosine similarity를 계산한다. 이 분석은 그 지점에서 한 번 멈추고, **step K=13 해를 유지한 채 duplicate가 된 component만 제외하면 cross-group 결과가 어떻게 달라지는지**를 확인하는 것이 목적이다.

## 왜 이 분석을 했는가

1. baseline figure는 [final_summary.csv](/home/alice/workspace/26-03-synergy-analysis/outputs/runs/default_run/final_summary.csv) 기준으로 `global_step: k_gap_raw=13, k_selected=16`이다.
2. 따라서 현재 figure는 “gap statistic이 제안한 구조 K”보다 “zero-duplicate를 만족하는 더 큰 K”의 결과를 반영한다.
3. 사용자가 보고 싶은 것은 `K=13` 구조를 버리지 않고, 중복된 step component만 제거했을 때도 cross-group cosine matching이 유지되는지 여부다.
4. 이번 rerun에서는 baseline audit과 같은 기준으로 `K=13`의 **min-duplicate candidate**를 다시 찾았고, 그 후보에서 실제 duplicate trial은 `유병한_v110.0_T6`, `조민석_v30.0_T2` 두 개였다.
5. fixed-`K=13` observed objective는 baseline metadata와 비교하되, GPU/환경 차이를 고려해 `--objective-atol` 허용 오차 안에서 일치 여부를 기록한다.

## 이번 분석의 핵심 규칙

1. 입력은 `outputs/runs/default_run/` 아래 baseline export만 사용한다.
2. step 그룹은 `K=13`으로 고정하고, baseline uniqueness search와 같은 방식으로 **duplicate trial 수가 가장 적은 candidate**를 선택한다.
3. duplicate trial-cluster pair가 있으면, 그 pair 안에서 **cluster centroid와 cosine similarity가 가장 높은 component 1개만 남기고 나머지 duplicate component만 제외**한다.
4. nonstep 그룹은 baseline representative W를 그대로 사용한다.
5. 정리된 step representative W와 baseline nonstep representative W로 cross-group cosine similarity, assignment, decision figure를 다시 만든다.

## 파일 구성

- `analyze_cosine_rerun_gap13_duplicate_exclusion.py`
  - baseline export를 읽고, step `K=13` 고정 rerun과 duplicate-component exclusion을 수행한다.
- `report.md`
  - 왜 이 분석을 했는지, 어떤 규칙으로 제외했는지, 결과가 baseline과 어떻게 달라졌는지 요약한다.
- `artifacts/gap13_duplicate_component_exclusion_rerun/`
  - 실행 결과 CSV, figure, checksum, summary JSON이 저장된다.

## 실행 방법

```bash
conda run --no-capture-output -n cuda python \
  analysis/cosine_rerun_gap13_duplicate_exclusion/analyze_cosine_rerun_gap13_duplicate_exclusion.py \
  --overwrite
```

dry-run으로 입력과 reconstruction consistency만 확인하려면:

```bash
conda run --no-capture-output -n cuda python \
  analysis/cosine_rerun_gap13_duplicate_exclusion/analyze_cosine_rerun_gap13_duplicate_exclusion.py \
  --dry-run
```

## 주요 산출물

- `summary.json`
- `step_k13_component_assignments.csv`
- `step_k13_duplicate_component_summary.csv`
- `step_k13_representative_W_before_exclusion.csv`
- `step_k13_representative_W_after_exclusion.csv`
- `cross_group_w_pairwise_cosine.csv`
- `cross_group_w_cluster_decision.csv`
- `figures/cross_group_cosine_heatmap.png`
- `figures/cross_group_matched_w.png`
- `figures/cross_group_decision_summary.png`
- `md5_compare_vs_default_run_figures.csv`
- `checksums.md5`

## 이번 실행에서 바로 확인할 수 있는 결과

기본 실행 산출물은 `artifacts/gap13_duplicate_component_exclusion_rerun/` 아래에 있다.

이번 rerun 기준 핵심 값은 다음과 같다.

1. step baseline은 `k_gap_raw=13`, `k_selected=16`이었다.
2. `K=13` min-duplicate candidate에서 제외된 component는 2개였다.
   - `유병한_v110.0_T6`: cluster `6`에서 component `5` 제외
   - `조민석_v30.0_T2`: cluster `0`에서 component `2` 제외
3. rerun 후 step cluster는 `13`개 그대로 유지되었다.
4. cross-group matching의 `same_synergy` 개수는 `11쌍`으로 baseline과 같았고, step group-specific cluster 수는 baseline `5개`에서 `2개`로 줄었다.
5. 새 figure 3종의 MD5는 baseline figure와 모두 달랐다. 이 값은 이미지 바이트가 달라졌다는 뜻이며, 해석은 checksum보다 `cross_group_w_cluster_decision.csv`의 cluster count 변화와 함께 봐야 한다.
