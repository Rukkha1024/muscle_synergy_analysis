# first_zero_duplicate_k_rerun

이 폴더는 **main pipeline을 바꾸지 않고**, pipeline이 이미 만든 final parquet만 읽어서 `gap statistic` 없이 대표 `K`를 다시 고르고 싶을 때 쓰는 analysis 전용 작업 공간이다.

현재 질문은 "중복 trial이 처음 0개가 되는 값은 `K=13`인데, 왜 pipeline 결과는 `15`로 보이나?"였다. 이 분석은 그 질문을 production CLI 변경 없이 재현 가능한 방식으로 답하기 위해 만들어졌다.

## 사용자 목표

1. `gap statistic`을 완전히 건너뛴다.
2. pooled clustering 입력을 final parquet에서 offline으로 다시 만든다.
3. `k_min`부터 순서대로 올리면서 **duplicate trial이 처음 0개가 되는 `K`**를 찾는다.
4. 그 값을 pipeline metadata의 `k_gap_raw`, `k_selected`, `k_min_unique`와 나란히 비교한다.

## 왜 `analysis/`에서만 하는가

- main pipeline의 source of truth와 기본 동작은 유지해야 한다.
- 이번 질문은 production behavior를 바꾸는 기능 추가가 아니라, **기존 output을 다른 규칙으로 해석해 보는 rerun**에 가깝다.
- 따라서 입력은 raw EMG가 아니라 pipeline 최종 산출물인 single parquet bundle만 사용한다.

## 기본 입력

- 기본 source parquet: `outputs/final_concatenated.parquet`
- 기본 group: `pooled_step_nonstep`

2026-03-19 기준 현재 저장소의 기본 `concatenated` bundle metadata는 다음과 같다.

- `k_gap_raw = 15`
- `k_selected = 15`
- `k_min_unique = 13`

즉, pipeline metadata만 봐도 "gap recommendation은 `15`이고, duplicate가 처음 0개가 되는 값은 `13`"이라는 차이가 이미 들어 있다. 이 analysis는 그 차이를 **직접 재탐색해서 재현**하는 역할을 한다.

## 선택 규칙

이번 analysis의 선택 규칙은 하나뿐이다.

- `first_zero_duplicate`: `k_min`부터 `K`를 증가시키며, searched candidate 중 duplicate trial이 처음 0개가 되는 `K`를 최종값으로 채택한다.

여기서 duplicate trial은 **같은 trial 안의 component 둘 이상이 같은 cluster label을 받는 경우**를 뜻한다. 이 정의는 `src/synergy_stats/clustering.py`의 production helper와 동일하다.

## 실행

작업 디렉터리: repo root

### dry-run

```bash
conda run --no-capture-output -n cuda python \
  analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
  --source-parquet outputs/final_concatenated.parquet \
  --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run \
  --dry-run
```

dry-run에서는 다음만 확인한다.

- source parquet를 읽을 수 있는가
- 필요한 frame이 모두 들어 있는가
- pooled feature row 재구성이 되는가
- no-gap rerun 설정과 예정된 `K` 범위가 무엇인가

### full run

```bash
conda run --no-capture-output -n cuda python \
  analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
  --source-parquet outputs/final_concatenated.parquet \
  --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run \
  --overwrite
```

기본 질문을 그대로 확인하고 싶다면 위 명령을 그대로 쓰면 된다.

### 다른 bundle로 바꾸기

예를 들어 `trialwise` bundle에서 같은 질문을 보고 싶다면:

```bash
conda run --no-capture-output -n cuda python \
  analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
  --source-parquet outputs/final_trialwise.parquet \
  --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/trialwise_run \
  --overwrite
```

## 산출물

이제 이 analysis는 scan 결과만 남기지 않고, **선택된 no-gap `K`를 기준으로 pipeline과 같은 소비 형태의 결과물**도 같이 저장한다.

- `summary.json`: 이번 rerun의 핵심 요약
- `k_scan.json`: `K`별 duplicate burden과 zero-duplicate 여부
- `checksums.md5`: 생성 파일 checksum
- `k_duplicate_burden.png`: analysis rerun과 pipeline metadata를 나란히 보여주는 figure
- `analysis_methods_manifest.json`: analysis 작업폴더 기준 상대경로 manifest
- `final.parquet`: no-gap rerun 결과를 single parquet bundle로 다시 저장한 파일
- `final_concatenated.parquet`: mode alias parquet
- `concatenated/clustering_audit.xlsx`: pipeline과 같은 형식의 clustering audit workbook
- `concatenated/results_interpretation.xlsx`: pipeline과 같은 형식의 interpretation workbook
- `concatenated/figures/*.png`: pooled cluster figure와 mode figure

기본 `default_run` 기준 출력 트리는 아래와 같다.

```text
analysis/first_zero_duplicate_k_rerun/artifacts/default_run/
  analysis_methods_manifest.json
  checksums.md5
  final.parquet
  final_concatenated.parquet
  k_duplicate_burden.png
  k_scan.json
  summary.json
  concatenated/
    clustering_audit.xlsx
    results_interpretation.xlsx
    figures/
      01_trial_composition.png
      03_cluster_strategy_composition.png
      04_pooled_cluster_representatives.png
      05_within_cluster_strategy_overlay.png
      pooled_step_nonstep_clusters.png
      nmf_trials/*.png
```

## 현재 확인된 결과

2026-03-19 기준 `outputs/final_concatenated.parquet`에 대해 실제 rerun을 돌린 결과는 다음과 같다.

- pooled vector 수: `221`
- analysis unit 수: `45`
- `k_min = 7`
- no-gap rerun의 최종값: `k_selected_first_zero_duplicate = 13`
- pipeline metadata: `k_gap_raw = 15`, `k_selected = 15`, `k_min_unique = 13`

즉, 현재 저장소 상태에서는 **gap statistic을 빼면 `K=13`이 맞고**, pipeline이 `15`를 보고한 이유는 duplicate-free floor가 아니라 gap recommendation을 먼저 반영했기 때문이다.

이 analysis는 그 결론을 말로만 남기지 않고, **`K=13`으로 다시 계산된 parquet/workbook/figure 묶음**을 `analysis/` 작업폴더 안에 저장한다.

## 해석 방법

- `pipeline_k_gap_raw`: pipeline이 gap statistic으로 먼저 고른 값
- `pipeline_k_selected`: pipeline이 최종 채택한 값
- `pipeline_k_min_unique`: pipeline metadata상 duplicate가 처음 0개가 되는 값
- `k_selected_first_zero_duplicate`: 이번 analysis가 gap 없이 다시 찾은 값

현재 사용자 질문의 핵심은 `pipeline_k_gap_raw` 또는 `pipeline_k_selected`가 `15`여도, **no-gap rule에서는 `13`이 먼저 zero-duplicate가 될 수 있다**는 점이다.

## 주의

- 이 폴더는 production pipeline을 대체하지 않는다.
- `main.py`나 main pipeline config를 변경하지 않는다.
- 입력은 final parquet bundle 하나뿐이며, raw EMG나 intermediate CSV를 다시 만들지 않는다.
- `summary.json`, `k_scan.json`, `final.parquet`, `final_concatenated.parquet`, `analysis_methods_manifest.json`, 그리고 PNG figure는 현재 byte-level 재현성을 확인했다.
- `.xlsx` workbook은 내용과 sheet 구조는 같지만, `openpyxl`의 생성 시각 metadata 때문에 run 간 MD5가 달라질 수 있다.
