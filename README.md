# EMG Synergy Pipeline

이 저장소는 EMG parquet와 이벤트 xlsm을 받아 `subject-velocity-trial` 단위로 trial을 자르고, 각 trial에서 근육 시너지를 추출한 뒤 피험자 내 representative cluster를 내보내는 파이프라인이다. 현재 기본 분석 구간은 `platform_onset ~ step_onset`이며, step trial은 실제 `step_onset`을 사용하고 nonstep trial은 같은 피험자에서 선택된 comparison velocity의 step trial 평균 `step_onset`을 surrogate 종료점으로 사용한다.

파이프라인은 논문식 비교 구조를 따르기 위해 `mixed velocity` 비교 세트만 기본 선택한다. 즉 event workbook에서 `mixed == 1`로 표시되고, 같은 `subject-velocity` 안에 총 4 trial이 있으며 그 안에서 step 2회와 nonstep 2회가 공존하고, 선택된 step trial에 실제 `step_onset`이 존재하는 경우만 본 분석에 포함한다. 또한 한 피험자에는 하나의 comparison velocity만 남아야 하며, 둘 이상이 동시에 성립하면 오류로 처리한다.

## 빠른 시작

이 저장소의 공식 실행 환경은 conda env `cuda`다. Python과 pip는 아래 형식으로 실행한다.

```bash
conda run -n cuda python ...
conda run -n cuda pip ...
```

fixture 입력으로 전체 파이프라인을 검증하려면 저장소 루트에서 아래 명령을 실행한다.

```bash
conda run -n cuda python main.py \
  --config tests/fixtures/global_config.yaml \
  --out outputs/runs/fixture_run \
  --overwrite
```

실운영 입력 경로가 실제로 읽히는지만 먼저 확인하려면 dry-run을 사용한다.

```bash
conda run -n cuda python main.py \
  --config configs/global_config.yaml \
  --dry-run
```

## 분석 창과 비교 규칙

현재 기본 설정은 [configs/emg_pipeline_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/emg_pipeline_config.yaml)에 있다. 핵심 규칙은 아래와 같다.

- 시작 이벤트는 `platform_onset`이다.
- 종료 이벤트는 파생 컬럼 `analysis_window_end`다.
- step trial은 실제 `step_onset`을 `analysis_window_end`로 사용한다.
- nonstep trial은 같은 `subject`에서 선택된 comparison velocity의 step trial 평균 `step_onset`을 `analysis_window_end`로 사용한다.
- 기본 selection rule은 `mixed == 1`, 총 4 trial, step 2회, nonstep 2회, step trial의 `step_onset` complete, subject당 comparison velocity 1개 조건이다.

이 규칙 덕분에 step과 nonstep을 같은 시간 구조에서 비교할 수 있고, perturbation 강도 차이를 덜어낸 상태에서 시너지 패턴을 비교할 수 있다. 이전 `platform_onset ~ platform_offset` 구간을 다시 쓰고 싶다면 `windowing.offset_column`을 `platform_offset`으로 바꾸고 mixed selection을 끄면 된다.

## 입력 파일

기본 실행은 아래 두 입력을 사용한다.

- EMG parquet: `input.emg_parquet_path`
- 이벤트 xlsm: `input.event_xlsm_path`

기본 경로는 [configs/global_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/global_config.yaml)에 정의되어 있다. fixture 실행은 [tests/fixtures/global_config.yaml](/home/alice/workspace/26-03-synergy-analysis/tests/fixtures/global_config.yaml)을 사용한다.

EMG parquet의 최소 필수 컬럼은 아래와 같다.

- `subject`
- `velocity`
- `trial_num`
- `original_DeviceFrame`
- 근육 채널 컬럼들 (`muscles.names`)

이벤트 xlsm은 아래 컬럼을 준비해야 한다.

- `subject`
- `velocity`
- `trial` 또는 `trial_num`
- `platform_onset`
- `platform_offset`
- `step_onset`
- `step_TF`
- `state`
- `mixed`

`step_onset`은 전체 행에 다 채워질 필요는 없지만, 기본 mixed 비교 세트에 선택된 step trial에는 반드시 존재해야 한다. 그렇지 않으면 그 비교 세트는 분석 대상에서 제외된다.

## 설정 파일

파이프라인 설정은 `configs/` 아래 YAML로 분리되어 있다.

- [configs/global_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/global_config.yaml)
  전역 입력 경로와 런타임 옵션을 관리한다.
- [configs/emg_pipeline_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/emg_pipeline_config.yaml)
  trial window, mixed selection, surrogate `step_onset`, stance metadata 규칙을 관리한다.
- [configs/synergy_stats_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/synergy_stats_config.yaml)
  근육 목록, NMF, clustering, representative `H` 100-window 보간, figure export 설정을 관리한다.

루트 오케스트레이터 [main.py](/home/alice/workspace/26-03-synergy-analysis/main.py)는 전역 설정을 먼저 읽고 도메인 설정을 병합한 뒤 `scripts/emg/NN_*.py` 순서대로 실행한다.

## 파이프라인 단계

실제 실행 순서는 [main.py](/home/alice/workspace/26-03-synergy-analysis/main.py)에 명시되어 있다.

1. [scripts/emg/01_load_emg_table.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/01_load_emg_table.py)
   EMG parquet와 event workbook을 읽고, mixed comparison filter와 surrogate `step_onset`을 적용한 event metadata를 준비한다.
