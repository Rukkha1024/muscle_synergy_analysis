# step vs nonstep: 교수님 로직 비교 리포트

## 목적

`analysis/compare_professor/squat_230922.py`의 핵심 NMF 로직(최소 rank VAF>0.9)과 “trial 내부 중복 클러스터 배정 금지” 개념을 사용해서,
현재 프로젝트의 step/nonstep trial에 대해 시너지를 재추출하고,
baseline 파이프라인 결과(`outputs/runs/default_run`)와 비교한다.

## 실행 커맨드

    conda run -n module python analysis/compare_professor/compare_step_nonstep_professor_logic.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/compare_professor/artifacts/professor_step_nonstep_compare \
      --overwrite

## 결과 요약(placeholder)

결과 파일은 아래 outdir에서 확인한다.

- Outdir: `analysis/compare_professor/artifacts/professor_step_nonstep_compare/`
- Summary: `analysis/compare_professor/artifacts/professor_step_nonstep_compare/summary.json`
- Trial summary: `analysis/compare_professor/artifacts/professor_step_nonstep_compare/professor_trial_summary.csv`

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
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare/global_step_centroids_professor.png`
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare/global_nonstep_centroids_professor.png`
- professor vs pipeline cosine similarity heatmap:
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare/global_step_similarity_professor_vs_pipeline.png`
  - `analysis/compare_professor/artifacts/professor_step_nonstep_compare/global_nonstep_similarity_professor_vs_pipeline.png`

정량 요약(각 professor cluster별 “가장 유사한 pipeline cluster”의 cosine similarity 평균):

- global_step mean(best cosine) = `0.940837318`
- global_nonstep mean(best cosine) = `0.97319943`

### 4) 클러스터링(“trial 내부 중복 배정 금지”) 처리 메모

교수님 코드의 핵심 제약은 “한 trial 안에서 여러 시너지가 같은 클러스터로 중복 배정되면 안 됨”이다.

이번 구현에서는 비교 가능성을 위해 cluster 수를 **각 그룹의 최대 시너지 수**로 고정했다.

- step: K=7 (최대 시너지 수=7)
- nonstep: K=5 (최대 시너지 수=5)

단, raw KMeans 라벨은 중복이 자주 발생하여(예: step 24 trial, nonstep 27 trial에서 중복),
각 trial 내부에서 centroid에 대한 거리(cost) 기반으로 **고유 배정(unique assignment) 보정**을 적용해 중복을 0으로 만들었다.

## 재현성 / MD5 체크

동일한 설정으로 outdir을 2개로 나눠 재실행 후, `.csv`/`.json` 산출물의 MD5가 동일함을 확인했다.

- 기준: `analysis/compare_professor/artifacts/professor_step_nonstep_compare/checksums.md5`
- 재실행: `analysis/compare_professor/artifacts/professor_step_nonstep_compare_rerun/checksums.md5`

## 해석 메모

- 교수님 코드의 원래 흐름은 “raw EMG → 필터 → window → 100프레임 리샘플 → min-max 정규화 → NMF”인데,
  이번 비교에서는 입력 parquet이 이미 resampled/min-max 정규화이므로 추가 리샘플/정규화를 생략했다. (README 참고)
- 파이프라인은 component 정규화 및 rank 탐색 제한(`max_components_to_try`) 때문에 교수님 로직과 구조적으로 결과가 달라질 수 있다.
