# 이슈 006: EMG clustering audit workbook export

**상태**: 완료
**생성일**: 2026-03-14

## 배경

EMG synergy pipeline은 이미 clustering 해가 왜 채택되었는지 설명하는 데 필요한 핵심 근거를 계산하고 있다. 여기에는 gap statistic 결과, gap이 먼저 고른 `K`, 그리고 후보 `K` 전반의 duplicate-trial burden이 포함된다. 하지만 현재 이 진단 정보는 CSV의 JSON 필드에 묶여 있어 Excel에서 바로 읽기에는 불편하다.

사용자는 이 clustering 근거를 각 run output 디렉터리에 저장되는 단일 Excel workbook으로 보고 싶어 한다. 이 workbook은 선택 근거와 duplicate 상세를 Excel에서 읽기 쉬운 형식으로 보여줘야 하며, 표를 어떻게 읽는지와 간단한 예시도 workbook 안에 함께 포함해야 한다.

## 완료 기준

- [x] 각 pipeline run이 run output 디렉터리 아래에 `clustering_audit.xlsx`를 기록한다.
- [x] workbook이 `summary`, `duplicates`, `table_guide` 시트를 포함한다.
- [x] `summary` 시트가 항상 표 위에 읽는 법과 worked example을 포함한다.
- [x] workbook이 duplicate trial summary와 duplicate cluster detail을 모두 export한다.
- [x] 기존 stable CSV output은 코드 수준 호환성을 유지하며, 이번 턴에서는 사용자의 요청에 따라 full pipeline rerun 없이 테스트 중심 검증만 수행했다.
- [x] Excel workflow skill이 audit workbook의 summary 시트에 읽는 법과 예시를 요구하도록 갱신된다.

## 작업 목록

- [x] 1. candidate `K`별 workbook-ready duplicate evidence를 보존하도록 clustering diagnostics를 확장한다.
- [x] 2. clustering audit workbook용 export 및 validation helper를 추가한다.
- [x] 3. artifact export 단계에 workbook 생성을 연결한다.
- [x] 4. workbook 내용과 duplicate evidence serialization을 검증하는 테스트를 추가하거나 갱신한다.
- [x] 5. 새 workbook 패턴에 맞게 README와 Excel skill 가이드를 갱신한다.
- [x] 6. validation, reviewer check, 한국어 5줄 커밋 메시지까지 완료한다.

## 참고 사항

- 주요 구현 파일:
  - `src/synergy_stats/clustering.py`
  - `src/synergy_stats/artifacts.py`
  - `src/synergy_stats/excel_audit.py`
- 주요 테스트:
  - `tests/test_synergy_stats/test_clustering_contract.py`
  - `tests/test_synergy_stats/test_excel_audit.py`
- workbook 구조:
  - `summary`
  - `duplicates`
  - `table_guide`
- 환경 메모:
  - 이번 턴에서는 active environment에서 desktop Excel automation이 불가능해 `openpyxl` fallback으로 workbook을 구현했고, Excel UI visual QA는 생략 사실을 함께 기록했다.
- 아래 명령으로 검증을 완료했다.
  - `conda run --no-capture-output -n module python -m py_compile src/synergy_stats/clustering.py src/synergy_stats/artifacts.py src/synergy_stats/excel_audit.py tests/test_synergy_stats/test_clustering_contract.py tests/test_synergy_stats/test_excel_audit.py`
  - `conda run --no-capture-output -n module python -m pytest tests/test_synergy_stats/test_clustering_contract.py tests/test_synergy_stats/test_excel_audit.py -q`
- 남은 제한 사항:
  - 사용자가 test-only validation을 요청해 이번 턴에서는 full pipeline rerun과 curated MD5 비교를 의도적으로 생략했다.
