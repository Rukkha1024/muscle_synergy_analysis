# 이슈 007: pooled shared-specific synergy 분석 워크플로 구현

**상태**: 완료
**생성일**: 2026-03-15

## 배경

현재 EMG synergy pipeline은 `global_step`과 `global_nonstep`을 서로 분리해서 clustering 하므로, 두 조건에서 같은 `cluster_id`가 나와도 이를 공통 조건 수준의 identity로 바로 해석할 수 없다. 승인된 ExecPlan `.agents/execplans/onet_cluster.md`는 baseline pipeline을 수정하지 않고, analysis 전용으로 trial synergy를 다시 추출한 뒤 step/nonstep 구조 벡터를 하나의 shared clustering space로 풀링하고, cluster 요약표, figure, 사람이 읽는 report를 export하는 워크플로를 정의한다.

이 작업이 필요한 이유는 사용자가 pooled cluster가 조건 간에 얼마나 공유되는지, 각 조건이 해당 cluster를 얼마나 점유하는지, 몇 명의 subject가 기여하는지, 그리고 같은 cluster 안에서 step과 nonstep 대표 `H` 프로파일이 어떻게 다른지를 직접 확인할 수 있어야 하기 때문이다.

## 완료 기준

- [x] `analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py`가 존재하고 `--dry-run`, `--baseline-run`, `--outdir`, `--overwrite`를 지원한다.
- [x] 분석 시작 전에 baseline `all_trial_window_metadata.csv`와 event 기반 trial key 및 step/nonstep label이 완전히 일치하는지 검증한다.
- [x] pooled clustering search가 gap statistic + zero-duplicate constraint를 사용하고 `k_lb`, `k_gap_raw`, `k_selected`를 기록한다.
- [x] 실행 결과로 `pooled_cluster_members.csv`, `pooled_cluster_summary.csv`, `pooled_representative_W.csv`, `pooled_representative_H_long.csv`가 생성된다.
- [x] `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/` 아래에 계획된 6개 figure가 생성된다.
- [x] `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/report.md`에 사람이 읽을 수 있는 artifact report가 생성된다.
- [x] 검증에 dry-run, full execution, output schema/file 확인, reviewer pass, rerun output MD5 비교가 포함된다. 필수 사용자 산출물은 모두 일치했고, `run_metadata.json`만 극미한 floating-point drift가 남았다.

## 작업 목록

- [x] 1. `analysis/pooled_shared_specific_synergy/` 폴더와 메인 엔트리 스크립트, 폴더 수준 report를 만든다.
- [x] 2. config 입력에서 selected trial table을 다시 구성하고 `outputs/runs/default_run/all_trial_window_metadata.csv`와 대조 검증한다.
- [x] 3. trial-level NMF feature를 다시 추출하고 모든 step/nonstep 구조 벡터를 하나의 clustering table로 풀링한다.
- [x] 4. gap-statistic selection과 zero-duplicate enforcement로 pooled clustering을 수행한다.
- [x] 5. pooled member, summary, representative `W`, representative `H` 산출물을 export한다.
- [x] 6. 계획된 6개 figure와 artifact `report.md`를 생성한다.
- [x] 7. dry-run/full validation, rerun MD5 비교, reviewer check, 한국어 5줄 커밋 메시지까지 완료한다.

## 참고 사항

- 기준 계획 문서: `.agents/execplans/onet_cluster.md`
- 범위 경계: analysis 전용. `scripts/emg/*`를 수정하거나 `outputs/runs/default_run/*`를 덮어쓰지 않는다.
- 예상 output 루트:
  - `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/`
- 주요 산출물:
  - `pooled_cluster_members.csv`
  - `pooled_cluster_summary.csv`
  - `pooled_representative_W.csv`
  - `pooled_representative_H_long.csv`
  - `figures/pooled_clusters.png`
  - `figures/step_vs_nonstep_W.png`
  - `figures/step_vs_nonstep_H.png`
  - `figures/occupancy_summary.png`
  - `figures/k_selection_diagnostic.png`
  - `figures/subcentroid_similarity_heatmap.png`
  - `report.md`
- 검증 실행은 `module` 환경의 처리 시간을 고려해 pooled 로직은 유지하되 다음 practical override를 사용했다: `--nmf-backend sklearn_nmf --clustering-algorithm sklearn_kmeans --repeats 40 --gap-ref-n 20 --gap-ref-restarts 10 --uniqueness-candidate-restarts 80`.
- 관찰된 검증 결과: dry-run은 `125` selected trial, `24` selected subject로 통과했고, full run은 `486` pooled component, `k_lb=7`, `k_gap_raw=13`, `k_selected=16`, selected `K`에서 duplicate `0`을 기록했다.