2. [scripts/emg/02_extract_trials.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/02_extract_trials.py)
   선택된 trial만 `platform_onset ~ analysis_window_end` 구간으로 자르고 `DeviceFrame`을 onset 기준으로 다시 맞춘다.
3. [scripts/emg/03_extract_synergy_nmf.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/03_extract_synergy_nmf.py)
   trial별 NMF를 수행하고, trial window provenance를 feature metadata에 붙인다.
4. [scripts/emg/04_cluster_synergies.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/04_cluster_synergies.py)
   피험자 내 representative cluster를 찾는다.
5. [scripts/emg/05_export_artifacts.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/05_export_artifacts.py)
   CSV, parquet, trial window metadata, subject figure, overview figure를 저장한다.

## 현재 시너지 규칙

현재 저장소가 유지하는 시너지 추출 규칙은 아래와 같다.

- NMF rank는 `1 ~ max_components_to_try` 범위에서 순차 탐색한다.
- `VAF >= 0.90`를 처음 만족하는 rank를 채택한다.
- `W`는 column norm 기준으로 정규화한다.
- representative `H`는 export 단계에서만 100-window로 보간한다.
- clustering은 피험자 내에서만 수행하며, cross-subject global cluster 정렬은 하지 않는다.

즉 overview figure는 “전 피험자 공통 cluster 평균”이 아니라 “subject-local cluster를 한 파일에 모아 본 overview”다.

## 출력 파일

기본 런 디렉터리는 `runtime.output_dir` 아래에 생성된다. fixture 실행 기준 주요 산출물은 아래와 같다.

- `final_summary.csv`
- `all_representative_W_posthoc.csv`
- `all_representative_H_posthoc_long.csv`
- `all_trial_window_metadata.csv`
- `figures/subject_<subject_id>_clusters.png`
- `figures/overview_all_subject_clusters.png`
- `subject_<subject_id>/trial_window_metadata.csv`
- `outputs/final.parquet`

`all_trial_window_metadata.csv`는 이번 변경에서 가장 먼저 확인해야 하는 파일이다. 이 파일에는 각 trial이 어떤 window를 사용했는지, surrogate를 썼는지, mixed selection을 어떻게 통과했는지, step/nonstep class가 무엇인지가 기록된다. `analysis_window_source`는 기본적으로 `actual_step_onset`, `subject_mean_step_onset`, `platform_offset` 중 하나를 가진다.

## 출력 해석

`trial_window_metadata.csv`와 `all_trial_window_metadata.csv`에서 아래 컬럼을 보면 window 해석이 가능하다.

- `analysis_window_onset_column`
- `analysis_window_offset_column`
- `analysis_window_start`
- `analysis_window_end`
- `analysis_window_source`
- `analysis_window_is_surrogate`
- `analysis_step_class`
- `analysis_mixed_group_step_trials`
- `analysis_mixed_group_nonstep_trials`
- `analysis_selection_rule`

subject figure는 cluster마다 왼쪽에 `W` bar plot, 오른쪽에 `H(100-window)` line plot을 배치한다. overview figure는 이 subject figure들을 한 화면에 모아 놓은 montage다. 여기서 cluster 번호는 subject-local label이므로, 다른 피험자의 같은 번호 cluster와 직접 평균 비교하면 안 된다.

## 실행 예시

실운영 경로로 실제 계산을 수행할 때는 아래 형식을 사용한다.

```bash
conda run -n cuda python main.py \
  --config configs/global_config.yaml \
  --out outputs/runs/platform_to_step_onset \
  --overwrite
```

입력 경로만 임시로 바꾸고 싶다면 CLI override를 사용한다.

```bash
conda run -n cuda python main.py \
  --config configs/global_config.yaml \
  --parquet /path/to/processed_emg_data.parquet \
  --meta-xlsm /path/to/perturb_inform.xlsm \
  --out outputs/runs/custom_run \
  --overwrite
```

## 검증

pytest 전체 실행:

```bash
conda run -n cuda python -m pytest tests -q
```

fixture reference baseline 생성과 curated MD5 비교:

```bash
conda run -n cuda python main.py \
  --config tests/fixtures/global_config.yaml \
  --out tests/reference_outputs/reference_baseline \
  --overwrite

conda run -n cuda python main.py \
  --config tests/fixtures/global_config.yaml \
  --out outputs/runs/fixture_run \
  --overwrite

conda run -n cuda python scripts/emg/99_md5_compare_outputs.py \
  --base tests/reference_outputs/reference_baseline \
  --new outputs/runs/fixture_run
```

실제 확인된 검증 결과는 아래와 같다.

- `conda run -n cuda python -m pytest tests -q` 통과
- `conda run -n cuda python main.py --config configs/global_config.yaml --dry-run` 통과
- fixture reference baseline 대비 curated MD5 비교 통과

## 현재 범위와 제한

- 기본 mixed selection은 `mixed == 1`이면서 총 4 trial, step 2회, nonstep 2회, step trial의 실제 `step_onset` complete, subject당 comparison velocity 1개 조건을 요구한다.
- cross-subject global cluster alignment는 아직 구현하지 않았다.
- figure는 PNG export를 기본으로 사용한다.
- Qt 관련 `wayland` plugin 경고가 출력될 수 있지만, 현재 fixture 실행에서는 산출물 생성에 영향을 주지 않았다.
