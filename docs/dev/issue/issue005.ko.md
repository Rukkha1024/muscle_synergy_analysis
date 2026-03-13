# 이슈 005: Trial 단위 duplicate cluster assignment 감사

**상태**: 완료
**생성일**: 2026-03-13

## 배경

현재 저장소에는 muscle synergy 해석에 직접 영향을 주는 clustering 경로가 두 개 있습니다. `scripts/emg/`와 `src/synergy_stats/` 아래의 production 경로는 trial-level NMF feature와 duplicate 방지 재배정 단계를 사용하고, `analysis/compare_Cheung,2021/`는 그 safeguard 없이 plain k-means와 gap statistic을 사용하는 논문형 경로를 별도로 가집니다.

사용자는 같은 trial 내부 duplicate cluster assignment가 실제로 얼마나 발생하는지, production 재배정이 정확히 어디서 개입하는지, 그 과정에서 assignment cost를 얼마나 희생하는지, 그리고 이 문제가 downstream biological interpretation을 흔드는 수준인지 재현 가능하게 감사하기를 원합니다. 이번 감사는 production logic와 분리된 스크립트/결과물로 남아야 하며, repo 코드·설정·출력만 근거로 해야 합니다.

## 완료 기준

- [x] production pipeline을 수정하지 않는 독립 audit entrypoint가 존재한다.
- [x] audit가 실제 NMF, normalization, clustering, gap-statistic, matching, reassignment 경로를 정확한 파일/함수명과 함께 매핑한다.
- [x] audit가 paper-like unconstrained clustering과 production pre/post forced reassignment 상태의 duplicate 지표를 계산한다.
- [x] audit가 reassignment 비용 변화, 전이 패턴, 남은 duplicate 예외를 측정한다.
- [x] audit가 `results/duplicate_assignment_audit/` 아래에 요청된 결과 파일과 `summary.md`를 생성한다.
- [x] audit가 `src/synergy_stats/clustering.py`의 uniqueness enforcement 경로를 검증하는 회귀 테스트를 추가한다.
- [x] validation, explorer, reviewer pass를 마친 뒤 마감한다.

## 작업 목록

- [x] 1. audit 범위, 데이터 소스, 지표, 검증 절차를 고정하는 bilingual ExecPlan을 작성한다.
- [x] 2. repo 코드로 paper-like와 production clustering 상태를 재구성하는 독립 audit 스크립트를 구현한다.
- [x] 3. `results/duplicate_assignment_audit/` 아래에 summary table, duplicate-pair export, K 민감도 결과, plot을 생성한다.
- [x] 4. production uniqueness enforcement 동작을 검증하는 집중 회귀 테스트를 추가한다.
- [x] 5. audit와 validation 명령을 실행하고, 핵심 결과와 caveat를 기록한다.
- [x] 6. explorer/reviewer pass를 마친 뒤 한국어 5줄 이상 커밋 메시지로 커밋한다.

## 참고 사항

- audit entrypoint는 `analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`이다.
- 생성된 결과는 `results/duplicate_assignment_audit/` 아래에 `summary.md`, `overall_metrics.csv`, `per_unit_metrics.csv`, `duplicate_pairs.csv`, `per_cluster_stats.csv`, `k_sensitivity.csv`, `reassignment_stats.csv`, plot으로 저장된다.
- 검증은 아래 명령으로 완료했다.
  `conda run --no-capture-output -n module python -m py_compile analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py tests/test_synergy_stats/test_duplicate_assignment_audit.py`
  `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`
  `conda run --no-capture-output -n module pytest tests/test_synergy_stats/test_duplicate_assignment_audit.py`
- 핵심 수치는 다음과 같다.
  paper-like duplicate unit rate `28/125 = 0.224`
  production pre-force duplicate unit rate `35/125 = 0.280`
  production post-force duplicate unit rate `0/125 = 0.000`
  reassigned synergies `44/486 = 0.091`
- explorer와 reviewer pass는 concrete implementation finding이 없다고 보고했다. 남은 리스크는 `compare_Cheung` checked-in runtime override(`10/5/3`)를 기준으로 audit를 맞췄다는 점과, audit script가 private helper에 의존한다는 점이다.
