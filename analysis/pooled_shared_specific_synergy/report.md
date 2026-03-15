# pooled_shared_specific_synergy

이 폴더는 `.agents/execplans/onet_cluster.md`를 구현하는 **analysis 전용 pooled synergy clustering 작업 공간**이다. baseline pipeline이 step과 nonstep을 각각 따로 clustering 하는 것과 달리, 여기서는 두 조건에서 나온 모든 trial-level synergy 구조 벡터를 한 번에 풀링해서 공통 cluster space를 만든다.

핵심 목적은 같은 `cluster_id` 안에서 다음을 직접 비교하는 것이다.

- step member 수와 nonstep member 수
- step/nonstep subject coverage
- step sub-centroid와 nonstep sub-centroid의 구조 유사도
- 같은 cluster 안에서 step 대표 `H`와 nonstep 대표 `H`의 시간 프로파일 차이

## 실행 방법

작업 디렉터리: repo root (`/home/alice/workspace/26-03-synergy-analysis`)

먼저 baseline 정렬과 입력 경로만 확인하는 dry-run:

    conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
      --dry-run

실제 pooled 분석 실행:

    conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
      --overwrite

검증 중 실제로 사용한 practical override 예시는 아래와 같다. `module` 환경에서 빠르게 끝까지 검증하기 위해 backend와 search 횟수만 줄였고, pooled clustering 로직 자체는 유지했다.

    conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
      --overwrite \
      --nmf-backend sklearn_nmf \
      --clustering-algorithm sklearn_kmeans \
      --repeats 40 \
      --gap-ref-n 20 \
      --gap-ref-restarts 10 \
      --uniqueness-candidate-restarts 80

## 기대 산출물

실행이 끝나면 아래 경로 아래에 pooled 분석 산출물이 생성된다.

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/

주요 CSV:

- `pooled_cluster_members.csv`
- `pooled_cluster_summary.csv`
- `pooled_representative_W.csv`
- `pooled_representative_H_long.csv`

주요 figure:

- `figures/pooled_clusters.png`
- `figures/step_vs_nonstep_W.png`
- `figures/step_vs_nonstep_H.png`
- `figures/occupancy_summary.png`
- `figures/k_selection_diagnostic.png`
- `figures/subcentroid_similarity_heatmap.png`

## 리포트 위치

실행마다 사람이 바로 읽을 수 있는 artifact report가 아래 위치에 생성된다.

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/report.md

이 artifact report에는 최소한 selected trial 수, selected subject 수, `k_lb`, `k_gap_raw`, `k_selected`, cluster별 occupancy/coverage, 높은 sub-centroid similarity cluster, 그리고 6개 figure에 대한 한 줄 해석이 정리되어야 한다.

현재 검증 결과 기준으로는 `125` selected trial, `24` selected subject, `486` pooled component, `k_lb=7`, `k_gap_raw=13`, `k_selected=16`이 관찰되었고, selected `K`에서 duplicate trial count는 `0`이었다.

## 해석 메모

이 분석은 **pipeline 대체가 아니라 analysis-only validation/interpretation layer**다. 따라서 baseline output을 덮어쓰지 않으며, 결과 해석도 항상 `outputs/runs/default_run/`과 분리해서 본다.
