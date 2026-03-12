# compare_professor (교수님 로직 비교)

이 폴더는 **교수님 muscle synergy 분석 로직**을 현재 프로젝트 데이터셋/파이프라인 구조에 맞춰 재실행하고, `step vs nonstep` 결과를 내 파이프라인 산출물과 비교하기 위한 분석 작업 공간이다.

## 1) 교수님 분석 로직(핵심)

원본 레퍼런스: `analysis/compare_professor/squat_230922.py`

이 프로젝트에서 “교수님 로직”으로 재현하는 핵심은 다음 2가지다.

1. **NMF 시너지 수 선택 규칙(VAF 기반)**  
   - trial EMG 행렬 `X(time × muscles)`에 대해 rank를 1부터 근육 수까지 증가시키며 NMF를 수행한다.
   - 매 rank에서 재구성 오차로 VAF(Variance Accounted For)를 계산한다.
   - **VAF가 처음으로 0.90을 초과하는 최소 rank**를 해당 trial의 시너지 수로 선택한다.
   - 구현 세팅(교수님 코드 그대로):
     - `sklearn.decomposition.NMF(init="random", random_state=0)`
     - `VAF = 1 - sum((X - X_hat)^2) / sum(X^2)`

2. **시너지 구조 클러스터링(정렬/정합) 아이디어**  
   - trial마다 얻어진 “시너지 구조 벡터(근육 가중치)”를 풀링하여 KMeans로 클러스터링한다.
   - 중요한 제약: **한 trial 안에서 여러 시너지가 같은 클러스터로 중복 배정되면 안 된다.**  
     (교수님 코드는 중복이 없어질 때까지 K를 증가시키며 재시도하는 방식)

## 2) 유저 데이터셋에 맞춰서 변경된 점(이번 작업의 의사결정)

이번 비교는 사용자 답변을 반영해서 아래처럼 “데이터셋 현실”에 맞춰 교수님 로직 일부를 생략/대체한다.

1. **추가 리샘플/추가 min-max 정규화는 하지 않는다.**  
   - 이유: 이 프로젝트의 입력 parquet(`min-max_norm_only.parquet`) 자체가 이미 trial별 **고정 프레임(resampled_frame 0~499)** 및 **min-max 정규화**된 EMG를 포함한다.
   - 따라서 교수님 코드에서 하던 “window를 100프레임으로 재리샘플 + 채널별 min-max 정규화”는 본 비교에서 생략한다.

2. **추가 EMG 필터(HP/LP)는 적용하지 않는다.**  
   - 이유: 입력 parquet이 이미 post-processed(정규화 포함)된 데이터로 간주한다.

3. **step vs nonstep 분리는 교수님 코드가 아니라, 프로젝트 이벤트 메타데이터를 사용한다.**  
   - `configs/global_config.yaml`의 `event_xlsm_path`(perturb_inform.xlsm)로부터 `analysis_is_step`, `analysis_is_nonstep` 라벨을 만들고,
   - 동일 trial window 선택 규칙으로 trial을 구성한 뒤 step/nonstep 그룹으로 분리한다.

## 3) 교수님 로직 vs 내 synergy analysis(파이프라인) 로직 차이점

baseline 파이프라인 결과(내 결과물)는 `outputs/runs/default_run/` 아래에 존재한다.

### 3.1 NMF 차이

- **초기화/난수**
  - 교수님: `init="random"`, `random_state=0`
  - 파이프라인: `init="nndsvda"` (config 기반), seed는 `runtime.seed` 기반

- **성분 정규화**
  - 교수님: NMF 결과를 별도 정규화하지 않고 그대로 사용
  - 파이프라인: 시너지 구조/활성을 재스케일(정규화)하여 trial 간 비교가 안정적이도록 처리

- **rank 탐색 범위**
  - 교수님: 1..근육 수(예: 16)까지 탐색
  - 파이프라인: `configs/synergy_stats_config.yaml`의 `max_components_to_try`(현재 8)까지만 탐색

### 3.2 클러스터링 차이

- 교수님: “중복 배정이 없어질 때까지 K를 키우며” KMeans를 반복 실행하는 방식(개념적으로).
- 파이프라인: KMeans + within-trial 제약을 만족시키기 위한 보정 로직이 포함되어 있으며, 결과를 `outputs/runs/<run_id>/global_*/*`로 export한다.

이번 비교 구현(`compare_step_nonstep_professor_logic.py`)에서는 다음 현실적인 절충을 적용했다.

- step/nonstep 각각에 대해 K를 “그 그룹의 최대 시너지 수”로 두고(K=7, K=5),
- raw KMeans 결과에서 trial 내부 중복이 발생하는 경우가 많아, centroid 거리(cost) 기반의 **고유 배정(unique assignment) 보정**을 적용해 중복을 0으로 만든다.

즉, “중복 배정 금지”라는 교수님 제약을 **항상 만족**시키도록 구현은 했지만, 중복 해소 방식은 교수님 코드의 “K 증가 재시도”와 1:1로 동일하지 않다.

### 3.3 출력 산출물 위치/형식 차이

- 교수님 비교 분석(이번 작업): `analysis/compare_professor/artifacts/...`
- 파이프라인(내 결과물 baseline): `outputs/runs/default_run/...`

## 4) 실행 방법

작업 디렉토리: repo root (`/home/alice/workspace/26-03-synergy-analysis`)

    conda run -n module python analysis/compare_professor/compare_step_nonstep_professor_logic.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/compare_professor/artifacts/professor_step_nonstep_compare \
      --overwrite

생성되는 주요 파일(예시):

- `analysis/compare_professor/artifacts/professor_step_nonstep_compare/summary.json`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare/professor_trial_summary.csv`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare/global_step_centroids_professor.csv`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare/global_nonstep_centroids_professor.csv`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare/checksums.md5`

## 5) 리포트

정리된 비교 리포트: `analysis/compare_professor/report.md`
