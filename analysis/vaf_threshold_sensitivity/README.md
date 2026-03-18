# vaf_threshold_sensitivity

이 폴더는 **VAF 기준값 변화에 따른 NMF 시너지 수와 pooled k-means의 K 변화**를 `analysis/` 문맥에서 재현하고, 특히 `90%` cutoff를 방어할 수 있는지 점검하기 위한 작업 공간이다.

## 목표

- VAF 기준값 `85%`부터 `95%`까지 `1%` 단위로 바꿨을 때 시너지 수와 pooled `K`가 어떻게 달라지는지 확인한다.
- 결과는 `trialwise`와 `concatenated` 두 mode 모두에 대해 비교한다.
- trial selection과 clustering은 **main pipeline 로직을 그대로 재사용**하고, NMF는 같은 low-level rank fitting / VAF 계산 규칙을 캐시 기반으로 재사용한다.
- broad sweep에서는 계산 시간을 줄이기 위해 clustering restart 수만 선택적으로 낮춰 screening하고, 필요한 구간은 별도 out-dir로 정밀 rerun할 수 있다.

## 입력 데이터

- 설정: `configs/global_config.yaml`
- NMF / clustering 설정 source of truth: `configs/synergy_stats_config.yaml`
- EMG 입력: `input.emg_parquet_path`
- 이벤트 메타데이터: `input.event_xlsm_path`

## 핵심 구현 원칙

1. trial selection은 `load_event_metadata()` + `merge_event_metadata()` + `build_trial_records()` 경로를 그대로 따른다.
2. `trialwise` NMF는 각 trial에 대해 가능한 rank를 한 번씩 fit한 뒤, threshold별로 최소 만족 rank를 다시 선택한다.
3. `concatenated`는 `(subject, velocity, step_class)` super-trial을 fit한 뒤 source trial averaged activation profile을 다시 나눠 threshold별 feature row를 만든다.
4. clustering은 mode별 단일 `pooled_step_nonstep` 공간에서 `cluster_feature_group()`를 호출한다.
5. `K` 선택 규칙은 main pipeline과 동일하게 `gap statistic + zero-duplicate feasibility`를 따른다.

## 실행

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --dry-run
```

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
  --cluster-repeats 100 \
  --gap-ref-n 100 \
  --gap-ref-restarts 20 \
  --uniqueness-candidate-restarts 100
```

위 command가 현재 `report.md`의 broad sweep 숫자를 재현하는 screening profile이다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py
```

위 command는 같은 분석을 default clustering profile로 수행하는 exact-profile rerun이다. restart 수가 더 크므로 screening profile과 숫자가 완전히 같지 않을 수 있다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
  --thresholds 0.89 0.90 0.91 \
  --out-dir analysis/vaf_threshold_sensitivity/artifacts/exact_89_91
```

## 산출물

- `report.md`: 사용자용 요약 리포트
- `artifacts/default_run/summary.json`: broad sweep 구조화 결과
- `artifacts/default_run/by_threshold/vaf_XX/summary.json`: threshold별 구조화 결과
- `artifacts/default_run/checksums.md5`: broad sweep 산출물 checksum
- `artifacts/exact_89_91/`: `89%`, `90%`, `91%` 주변 정밀 rerun을 따로 저장할 때 사용하는 out-dir 예시

각 `summary.json`에는 `run_metadata`가 포함되어 있어, clustering restart override를 사용했는지 함께 추적할 수 있다.
