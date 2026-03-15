# step vs nonstep: 교수님 로직 비교 리포트

## 목적

`analysis/compare_professor/squat_230922.py`의 핵심 NMF 로직(최소 rank VAF>0.9)과 “trial 내부 중복 클러스터 배정 금지” 개념을 사용해서,
현재 프로젝트의 step/nonstep trial에 대해 시너지를 재추출하고,
baseline 파이프라인 결과(`outputs/runs/default_run`)와 비교한다.

## 실행 커맨드

    conda run -n cuda python analysis/compare_professor/compare_step_nonstep_professor_logic.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun \
      --kmeans-retries 100 \
      --overwrite

## 결과 요약

결과 파일은 아래 outdir에서 확인한다.

- Outdir: `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/`
- Summary: `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/summary.json`
- Trial summary: `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/professor_trial_summary.csv`

### 1) trial 수(step/nonstep) 일치 여부

- 기대(baseline default_run): step=53, nonstep=72
- 관측(교수님 로직 재실행): step=53, nonstep=72 (일치)

### 2) 교수님 로직 기준 시너지 수 분포(step vs nonstep)

- baseline(pipeline n_components, 전체 125 trial): `{1:1, 2:6, 3:37, 4:50, 5:26, 6:4, 7:1}`
- professor(NMF init=random, random_state=0, VAF>0.9 최소 rank, 전체 125 trial): `{1:1, 2:6, 3:36, 4:51, 5:26, 6:4, 7:1}`

그룹별(professor 기준):

- step(53 trial): `{2:3, 3:10, 4:16, 5:19, 6:4, 7:1}`
- nonstep(72 trial): `{1:1, 2:3, 3:26, 4:35, 5:7}`

요약:

- 이번 데이터/윈도우에서는 **교수님 방식 NMF와 파이프라인 NMF가 선택한 시너지 수가 거의 동일**했다.  
  (rank=3/4에서 1개씩만 swap된 수준)

### 3) 시너지 구조(centroids) 비교: professor vs pipeline

산출물:

- professor centroids:
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/global_step_centroids_professor.png`
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/global_nonstep_centroids_professor.png`
- professor vs pipeline cosine similarity heatmap:
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/global_step_similarity_professor_vs_pipeline.png`
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/global_nonstep_similarity_professor_vs_pipeline.png`

정량 요약(각 professor cluster별 “가장 유사한 pipeline cluster”의 cosine similarity 평균):

- global_step mean(best cosine) = `0.908149819`
- global_nonstep mean(best cosine) = `0.884180503`

### 4) 클러스터링(“trial 내부 중복 배정 금지”) 처리 메모

교수님 코드의 핵심 제약은 “한 trial 안에서 여러 시너지가 같은 클러스터로 중복 배정되면 안 됨”이다.

이번 구현에서는 비교를 위해 cluster 수의 시작값을 **`max(2, 각 그룹의 최대 시너지 수)`**로 둔다.

- step: K=7 (최대 시너지 수=7)
- nonstep: K=5 (최대 시너지 수=5)

이번 스크립트(`compare_step_nonstep_professor_logic.py`)의 실제 동작은 아래와 같다.

1. `k_min = max(2, 그룹 내 최대 시너지 수)`로 둔다. (이번 데이터에서는 step 7, nonstep 5)
2. 바깥 `retry` 루프를 `0..99`까지 돌리며, 각 retry에서 `random_state = seed + retry`, `n_init = 1`로 KMeans 후보 해를 다시 생성한다.
3. 각 retry 안에서는 `k_min..k_max`를 순서대로 시험하고, “trial 내부 중복 배정이 0”이 되는 **첫 번째 K**만 성공 후보로 저장한다.
4. 모든 retry가 끝나면, 성공 후보들 중 **mode K**를 선택하고, 동률이면 **더 작은 K**를 고른다.
5. 같은 K 안에서는 **inertia가 가장 작은 해**를 고르고, 여기까지도 같으면 **더 작은 retry index**를 최종 채택한다.
6. 성공 후보가 하나도 없을 때만 SciPy Hungarian assignment 기반의 **고유 배정(unique assignment) 보정**을 마지막 fallback으로 사용한다.

이번 데이터에서는 retry 기반 성공 후보가 이미 충분히 나와 fallback은 사용되지 않았다.

- step: 성공 후보 19개, 선택 K=20, 선택 retry=34, `status=success_retry_selected`
- nonstep: 성공 후보 35개, 선택 K=22, 선택 retry=99, `status=success_retry_selected`

참고:

- 교수님 원본은 성공 후보를 모은 뒤 추가 ICC 절차로 최종 해를 고르지만, 이번 비교 스크립트는 그 단계까지는 옮기지 않았다.
- 따라서 현재 구현의 최종 선택 규칙은 **mode K + lowest inertia**이며, 교수님 코드와 완전히 동일한 후처리는 아니다.

### 5) repair vs retry-only 해석 메모

