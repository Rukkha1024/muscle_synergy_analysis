# EMG Synergy Pipeline

이 저장소는 platform translation perturbation 과제에서 수집된 EMG parquet와 이벤트 xlsm을 입력으로 받아, `subject-velocity-trial` 단위 trial을 정의하고 step과 non-step 비교를 위한 근육 시너지를 추출하는 파이프라인이다. 문서의 설명 순서는 실행 가이드보다 분석 설계와 처리 절차를 먼저 제시하는 방법론 형식을 따른다.

기본 분석 구간은 `platform_onset ~ analysis_window_end`이며, step trial은 실제 `step_onset`을 종료점으로 사용한다. 반면 nonstep trial은 실제 step event가 존재하지 않으므로, 같은 피험자에서 선택된 comparison velocity의 step trial 평균 step latency(`step_onset - platform_onset`)를 적용하여 `analysis_window_end = platform_onset + mean(step_onset - platform_onset)` 형태의 surrogate 종료점을 사용한다. 최종 산출물은 trial window provenance와 함께, `mixed comparison` 필터를 통과한 전체 step 집단과 전체 nonstep 집단에 대해 계산한 representative synergy 및 figure를 포함한다.

## 1. 분석 목적과 비교 단위

본 파이프라인의 목적은 동일 피험자 내부에서 step 전략과 non-step 전략을 비교 가능한 시간 구조로 정렬한 뒤, 각 trial에서 추출된 근육 시너지를 전체 step 집단과 전체 nonstep 집단의 representative cluster로 요약하는 데 있다. 이를 위해 분석의 기본 단위는 `subject-velocity-trial`로 두고, 비교 세트는 논문식 paired comparison 구조를 반영하도록 `mixed velocity` 조건으로 제한한다.

기본 선택 규칙은 event workbook에서 `mixed == 1`로 표시된 세트만 포함하는 것이다. 또한 같은 `subject-velocity` 안에 총 4 trial이 존재하고, 그 안에서 step 2회와 nonstep 2회가 공존해야 하며, 선택된 step trial에는 실제 `step_onset`이 존재해야 한다. 한 피험자에 둘 이상의 comparison velocity가 동시에 남는 경우는 허용하지 않으며 오류로 처리한다.

## 2. 입력 자료와 필수 메타데이터

기본 실행은 아래 두 입력 파일을 사용한다.

- EMG parquet: `input.emg_parquet_path`
- 이벤트 xlsm: `input.event_xlsm_path`

기본 경로는 [configs/global_config.yaml](configs/global_config.yaml)에 정의되어 있으며, 전역 출력 위치와 재현성 관련 seed 역시 같은 파일에서 관리한다.

현재 기본 EMG parquet 경로는 `min-max_norm_only.parquet`이며, min-max 정규화가 완료된 데이터다. 또한 trial별 길이를 고정하기 위한 resampling이 이미 적용되어 있어 `resampled_frame` 컬럼을 포함한다. 기본 입력 기준으로 각 trial은 동일한 resampled 길이를 가지며, 현재 파이프라인은 이 resampled parquet를 입력으로 사용한다.

EMG parquet는 최소한 아래 컬럼을 포함해야 한다.

- `subject`
- `velocity`
- `trial_num`
- `original_DeviceFrame`
- 근육 채널 컬럼들 (`muscles.names`)

이벤트 xlsm은 아래 컬럼을 포함해야 한다.

- `subject`
- `velocity`
- `trial` 또는 `trial_num`
- `platform_onset`
- `platform_offset`
- `step_onset`
- `step_TF`
- `state`
- `mixed`

현재 근육 채널 목록은 [configs/synergy_stats_config.yaml](configs/synergy_stats_config.yaml)에 정의되어 있으며 다음 16개 근육을 사용한다.

- `TA`
- `EHL`
- `MG`
- `SOL`
- `PL`
- `RF`
- `VL`
- `ST`
- `RA`
- `EO`
- `IO`
- `SCM`
- `GM`
- `ESC`
- `EST`
- `ESL`

## 3. Trial 선택 기준

분석 대상 trial은 [configs/emg_pipeline_config.yaml](configs/emg_pipeline_config.yaml)의 selection rule에 따라 선별된다. 기본 규칙은 다음과 같다.

- `mixed_only: true`
- `mixed_column: "mixed"`
- `require_total_trials: 4`
- `require_step_trials: 2`
- `require_nonstep_trials: 2`
- `single_velocity_per_subject: true`

이 규칙은 step과 non-step이 동일 피험자, 동일 comparison velocity, 동일 trial count 구조 안에서 비교되도록 강제한다. 따라서 본 저장소의 기본 산출물은 모든 원시 trial의 전수 요약이 아니라, paired interpretation이 가능한 curated mixed comparison set의 결과로 이해해야 한다.

## 4. 분석 구간 정의

