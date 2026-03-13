# 이슈 002: Cheung 2021 방식 step vs nonstep 시너지 비교 분석 구현

**상태**: 진행 중
**생성일**: 2026-03-13

## 배경

`analysis/compare_Cheung,2021/` 폴더에는 현재 참고 논문 PDF와 ExecPlan만 있고, 실제로 실행 가능한 분석 워크플로는 아직 없습니다. 이번 작업의 목표는 현재 섭동 데이터셋에서 Cheung식 NMF 선택 규칙으로 trial 단위 근육 시너지를 다시 추출하고, step과 nonstep의 구조를 비교하며, academic style figure와 prior-study 비교 보고서를 생성하는 self-contained 분석을 만드는 것입니다. 이 과정에서 운영 파이프라인 산출물은 수정하지 않습니다.

## 완료 기준

- [x] `analysis/compare_Cheung,2021/` 아래에 단일 진입 스크립트가 존재하고 `--dry-run`을 지원한다.
- [x] `outputs/runs/default_run`의 trial metadata와 설정 파일에 연결된 normalized EMG parquet를 사용해 선택 trial을 다시 구성한다.
- [x] 논문식 비교 지표, pipeline style cluster figure, 완성된 `report.md`를 생성한다.
- [x] 현재 환경에서 dry-run과 full run을 실행하고 결과 검증을 완료한다.

## 작업 목록

- [x] 1. 실제 폴더, 입력, 구현 결정에 맞게 ExecPlan을 갱신한다.
- [x] 2. NMF, clustering, matching, cross-fit, 구조 지표를 포함한 분석 스크립트를 구현한다.
- [x] 3. pipeline style cluster figure를 만들고 prior-study 비교 보고서를 작성한다.
- [x] 4. dry-run과 full validation을 실행하고 체크섬과 리뷰 결과를 기록한다.

## 참고 사항

- `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`를 단일 진입점으로 구현했다.
- baseline truth는 `outputs/runs/default_run/all_trial_window_metadata.csv`에 있고, 실제 재분석용 time-series 입력은 설정 파일에 연결된 normalized EMG parquet에서 다시 읽어야 함을 확인했다.
- `module` conda 환경에서 `--dry-run`, `--prototype`, full run, 재실행 검증까지 완료했다.
- cluster figure는 `src/synergy_stats/figures.py`의 파이프라인 렌더러를 재사용해 `default_run`과 같은 스타일로 맞췄다.
- 반복 full run 후 `report.md`와 유지된 PNG 산출물의 MD5 체크섬이 안정적으로 유지됨을 확인했다.
