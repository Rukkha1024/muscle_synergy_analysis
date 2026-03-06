# 이슈 001: 승인된 EMG 시너지 아키텍처 스캐폴드 계획 구현

**상태**: 진행 중
**생성일**: 2026-03-06

## 배경

저장소에는 `.agents/execplans/repo_architecture_scaffold_execplan_en.md` 승인본이 있지만,
실제로 실행 가능한 파이프라인, 도메인 패키지, 설정 파일, 테스트, 검증 흐름은 아직 없습니다.
이 작업은 `configs/`, `src/`, `scripts/`, `outputs/`, `analysis/` 구조에 맞춰 그 승인 계획을 구현합니다.

## 완료 기준

- [ ] 저장소에 실행 가능한 `main.py` 오케스트레이터와 `src/emg_pipeline/`, `src/synergy_stats/`가 존재한다.
- [ ] 파이프라인이 fixture 입력으로 실행되어 subject 출력, 통합 CSV, `run_manifest.json`, `outputs/final.parquet`를 쓴다.
- [ ] 테스트가 trial slicing, NMF 동작, 군집 중복 정책, 출력 아티팩트 존재를 검증한다.
- [ ] curated MD5 비교가 stable 출력만 골라 reference baseline과 비교할 수 있다.
- [ ] living ExecPlan, README, 환경 문서가 구현된 실행 흐름을 반영한다.

## 작업 목록

- [x] 1. 최상위 디렉터리 구조를 `configs/`, `outputs/`, `archive/`로 정규화한다.
- [x] 2. 루트 오케스트레이터, 도메인 패키지, 번호가 있는 EMG 스크립트 래퍼를 추가한다.
- [ ] 3. 새 파이프라인용 fixture 입력과 pytest 범위를 추가한다.
- [ ] 4. fixture 실행과 curated MD5 검증을 수행한다.
- [ ] 5. 마크다운 living 문서를 갱신하고 한국어 커밋으로 마무리한다.

## 참고 사항

승인된 ExecPlan 자체가 구현 계획 역할을 하므로, 이 이슈는 새로운 계획을 만드는 대신 실행 진행을 추적합니다.
저장소 규칙상 이슈, ExecPlan, 테스트는 서로 어긋나지 않도록 계속 같이 갱신해야 합니다.
