# first_zero_duplicate_k_rerun

이 폴더는 main pipeline이 이미 만든 final parquet만 읽어서 `gap statistic` 없이 대표 `K`를 다시 고르거나, paired-only bundle 기준으로 cluster presence 통계를 다시 계산하고 싶을 때 쓰는 analysis 전용 작업 공간이다.

현재 질문은 "중복 trial이 처음 0개가 되는 값은 `K=13`인데, 왜 pipeline 결과는 더 큰 값을 보이나?"였고, 이후 main pipeline의 filtering source of truth도 `(subject, velocity)` paired gate를 포함하도록 바뀌었다. 이 analysis는 그 paired-only final parquet를 production CLI 밖에서 다시 읽어, no-gap rerun과 paired exact McNemar 통계를 reviewer-friendly artifact로 정리하기 위해 만들어졌다.

## 공식 결과 문서

- paired 결과 해석 report: `analysis/first_zero_duplicate_k_rerun/report.md`
- paired 통계 workbook: `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_statistics.xlsx`
- paired summary: `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/summary.json`

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

2026-03-22 기준 현재 저장소의 기본 paired-only `concatenated` bundle metadata는 다음과 같다.

- `k_gap_raw = 16`
- `k_selected = 16`
- `k_min_unique = 13`

즉, pipeline metadata만 봐도 "gap recommendation은 `16`이고, duplicate가 처음 0개가 되는 값은 `13`"이라는 차이가 이미 들어 있다. 이 analysis는 그 차이를 **직접 재탐색해서 재현**하는 역할을 한다.

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

### paired refilter run

`subject+velocity` 기준 paired filter가 이미 반영된 final parquet를 다시 읽어서, paired subset만으로 `first_zero_duplicate` reclustering과 paired exact McNemar 통계를 만들고 싶다면 아래 명령을 사용한다.

```bash
conda run --no-capture-output -n cuda python \
  analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py \
  --source-parquet outputs/final_concatenated.parquet \
  --config configs/global_config.yaml \
  --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering \
  --overwrite
```

이 workflow는 raw event/meta를 다시 읽지 않는다. 입력은 paired filter가 끝난 single parquet bundle 하나뿐이다.
현재 `main.py --out ...`는 workbook/figure는 지정한 run directory 아래에 쓰지만, canonical single parquet alias는 여전히 루트 `outputs/final_concatenated.parquet`에 기록하므로 위 경로를 사용한다.

### paired refilter workflow

`subject + velocity` 기준으로 **step / nonstep이 둘 다 있는 key만 남긴 뒤**, 그 subset에서 다시 `first_zero_duplicate` reclustering과 paired statistics를 보고 싶다면 아래 순서로 실행하면 된다.

1. main pipeline을 isolated output으로 한 번 다시 돌려 paired-only final parquet를 만든다.
2. 그 parquet를 입력으로 새 paired analysis script를 실행한다.

```bash
conda run --no-capture-output -n cuda python \
  main.py \
  --config configs/global_config.yaml \
  --out outputs/paired_refilter_pipeline \
  --overwrite

conda run --no-capture-output -n cuda python \
  analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py \
  --source-parquet outputs/final_concatenated.parquet \
  --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering \
  --overwrite
```

이 workflow는 raw event/meta를 analysis 폴더에서 다시 읽지 않는다. source of truth는 main pipeline이 만든 paired-only `final_concatenated.parquet`이고, analysis는 그 parquet만 읽어 다음 산출물을 만든다.

- `paired_subset_manifest.csv`: paired key로 실제 rerun에 포함된 analysis unit 목록
- `excluded_nonpaired_manifest.csv`: pair를 이루지 못해 빠진 key 목록
- `paired_cluster_stats.csv`: cluster별 paired exact McNemar 요약
- `paired_cluster_detail.csv`: cluster x paired key detail evidence
- `paired_cluster_statistics.xlsx`: reviewer가 바로 읽을 수 있는 paired workbook
- `report.md`: 현재 paired 결과를 해석한 analysis 문서

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

paired refilter run은 위 산출물에 더해 아래 파일을 같이 남긴다.

- `paired_subset_manifest.csv`: paired key와 surviving step/nonstep analysis unit 대응표
- `excluded_nonpaired_manifest.csv`: source bundle 안에서 paired 조건을 만족하지 못한 key 목록
- `paired_cluster_stats.csv`: cluster별 paired presence 요약과 exact McNemar 결과
- `paired_cluster_detail.csv`: `cluster x paired key` 상세 evidence
- `paired_cluster_statistics.xlsx`: reviewer-facing paired summary workbook
- `report.md`: paired 결과 해석과 workbook 읽는 법을 정리한 문서

## 현재 확인된 결과

2026-03-22 기준 paired refilter rerun의 현재 확인 결과는 다음과 같다.

- source parquet: `outputs/final_concatenated.parquet`
- paired key 수: `21`
- source bundle 안 excluded pair key 수: `0`
- analysis unit 수: `42`
- pooled vector 수: `212`
- `k_min = 8`
- no-gap rerun의 최종값: `k_selected_first_zero_duplicate = 13`
- pipeline metadata: `k_gap_raw = 16`, `k_selected = 16`, `k_min_unique = 13`
- paired workbook: `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_statistics.xlsx`

즉, 현재 paired-only bundle에서도 **gap statistic을 빼면 `K=13`이 first zero-duplicate floor로 남고**, pipeline은 gap recommendation 때문에 `16`을 선택한다. cluster presence exact McNemar 결과는 `paired_cluster_statistics.xlsx`와 `report.md`에서 함께 읽을 수 있다.

## 해석 방법

- `pipeline_k_gap_raw`: pipeline이 gap statistic으로 먼저 고른 값
- `pipeline_k_selected`: pipeline이 최종 채택한 값
- `pipeline_k_min_unique`: pipeline metadata상 duplicate가 처음 0개가 되는 값
- `k_selected_first_zero_duplicate`: 이번 analysis가 gap 없이 다시 찾은 값
- `paired_key_n`: paired refilter workflow에서 실제로 남은 `subject+velocity` key 수
- `excluded_pair_key_n`: source bundle에 있었지만 paired subset에서 제외된 key 수

현재 paired workflow의 핵심은 `pipeline_k_gap_raw` 또는 `pipeline_k_selected`가 `16`이어도, **no-gap rule에서는 `13`이 먼저 zero-duplicate가 될 수 있다**는 점과, 그 paired cluster presence 차이가 보정 후에도 유지되는지는 workbook/report에서 따로 확인해야 한다는 점이다.

## 주의

- 이 폴더는 production pipeline을 대체하지 않는다.
- `main.py`나 main pipeline config를 변경하지 않는다.
- 입력은 final parquet bundle 하나뿐이며, raw EMG나 intermediate CSV를 다시 만들지 않는다.
- `summary.json`, `k_scan.json`, `final.parquet`, `final_concatenated.parquet`, `analysis_methods_manifest.json`, 그리고 PNG figure는 현재 byte-level 재현성을 확인했다.
- `.xlsx` workbook은 내용과 sheet 구조는 같지만, `openpyxl`의 생성 시각 metadata 때문에 run 간 MD5가 달라질 수 있다.
