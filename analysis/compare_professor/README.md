# compare_professor (교수님 로직 비교)

이 폴더는 **교수님 muscle synergy 분석 로직**을 현재 프로젝트 데이터셋/파이프라인 구조에 맞춰 재실행하고, `step vs nonstep` 결과를 main pipeline 기준 baseline bundle과 비교하기 위한 분석 작업 공간이다.

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
     (교수님 코드는 바깥 재시도 루프에서 후보 해를 여러 번 만들고, 중복이 없는 해를 저장하는 방식)

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
   - 또한 baseline(`outputs/runs/default_run/all_trial_window_metadata.csv`)의 `analysis_step_class`와 event 기반 라벨이 **완전히 동일한지** 스크립트 실행 시점에 검증한다.  
     (불일치하면 비교가 의미가 없으므로 중단)

## 3) 교수님 로직 vs 내 synergy analysis(파이프라인) 로직 차이점

baseline 파이프라인 결과(내 결과물)는 예시로 `outputs/runs/default_run/` 아래에 둘 수 있다. 현재 main pipeline의 source of truth는 pooled clustering 기반 baseline이며, 이 비교 스크립트는 그 metadata를 따르면서도 similarity figure를 위해 legacy per-group representative export가 들어 있는 **호환 baseline bundle**을 추가로 요구한다.

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

- 교수님: 바깥 재시도 루프에서 KMeans를 여러 번 다시 실행하고, trial 내부 중복이 없는 후보 해를 저장한 뒤 그 후보들 중에서 cluster 수를 정하는 흐름이다.
- 파이프라인: 현재 main pipeline은 mode별 단일 `pooled_step_nonstep` group을 source of truth로 사용하고, gap statistic과 zero-duplicate feasibility를 함께 반영해 대표 cluster를 고른다.

이번 비교 구현(`compare_step_nonstep_professor_logic.py`)에서는 다음 절충을 적용했다.

- 먼저 step/nonstep 각각에 대해 `k_min = max(2, 그룹 내 최대 시너지 수)`로 둔다. (이번 데이터에서는 step 7, nonstep 5)
- 바깥 `retry` 루프(`--kmeans-retries`, 기본 100)에서 `random_state = seed + retry`, `n_init = 1`로 KMeans 후보 해를 다시 만든다.
- 각 retry 안에서는 `k_min..k_max`를 순서대로 시험하고, trial 내부 중복이 없는 **첫 번째 K**만 그 retry의 성공 후보로 저장한다.
- 전체 retry가 끝나면, 저장된 후보들 중 **가장 자주 나온 cluster 수(mode K)**를 고르고, 동률이면 **더 작은 K**를 택한다.
- 같은 K 후보들 안에서는 **inertia가 가장 작은 해**를 고르고, 여기까지도 같으면 **더 작은 retry index**를 최종 해로 선택한다.
- 끝까지 성공 후보가 하나도 없을 때만 SciPy Hungarian assignment 기반의 **고유 배정(unique assignment) 보정**을 마지막 fallback으로 사용한다.
- 교수님 원본의 후속 ICC 기반 최종 선택까지는 이번 스크립트에서 재현하지 않았고, 대신 `mode K + lowest inertia`를 현재 선택 규칙으로 사용한다.

즉, 기본은 교수님식 “반복 KMeans 해 중 선택” 흐름이고, Hungarian은 교수님 원본의 일부가 아니라 현재 비교 스크립트의 안전장치다.

### 3.3 출력 산출물 위치/형식 차이

- 교수님 비교 분석(이번 작업): `analysis/compare_professor/artifacts/...`
- 파이프라인(main baseline 예시): `outputs/runs/default_run/...`

단, 현재 비교 스크립트는 `all_trial_window_metadata.csv` 외에도 `global_step/representative_W_posthoc.csv`, `global_nonstep/representative_W_posthoc.csv`를 읽어 교수님 centroid와 baseline centroid의 cosine similarity figure를 만든다. 따라서 bare pooled-only run이 아니라 이 호환 파일까지 포함한 baseline bundle이 필요하다.

## 4) 실행 방법

작업 디렉토리: repo root (`/home/alice/workspace/26-03-synergy-analysis`)

	    conda run -n cuda python analysis/compare_professor/compare_step_nonstep_professor_logic.py \
	      --config configs/global_config.yaml \
	      --baseline-run outputs/runs/default_run \
	      --outdir analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun \
	      --kmeans-retries 100 \
	      --overwrite

실행 환경 메모:

- “고유 배정(unique assignment) 보정(fallback)” 경로는 `scipy`가 필요하다.
- 기본 KMeans 동작은 `n_init=1`, `random_state=seed+retry` 기반의 professor-style retry search다.
- `--baseline-run`은 최소한 `all_trial_window_metadata.csv`와 legacy `global_step/global_nonstep` representative export를 함께 포함한 호환 baseline bundle이어야 한다.

현재 남겨둔 최신 결과 기준 주요 파일:

- `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/summary.json`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/professor_trial_summary.csv`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/global_step_centroids_professor.csv`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/global_nonstep_centroids_professor.csv`
- `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/checksums.md5`

## 5) 리포트

정리된 비교 리포트: `analysis/compare_professor/report.md`