- `repair` 자체가 연구적으로 “틀린” 것은 아니다. 다만 의미가 달라진다.
- retry-only 선택은 **KMeans가 자연스럽게 만든 duplicate-free 해**를 채택하는 해석에 가깝다.
- 반대로 Hungarian `repair`는 낮은 `K`에서 먼저 만든 해를 바탕으로, trial 내부 중복이 없도록 **사후 재배정(post-hoc assignment)** 하는 절차다.
- 따라서 `repair` 결과는 within-trial uniqueness 제약은 만족하지만, 반드시 “원래 KMeans가 선택한 가장 가까운 중심”만을 반영한다고 보기는 어렵다.
- 이 차이 때문에 `repair`를 쓰면 pipeline처럼 compact한 대표 cluster를 만들기 쉬워지고, retry-only를 쓰면 데이터가 요구하는 더 큰 `K`가 그대로 드러날 수 있다.
- 이번 비교에서 pipeline 결과와 크게 벌어진 직접 원인은 NMF가 아니라 **클러스터링 granularity 차이**였다.
- 즉, 기존 구현은 사실상 낮은 `K`에서 repair가 작동해 pipeline의 `K=7/5`와 비슷한 구조를 만들었고, 현재 retry-only 선택은 자연해 기준으로 `K=20/22`를 선택해 더 잘게 분할되었다.

### 6) 최신 재시도 결과의 cluster coverage

pipeline figure subtitle 기준은 `n_trials / total_trials (trial_pct) | n_subjects / total_subjects`이다.
아래 표는 최신 결과(`professor_step_nonstep_compare_retry_rerun`) 기준으로 같은 통계를 정리한 것이다.

#### step (`53 trials`, `21 subjects`)

| cluster_id | n_trials | trial_pct | n_subjects |
|---|---:|---:|---:|
| 0 | 9 | 17.0% | 6 |
| 1 | 15 | 28.3% | 9 |
| 2 | 9 | 17.0% | 5 |
| 3 | 19 | 35.8% | 12 |
| 4 | 7 | 13.2% | 6 |
| 5 | 11 | 20.8% | 7 |
| 6 | 15 | 28.3% | 8 |
| 7 | 6 | 11.3% | 5 |
| 8 | 12 | 22.6% | 8 |
| 9 | 16 | 30.2% | 10 |
| 10 | 17 | 32.1% | 12 |
| 11 | 6 | 11.3% | 5 |
| 12 | 5 | 9.4% | 4 |
| 13 | 12 | 22.6% | 8 |
| 14 | 15 | 28.3% | 9 |
| 15 | 6 | 11.3% | 4 |
| 16 | 27 | 50.9% | 15 |
| 17 | 1 | 1.9% | 1 |
| 18 | 8 | 15.1% | 7 |
| 19 | 10 | 18.9% | 8 |

해석상 큰 cluster만 보면 `C16 (50.9%)`, `C3 (35.8%)`, `C10 (32.1%)`, `C9 (30.2%)`, `C1/C6/C14 (각 28.3%)`가 상대적으로 넓게 분포한다.

#### nonstep (`72 trials`, `24 subjects`)

| cluster_id | n_trials | trial_pct | n_subjects |
|---|---:|---:|---:|
| 0 | 14 | 19.4% | 9 |
| 1 | 23 | 31.9% | 13 |
| 2 | 7 | 9.7% | 4 |
| 3 | 10 | 13.9% | 7 |
| 4 | 34 | 47.2% | 18 |
| 5 | 15 | 20.8% | 8 |
| 6 | 13 | 18.1% | 12 |
| 7 | 16 | 22.2% | 10 |
| 8 | 12 | 16.7% | 5 |
| 9 | 13 | 18.1% | 10 |
| 10 | 5 | 6.9% | 4 |
| 11 | 9 | 12.5% | 6 |
| 12 | 10 | 13.9% | 6 |
| 13 | 5 | 6.9% | 4 |
| 14 | 13 | 18.1% | 9 |
| 15 | 9 | 12.5% | 3 |
| 16 | 8 | 11.1% | 6 |
| 17 | 2 | 2.8% | 2 |
| 18 | 6 | 8.3% | 5 |
| 19 | 11 | 15.3% | 7 |
| 20 | 7 | 9.7% | 5 |
| 21 | 18 | 25.0% | 13 |

해석상 큰 cluster만 보면 `C4 (47.2%)`, `C1 (31.9%)`, `C21 (25.0%)`, `C7 (22.2%)`, `C5 (20.8%)`가 상대적으로 넓게 분포한다.

## 재현성 / MD5 체크

동일한 설정으로 outdir을 2개로 나눠 재실행했을 때 `.csv`/`.json` 산출물의 MD5가 일치함을 확인했고, 정리 후에는 가장 최근 결과만 남겨 두었다.

- 현재 유지된 최신 결과: `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun/checksums.md5`

## 해석 메모

- 교수님 코드의 원래 흐름은 “raw EMG → 필터 → window → 100프레임 리샘플 → min-max 정규화 → NMF”인데,
  이번 비교에서는 입력 parquet이 이미 resampled/min-max 정규화이므로 추가 리샘플/정규화를 생략했다. (README 참고)
- 파이프라인은 component 정규화 및 rank 탐색 제한(`max_components_to_try`) 때문에 교수님 로직과 구조적으로 결과가 달라질 수 있다.
