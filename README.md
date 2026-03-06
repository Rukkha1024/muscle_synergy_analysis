# EMG Synergy Pipeline

이 저장소는 EMG parquet와 이벤트 xlsm을 받아 `subject-velocity-trial` 단위로 trial을 자르고,
trial별 시너지(NMF)를 추출한 뒤 피험자 내 클러스터링 결과를 저장하는 파이프라인입니다.
현재 구현은 저장소 아키텍처 규칙에 맞춰 `configs/`, `src/`, `scripts/`, `outputs/`, `tests/` 구조로 정리되어 있습니다.

## 빠른 시작

이 저장소의 공식 실행 환경은 conda env `module`입니다.
Python과 pip는 아래 형식으로만 실행합니다.

```bash
conda run -n module python ...
conda run -n module pip ...
```

fixture 입력으로 전체 파이프라인을 바로 검증하려면 저장소 루트에서 아래 명령을 실행합니다.

```bash
conda run -n module python main.py \
  --config tests/fixtures/global_config.yaml \
  --out outputs/runs/fixture_run \
  --overwrite
```

성공하면 아래 결과가 생성됩니다.

- `outputs/runs/fixture_run/run_manifest.json`
- `outputs/runs/fixture_run/final_summary.csv`
- `outputs/runs/fixture_run/all_*.csv`
- `outputs/runs/fixture_run/subject_<subject>/...`
- `outputs/final.parquet`

## 입력 파일

기본 실행은 아래 두 입력을 사용합니다.

- EMG parquet: `input.emg_parquet_path`
- 이벤트 xlsm: `input.event_xlsm_path`

기본 경로는 [configs/global_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/global_config.yaml)에 정의되어 있습니다.
fixture 실행은 [tests/fixtures/global_config.yaml](/home/alice/workspace/26-03-synergy-analysis/tests/fixtures/global_config.yaml)을 사용합니다.

EMG parquet의 최소 필수 컬럼은 아래와 같습니다.

- `subject`
- `velocity`
- `trial_num`
- `original_DeviceFrame`
- 근육 채널 컬럼들 (`muscles.names`)

이벤트 xlsm의 최소 필수 컬럼은 아래와 같습니다.

- `subject`
- `velocity`
- `trial_num`
- `platform_onset`
- `platform_offset`

## 설정 파일

파이프라인 설정은 `configs/` 아래 YAML로 분리되어 있습니다.

- [configs/global_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/global_config.yaml)
  전역 입력 경로와 런타임 옵션
- [configs/emg_pipeline_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/emg_pipeline_config.yaml)
  EMG trial 정렬과 frame ratio
- [configs/synergy_stats_config.yaml](/home/alice/workspace/26-03-synergy-analysis/configs/synergy_stats_config.yaml)
  근육 목록, NMF, 클러스터링 옵션

루트 오케스트레이터 [main.py](/home/alice/workspace/26-03-synergy-analysis/main.py)는 전역 설정을 먼저 읽고,
도메인 설정을 병합한 뒤 `scripts/emg/NN_*.py` 순서대로 실행합니다.

## 실행 예시

실운영 경로로 실행할 때는 기본 전역 설정을 사용합니다.

```bash
conda run -n module python main.py \
  --config configs/global_config.yaml \
  --out outputs/runs/production_run \
  --overwrite
```

입력 경로만 임시로 바꾸고 싶다면 CLI override를 사용합니다.

```bash
conda run -n module python main.py \
  --config configs/global_config.yaml \
  --parquet /path/to/processed_emg_data.parquet \
  --meta-xlsm /path/to/perturb_inform.xlsm \
  --out outputs/runs/custom_run \
  --overwrite
```

설정과 입력만 먼저 확인하고 전체 계산은 건너뛰려면 dry-run을 사용합니다.

```bash
conda run -n module python main.py \
  --config configs/global_config.yaml \
  --dry-run
```

## 파이프라인 단계

실제 실행 순서는 [main.py](/home/alice/workspace/26-03-synergy-analysis/main.py)에 명시되어 있습니다.

1. [scripts/emg/01_load_emg_table.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/01_load_emg_table.py)
   parquet와 xlsm을 읽고 수동 이벤트 값을 우선 적용합니다.
2. [scripts/emg/02_extract_trials.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/02_extract_trials.py)
   `subject-velocity-trial` 단위로 잘라 `DeviceFrame`을 만듭니다.
3. [scripts/emg/03_extract_synergy_nmf.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/03_extract_synergy_nmf.py)
   trial별 시너지 특징을 추출합니다.
4. [scripts/emg/04_cluster_synergies.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/04_cluster_synergies.py)
   피험자 내 시너지 벡터를 클러스터링합니다.
5. [scripts/emg/05_export_artifacts.py](/home/alice/workspace/26-03-synergy-analysis/scripts/emg/05_export_artifacts.py)
   subject 결과, 통합 CSV, `outputs/final.parquet`를 저장합니다.

## 구현 메모

기본 설정은 reference 정책을 따라 `cuml_kmeans`를 우선 시도합니다.
다만 `module` 환경에 GPU 라이브러리가 없으면 현재 구현은 `sklearn_kmeans` fallback으로 fixture 검증을 계속 진행합니다.
NMF도 `torchnmf`를 우선 시도하고, unavailable이면 `sklearn` fallback을 사용합니다.

즉, fixture 기반 검증은 CPU fallback으로 통과할 수 있고, GPU parity가 필요한 실제 운영에서는
해당 라이브러리가 `module` 환경에 준비되어 있어야 합니다.

## 검증

pytest 전체 실행:

```bash
conda run -n module python -m pytest tests -q
```

curated MD5 비교:

```bash
conda run -n module python main.py \
  --config tests/fixtures/global_config.yaml \
  --out tests/reference_outputs/reference_baseline \
  --overwrite

conda run -n module python main.py \
  --config tests/fixtures/global_config.yaml \
  --out outputs/runs/fixture_run \
  --overwrite

conda run -n module python scripts/emg/99_md5_compare_outputs.py \
  --base tests/reference_outputs/reference_baseline \
  --new outputs/runs/fixture_run
```

이 비교는 변동성이 큰 로그/매니페스트를 제외하고 stable CSV만 검사합니다.

## 현재 범위와 제한

- `analysis/`는 아직 비어 있으며, 이후 분석 코드는 `outputs/final.parquet`만 읽어야 합니다.
- heatmap PNG/SVG는 아직 reference 수준으로 구현하지 않았고, 현재 우선순위는 runnable scaffold와 stable tabular outputs입니다.
- reference repo의 GPU 경로와 완전 parity를 내려면 `module` 환경에 `torch`, `torchnmf`, `cupy`, `cuml`이 준비되어야 합니다.
