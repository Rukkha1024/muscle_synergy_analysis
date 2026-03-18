# vaf_threshold_sensitivity

이 폴더는 **VAF 기준값 변화에 따른 NMF 시너지 수와 pooled k-means의 K 변화**를 `analysis/` 문맥에서 재현하기 위한 작업 공간이다.

## 목표

- VAF 기준값 `80%`, `85%`, `90%`, `95%`에서 시너지 수가 어떻게 달라지는지 확인한다.
- 결과는 `trialwise`와 `concatenated` 두 mode 모두에 대해 비교한다.
- NMF와 clustering은 **main pipeline 로직을 그대로 재사용**한다.

## 입력 데이터

- 설정: `configs/global_config.yaml`
- NMF / clustering 설정 source of truth: `configs/synergy_stats_config.yaml`
- EMG 입력: `input.emg_parquet_path`
- 이벤트 메타데이터: `input.event_xlsm_path`

## 핵심 구현 원칙

1. trial selection은 `load_event_metadata()` + `merge_event_metadata()` + `build_trial_records()` 경로를 그대로 따른다.
2. `trialwise` NMF는 trial별 `extract_trial_features()`를 사용한다.
3. `concatenated` NMF는 `build_concatenated_feature_rows()`를 사용한다.
4. clustering은 mode별 단일 `pooled_step_nonstep` 공간에서 `cluster_feature_group()`를 호출한다.
5. `K` 선택 규칙은 main pipeline과 동일하게 `gap statistic + zero-duplicate feasibility`를 따른다.

## 실행

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --dry-run
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py
```

## 산출물

- `report.md`: 사용자용 요약 리포트
- `artifacts/default_run/summary.json`: 재현용 구조화 결과
- `artifacts/default_run/by_threshold/vaf_XX/summary.json`: VAF parameter별 구조화 결과
- `artifacts/default_run/checksums.md5`: 생성 산출물 checksum