분석 창 정의는 [configs/emg_pipeline_config.yaml](configs/emg_pipeline_config.yaml)의 `windowing` 설정을 따른다. 시작 이벤트는 항상 `platform_onset`이며, 종료 이벤트는 파생 컬럼 `analysis_window_end`로 통일한다.

step trial의 경우 실제 `step_onset`이 `analysis_window_end`로 직접 사용된다. 반면 nonstep trial은 실제 step event가 존재하지 않으므로, 같은 피험자에서 선택된 comparison velocity의 step trial 평균 step latency(`step_onset - platform_onset`)를 적용하여 `analysis_window_end = platform_onset + mean(step_onset - platform_onset)` 형태로 surrogate 종료점을 정의한다. 이 규칙은 step과 non-step을 동일한 시간 기준에서 비교하기 위한 것으로, 결과 메타데이터에는 실제 종료점인지 surrogate 종료점인지가 함께 기록된다.

이전과 같이 `platform_onset ~ platform_offset` 구간을 사용하려면 `windowing.offset_column`을 `platform_offset`으로 바꾸고 mixed selection을 비활성화하면 된다. 다만 현재 README가 설명하는 기본 방법론은 `platform_onset ~ step_onset` 비교 구조를 전제로 한다.

## 5. 처리 절차

파이프라인 실행 순서는 [main.py](main.py)에 명시되어 있으며, 아래 다섯 단계로 고정된다.

1. [scripts/emg/01_load_emg_table.py](scripts/emg/01_load_emg_table.py)
   EMG parquet와 event workbook을 읽고, mixed comparison filter와 surrogate `step_onset` 규칙을 적용한 event metadata를 준비한다.
2. [scripts/emg/02_extract_trials.py](scripts/emg/02_extract_trials.py)
   선택된 trial만 `platform_onset ~ analysis_window_end` 구간으로 절단하고 `DeviceFrame`을 onset 기준으로 다시 정렬한다.
3. [scripts/emg/03_extract_synergy_nmf.py](scripts/emg/03_extract_synergy_nmf.py)
   trial별 NMF를 수행하고 trial window provenance를 feature metadata에 결합한다.
4. [scripts/emg/04_cluster_synergies.py](scripts/emg/04_cluster_synergies.py)
   `analysis_selected_group == True`인 trial만 모아 `global_step`과 `global_nonstep` 두 집단으로 clustering한다.
5. [scripts/emg/05_export_artifacts.py](scripts/emg/05_export_artifacts.py)
   CSV, parquet, trial window metadata, group figure를 저장한다.

이 순서는 `자료 로딩 → trial 절단 → 시너지 추출 → global step/nonstep 군집화 → 산출물 저장`의 분석 절차와 대응한다.

## 6. 시너지 추출 규칙

시너지 추출 설정은 [configs/synergy_stats_config.yaml](configs/synergy_stats_config.yaml)에서 관리한다. 현재 저장소가 유지하는 핵심 규칙은 아래와 같다.

- 분해 기법은 NMF를 사용한다.
- rank는 `1 ~ max_components_to_try` 범위에서 순차 탐색한다.
- `VAF >= 0.90`를 처음 만족하는 rank를 채택한다.
- `W`는 column norm 기준으로 정규화한다.
- `representative H`는 export 단계에서만 100-window로 보간한다.

현재 기본 파라미터는 `max_components_to_try: 8`, `vaf_threshold: 0.90`, `random_state: 42`, `target_windows: 100`이다. 따라서 대표 activation profile은 원시 시계열 길이 그대로 저장되는 것이 아니라, figure 및 summary export 시점에 100-window 길이로 정렬된 값으로 해석해야 한다.

## 7. Global step / nonstep 군집화와 대표 시너지

군집화는 [configs/synergy_stats_config.yaml](configs/synergy_stats_config.yaml)의 `synergy_clustering` 설정을 따른다. 현재 grouping은 `global_step`과 `global_nonstep` 두 집단으로 고정되며, YAML에서 `synergy_clustering.grouping` 같은 legacy 키는 지원하지 않는다. 기본 selection method는 `gap_statistic`이고, 알고리즘은 `cuml_kmeans`다. duplicate 정책은 `require_zero_duplicate_solution: true`, `duplicate_resolution: "none"`으로 관리한다. 즉 같은 trial에서 나온 복수 synergy가 동일 cluster에 중복 배정되는 해를 post-hoc으로 고치지 않고, zero-duplicate observed solution이 실제로 존재하는 K만 채택한다.

군집화 단계에서 사용하는 k range는 아래 규칙으로 정의한다.

- `k range = [k_lb, k_max]`
- `k_lb`는 선택된 trial들에서 subject별 NMF component 수(`H` 구조 수)의 최대값 중 최댓값(`subject NMF Hmax`) 이상이어야 한다. (`k_lb >= subject NMF Hmax`)
- `k_max`는 `synergy_clustering.max_clusters`와 전체 component 샘플 수를 고려하여 제한한다.

