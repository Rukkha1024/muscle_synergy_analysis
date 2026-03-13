# 이슈 003: professor 비교 cluster figure를 pipeline figure style에 맞추기

**상태**: 완료
**생성일**: 2026-03-13

## 배경

`analysis/compare_professor/compare_step_nonstep_professor_logic.py`는 현재 cluster centroid figure를 자체 1열 bar chart로 그려서, 저장소의 pipeline 산출물 style과 맞지 않습니다. 사용자는 professor 비교 figure도 pipeline과 같은 시각 스타일을 사용해 결과를 바로 비교할 수 있기를 원했습니다.

## 완료 기준

- [x] professor 비교 스크립트가 centroid PNG 출력에 pipeline cluster figure style을 재사용한다.
- [x] professor centroid figure의 출력 파일명은 그대로 유지된다.
- [x] 스크립트를 다시 실행하고 변경된 PNG 출력이 이전 reference 파일과 비교 검증된다.
- [x] 공용 figure 테스트와 review pass가 unresolved finding 없이 끝난다.

## 작업 목록

- [x] 1. 자체 centroid plotting 경로를 공용 pipeline renderer로 교체한다.
- [x] 2. pipeline style `H` 패널을 만들 수 있도록 NMF activation timecourse를 보존한다.
- [x] 3. professor 비교 산출물을 재생성하고 이전 artifact와의 MD5 차이를 기록한다.
- [x] 4. targeted validation과 explorer/reviewer 확인을 마친 뒤 마무리한다.

## 참고 사항

- 수정 범위는 `analysis/compare_professor/compare_step_nonstep_professor_logic.py`의 figure 생성 로직으로 제한한다.
- 재실행 결과 `professor_trial_summary.csv`와 `summary.json`은 그대로 유지되었고, 두 centroid PNG만 변경되었다.
- 검증은 `conda run -n module python ...compare_step_nonstep_professor_logic.py --overwrite`, `conda run -n module python -m py_compile ...`, `conda run -n module python -m pytest tests/test_synergy_stats/test_figures_headless_backend.py`로 완료했다.
- activation scaling fix 이후 reviewer 재검토에서 figure-style 변경에 남은 concrete bug는 없다고 확인했다.
