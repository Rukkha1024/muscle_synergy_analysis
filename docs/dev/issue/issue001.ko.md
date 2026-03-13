# 이슈 001: compare_professor에 교수님식 KMeans 재시도 선택 로직 복원

**상태**: 완료
**생성일**: 2026-03-13

## 배경

`analysis/compare_professor/compare_step_nonstep_professor_logic.py`는 현재 각 `K`마다 `KMeans`를 1회만 실행하고, 중복 없는 해를 찾지 못하면 Hungarian 보정으로 넘어갑니다. 반면 교수님 기준 코드는 초기값이 다른 여러 후보 해를 반복 생성하고, 그중 중복 없는 결과를 저장한 뒤 선택합니다. 이번 작업은 현재의 fallback은 마지막 안전장치로만 남기면서, 비교 스크립트가 교수님식 재시도-선택 흐름에 더 가깝게 동작하도록 복원하는 것입니다.

## 완료 기준

- [x] `compare_step_nonstep_professor_logic.py`가 각 `K`를 1회만 시험하지 않고 여러 seed로 재시도한다.
- [x] 재시도 결과 중 중복 없는 후보 해를 선택하고, 그 선택 정보를 출력 metadata에 남긴다.
- [x] 재시도 기반 선택이 실패할 때만 최종 fallback 경로를 사용한다.
- [x] 분석 스크립트를 실제로 실행하고, 반복 실행 간 MD5 체크섬 검증을 완료한다.

## 작업 목록

- [x] 1. 클러스터링 함수를 수정해 재시도 후보를 수집하고 최종 해를 선택한다.
- [x] 2. 재시도 설정과 선택 결과를 CLI/summary metadata에 반영한다.
- [x] 3. compare_professor 문서를 현재 동작에 맞게 갱신한다.
- [x] 4. 분석 스크립트를 재실행하고 반복 실행 산출물의 체크섬을 비교한다.

## 참고 사항

- `random_state = seed + retry`, `n_init = 1` 조합으로 교수님식 재시도 검색 흐름을 복원했다.
- 교수님 원본의 후속 ICC 기반 선택 단계는 이번 비교 스크립트로 옮기지 않았으므로, 최종 선택 기준은 `mode K + lowest inertia`로 두었다.
- 정리 전 반복 실행 간 MD5 체크섬 일치를 확인했고, 현재는 `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun`만 남겨 두었다.
- 이전 fallback 중심 결과와 새 결과의 체크섬이 달라져 로직 변경이 실제 산출물에 반영되었음을 확인했다.