후보 `K`마다 pooled synergy vector에 plain k-means를 적용하고, gap statistic의 1-SE 규칙으로 구조 기준 `k_gap_raw`를 먼저 고른다. 그 다음 `k_gap_raw` 이상에서 같은 trial 내부 duplicate가 0인 observed solution이 처음 나타나는 `k_selected`를 최종 cluster 수로 채택한다. 따라서 메인 파이프라인은 더 이상 trial 내부 라벨 재할당으로 success를 만들지 않는다.

중요한 점은 step과 nonstep을 서로 섞지 않는다는 것이다. `global_step`은 선택된 모든 step trial의 synergy component만 모아 clustering하고, `global_nonstep`은 선택된 모든 nonstep trial의 synergy component만 따로 clustering한다. 따라서 같은 `cluster_id`라도 step과 nonstep 사이를 직접 대응시키면 안 된다.

또한 global clustering이라고 해서 trial identity가 사라지는 것은 아니다. 각 component에는 `subject`, `velocity`, `trial_num`, `group_id`가 함께 저장되며, duplicate feasibility도 여전히 같은 `(subject, velocity, trial_num)` 안에서만 검사한다. 즉 서로 다른 피험자 component를 한데 모아도, 최종 채택된 해에서는 한 trial에서 나온 여러 synergy가 같은 cluster에 겹쳐 들어가지 않는다. 대신 이 조건은 metadata에 `k_lb`, `k_gap_raw`, `k_selected`, `k_min_unique`, `duplicate_trial_count_by_k_json`으로 함께 기록되어, 구조 기준 K와 feasibility 때문에 올린 K를 구분해 해석할 수 있다.

## 8. 산출물과 해석 기준

기본 런 디렉터리는 `runtime.output_dir` 아래에 생성된다. 주요 산출물은 아래와 같다.

- `final_summary.csv`
- `all_cluster_labels.csv`
- `all_cluster_members.csv`
- `all_representative_W_posthoc.csv`
- `all_representative_H_posthoc_long.csv`
- `all_trial_window_metadata.csv`
- `all_clustering_metadata.csv`
- `global_step/clustering_metadata.csv`
- `global_nonstep/clustering_metadata.csv`
- `global_step/cluster_labels.csv`
- `global_nonstep/cluster_labels.csv`
- `figures/global_step_clusters.png`
- `figures/global_nonstep_clusters.png`
- `outputs/final.parquet`

가장 먼저 확인할 파일은 `all_trial_window_metadata.csv`다. 이 파일에는 각 trial이 어떤 window를 사용했는지, surrogate 종료점을 썼는지, mixed selection을 어떻게 통과했는지, step/nonstep class가 무엇인지가 기록된다. 특히 아래 컬럼이 분석 창 해석의 기준이 된다.

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

`analysis_window_source`는 기본적으로 `actual_step_onset`, `subject_mean_step_onset`, `platform_offset` 중 하나를 가진다. figure는 `global_step_clusters.png`와 `global_nonstep_clusters.png` 두 장으로 저장되며, 각 cluster마다 왼쪽에 `W` bar plot, 오른쪽에 `H(100-window)` line plot을 배치한다. aggregate CSV와 group 디렉터리 안 CSV에는 모두 `group_id`가 포함되므로, 행이 step 집단인지 nonstep 집단인지 바로 확인할 수 있다.

## 9. 재현 실행과 검증

이 저장소의 공식 실행 환경은 conda env `cuda`다. Python과 pip는 아래 형식으로 실행한다.

```bash
conda run -n cuda python ...
conda run -n cuda pip ...
```

fixture 입력으로 전체 파이프라인을 재현하려면 저장소 루트에서 아래 명령을 실행한다.

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

실운영 계산은 아래 형식을 사용한다.

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

## 10. 현재 범위와 제한

- 기본 mixed selection은 `mixed == 1`, 총 4 trial, step 2회, nonstep 2회, 선택된 step trial의 실제 `step_onset` complete, subject당 comparison velocity 1개 조건을 요구한다.
- 군집화 단계에서 선택된 trial은 반드시 step 또는 nonstep 중 정확히 하나의 집단에만 속해야 한다. 양쪽 모두에 속하거나 어느 쪽에도 속하지 않는 trial이 발견되면 파이프라인은 `ValueError`로 즉시 실패한다.
- `global_step` 또는 `global_nonstep` 집단 중 하나라도 비어 있으면 군집화를 진행하지 않고 `ValueError`로 실패한다.
- cross-subject global cluster alignment는 현재 구현하지 않았다.
- figure는 PNG export를 기본 형식으로 사용한다.
- Qt 관련 `wayland` plugin 경고가 출력될 수 있으나, 현재 fixture 실행 기준 산출물 생성에는 영향을 주지 않았다.
