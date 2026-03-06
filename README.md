# EMG Synergy Clustering

실험의 EMG 데이터를 `subject-velocity-trial` 단위로 정리하고,
trial별 시너지 특징을 추출한 뒤 피험자 내(intra-subject) 클러스터링 결과를 저장하는 파이프라인입니다.

이 저장소는 연구자가 다음 흐름을 한 번에 실행할 수 있도록 구성되어 있습니다.

- 입력 CSV 로드
- trial 구간 추출
- 시너지 특징 추출
- 피험자 내 클러스터링
- 대표 시너지와 요약 파일 저장
- 실행 이력(`run_manifest.json`) 기록

현재 기준으로 알아두면 좋은 핵심 제약은 아래와 같습니다.

- `feature_extractor.type: nmf` 는 CPU 전용입니다.
- 기본 클러스터링 알고리즘인 `cuml_kmeans` 는 GPU가 필요합니다.
- `feature_extractor.type: cnn` 경로는 연구 확장을 위한 placeholder입니다.

## 이 README가 다루는 내용

이 문서는 코드를 설명하기보다, 처음 실행하는 사람이 바로 따라 할 수 있도록 아래에 집중합니다.

- 어떤 입력 파일이 필요한지
- 어떤 환경에서 실행해야 하는지
- `config.yaml`에서 무엇을 바꿔야 하는지
- 실행 후 어떤 결과물이 생성되는지
- 결과 검증은 어떻게 하는지

## 파이프라인 개요

```text
입력 CSV (EMG, frame x channel)
  -> subject-velocity-trial 기준 그룹화
  -> platform on-offset.xlsx 기준 trial 구간 추출
  -> feature_extractor 실행
      - nmf: CPU-only NMF
      - cnn: placeholder feature path
  -> trial별 특징 행렬 정리
  -> 피험자 내 클러스터링
  -> 대표 W/H 및 요약 CSV 저장
  -> 전체 통합 결과와 run_manifest.json 저장
```

## 실행 환경

이 저장소는 기존 conda 환경 `cuda`(WSL2) 사용을 전제로 합니다.
새 `venv`를 만들지 않고, 아래 형식을 그대로 사용하는 것을 권장합니다.

## 실행 전에 준비할 것

기본 설정 기준으로 아래 입력이 필요합니다.

### 1. EMG 입력 CSV

기본 경로:

```text
"C:\Users\Alice\OneDrive - 청주대학교\근전도 분석 코드\shared_files\output\02_processed\Chvatal_35-40\processed_emg_data.parquet"
```

### 2. 플랫폼 이벤트 Excel 파일

기본 경로:

```text
/mnt/c/Users/Alice/OneDrive - 청주대학교/근전도 분석 코드/perturb_inform.xlsx
```

## `config.yaml`에서 자주 확인할 항목

실행 전에는 아래 블록만 먼저 확인해도 대부분의 실행 실수를 줄일 수 있습니다.

### 1. 입력 경로

```yaml
input:
  csv_path: "DATA_input/min-max_data.csv"
  platform_excel_path: "/mnt/c/Users/Alice/OneDrive - 청주대학교/근전도 분석 코드/platform on-offset.xlsx"
```

### 2. 사용할 근육 채널

```yaml
muscles:
  names: ["TA","EHL","MG","SOL","PL","RF","VL","ST","RA","EO","IO","SCM","GM","ESC","EST","ESL"]
```

### 3. 특징 추출기 선택

```yaml
feature_extractor:
  type: "nmf"  # allowed: "nmf" | "cnn"
```

- `nmf`: 실제 기본 경로입니다.
- `cnn`: 현재는 placeholder 경로입니다.

### 4. NMF 관련 설정

```yaml
feature_extractor:
  nmf:
    vaf_threshold: 0.90
    max_components_to_try: 15
    random_state: 42
    fit_params:
      max_iter: 5000
      tol: 0.0001
      beta: 2
```

이 블록은 NMF 시너지 추출의 기준을 정합니다.
실험 조건 비교 중이 아니라면, 먼저 기본값으로 실행한 뒤 결과를 확인하는 흐름을 권장합니다.

### 5. 클러스터링 설정

```yaml
synergy_clustering:
  algorithm: "cuml_kmeans"
  max_clusters: 25
  repeats: 1000
  random_state: 42
```

중요:

- 현재 구현 기준으로 `algorithm: "cuml_kmeans"` 가 기본값입니다.
- 이 설정은 CUDA 장치가 필요합니다.
- 즉, NMF가 CPU-only라고 해서 전체 파이프라인이 CPU-only가 되는 것은 아닙니다.

### 6. 실행 환경 설정

```yaml
runtime:
  gpu_required: true
  seed: 42
  output_dir: "DATA_output"
  log_dir: "logs"
```

`runtime.gpu_required` 와 `synergy_clustering.algorithm` 조합에 따라 실제 GPU 필요 여부가 결정됩니다.
현재 코드는 GPU가 필요한 조건에서 CUDA 장치를 찾지 못하면 실행을 중단하도록 되어 있습니다.

## 실행 예시

### 1. 기본 실행

기본 설정 그대로 NMF 추출과 기본 클러스터링을 수행합니다.

```bash
conda run -n cuda python main.py \
  --config config.yaml \
  --out DATA_output_runs/nmf_default
```

## 재현성과 기록

### 1. 시드 고정

`runtime.seed` 값으로 아래 라이브러리의 난수 시드를 가능한 범위에서 함께 맞춥니다.

- `python`
- `numpy`
- `torch`

### 2. 실행 매니페스트 저장

매 실행마다 `run_manifest.json` 이 생성되며, 실행 환경을 추적하는 데 필요한 핵심 정보가 기록됩니다.

예:

- `created_at_utc`
- `python_executable`
- `python_version`
- `platform`
- `feature_extractor_type`
- `config_sha256`
- `runtime_seed`

같은 설정으로 반복 실행했는지 확인할 때 이 파일을 먼저 보는 것이 좋습니다.

## 결과 검증: MD5 비교

파이프라인 로직이 바뀌었을 때는 기존 출력과 새 출력을 비교해, 의도하지 않은 결과 차이가 없는지 확인할 수 있습니다.
현재 README 수정만으로는 이 검증이 필요하지 않지만, 실제 로직 변경 시에는 아래 절차를 그대로 재사용하면 됩니다.

## 현재 제한 사항

- `feature_extractor.type: cnn` 은 placeholder 경로입니다.
- 기본 클러스터링 구현은 `cuml_kmeans` 기준으로 설명되어 있습니다.
- 전체 파이프라인을 완전한 CPU-only로 운용하려면, 클러스터링 단계에도 CPU 대체 구현이 필요합니다.
- Excel 입력 경로가 로컬 OneDrive 경로를 가리키므로, 환경이 바뀌면 경로 수정이 필요할 수 있습니다.

