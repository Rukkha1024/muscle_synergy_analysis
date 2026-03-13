# 이슈 005: compare_Cheung 전용 duplicate assignment 감사

**상태**: 완료
**생성일**: 2026-03-13

## 배경

사용자는 source of truth를 `analysis/compare_Cheung,2021/`로 한정했다. 이 논문형 경로는 trial-level NMF synergy vector에 ordinary pooled k-means와 gap statistic을 적용하므로, 같은 trial 내부 duplicate cluster assignment가 실제 문제인지 판단할 때 직접 봐야 하는 코드 경로다.

production pipeline은 이미 자체 forced reassignment로 uniqueness를 강제하므로, 이번 이슈는 더 이상 production 동작 감시가 아니다. 대신 작업 전체가 `analysis/` 아래의 독립 분석으로 존재해야 하며, `compare_Cheung` 경로를 다시 실행해 duplicate burden을 측정하고, 그 경로 안에는 within-trial uniqueness enforcement가 없다는 점을 문서화하고, README·검증 스크립트·report·local artifact를 남겨야 한다.

## 완료 기준

- [x] 감사 작업이 `analysis/duplicate_assignment_audit/` 아래 독립 analysis workflow로 존재한다.
- [x] source of truth가 `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`로 명확히 고정된다.
- [x] audit report가 compare_Cheung-only 근거로 네 가지 사용자 질문에 답한다.
- [x] 재현 artifact가 `analysis/duplicate_assignment_audit/results/` 아래에 저장된다.
- [x] 실행 방법과 검증 방법을 설명하는 `README.md`가 존재한다.
- [x] 분석 코드 옆에 Python 검증 스크립트가 남아 있다.
- [x] validation, explorer, reviewer pass를 마치고 종료한다.

## 작업 목록

- [x] 1. “paper-like plus production 비교”에서 “compare_Cheung-only duplicate audit”로 범위를 좁힌다.
- [x] 2. `analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`에서 production reassignment 분석을 제거한다.
- [x] 3. compare_Cheung 경로를 기준으로 `analysis/duplicate_assignment_audit/report.md`와 local `results/` artifact를 생성한다.
- [x] 4. `analysis/duplicate_assignment_audit/README.md`와 `analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`를 추가한다.
- [x] 5. 이전 넓은 범위에서 생긴 top-level audit output과 production 전용 validation 흔적을 정리한다.
- [x] 6. 분석 실행, 검증 실행, explorer/reviewer pass 완료 후 한국어 5줄 이상 커밋 메시지로 커밋한다.

## 참고 사항

- 메인 entrypoint: `analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`
- 검증 entrypoint: `analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`
- 메인 보고서: `analysis/duplicate_assignment_audit/report.md`
- artifact 디렉터리: `analysis/duplicate_assignment_audit/results/`
- 핵심 측정 수치:
  - raw duplicate unit rate `28/125 = 0.224`
  - raw excess duplicate ratio `30/503 = 0.060`
  - raw duplicate pair rate `30/852 = 0.035`
  - selected K `global_step=11`, `global_nonstep=6`
  - compare_Cheung 코드 경로에는 forced reassignment 단계가 없다
- 검증은 아래 명령으로 완료했다.
  - `conda run --no-capture-output -n module python -m py_compile analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`
  - `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py --dry-run`
  - `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`
  - `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`
- 남은 리스크:
  - duplicate 수치가 현재 체크인된 compare_Cheung report와 맞도록 runtime override `10/5/3`를 의도적으로 사용했고, script 기본값 `1000/500/100`으로 다시 돌리면 결과가 달라질 수 있다.
