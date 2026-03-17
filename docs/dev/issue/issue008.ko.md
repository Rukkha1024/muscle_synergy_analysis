# 이슈 008: concatenated source-trial window provenance manifest 보강

**상태**: 완료
**생성일**: 2026-03-18

## 배경

현재 `concatenated` mode는 이미 `analysis_unit_id`, `source_trial_nums_csv`, `analysis_source_trial_count` 같은 analysis-unit provenance를 보존한다. 하지만 export되는 `all_trial_window_metadata.csv`는 이름상으로는 진짜 trial-window provenance처럼 보이는데, 실제 `concatenated` mode에서는 synthetic `trial_num=concat_step|concat_nonstep`를 가진 analysis-unit 수준 요약 row에 가깝다.

이 점이 사용자 입장에서는 의미 불일치다. 어떤 source trial들이 쓰였는지는 대략 볼 수 있지만, source trial별 analysis-window provenance를 별도 CSV에서 바로 확인할 수는 없다. 승인된 revision plan은 기존 `all_trial_window_metadata.csv` 계약은 그대로 유지하면서, `all_concatenated_source_trial_windows.csv`라는 additive artifact를 추가해 한 row가 한 source-trial window를 뜻하도록 만든다.

## 완료 기준

- [x] `src/synergy_stats/concatenated.py`가 concatenated analysis-unit metadata 안에 `source_trial_details`를 보존한다.
- [x] exporter가 `outputs/runs/<run_id>/concatenated/` 아래에 `all_concatenated_source_trial_windows.csv`를 쓴다.
- [x] `both` run에서는 `outputs/runs/<run_id>/all_concatenated_source_trial_windows.csv`도 생성되고, 이 파일에는 concatenated row만 들어간다.
- [x] `trialwise` only run에서는 `trialwise/all_concatenated_source_trial_windows.csv`가 생성되지 않는다.
- [x] 새 CSV는 source trial당 1행을 가지며 `analysis_unit_id`, `trial_num`, `source_trial_num`, `analysis_window_*` provenance 컬럼을 포함한다.
- [x] 기존 `all_trial_window_metadata.csv` 동작은 유지된다.
- [x] 마무리 전 `module` conda 환경에서 targeted test, smoke run, reviewer 스타일 diff 점검을 수행한다.

## 작업 목록

- [x] 1. concatenated analysis-unit metadata에 source-trial detail payload를 추가한다.
- [x] 2. 이 payload를 export 가능한 source-trial manifest row로 펼친다.
- [x] 3. concatenated mode output과 root combined output에 새 CSV를 쓴다.
- [x] 4. payload shape와 artifact/file-contract 동작을 검증하는 테스트를 갱신한다.
- [x] 5. 사용자가 기존 파일과 새 concatenated provenance 파일의 차이를 이해할 수 있도록 `README.md`를 수정한다.
- [x] 6. `module` 환경에서 검증을 수행하고 결과를 기록한다.
- [x] 7. `issue008`을 참조하는 한국어 5줄 커밋 메시지로 커밋한다.

## 참고 사항

- 기준 계획 문서: `.agents/execplans/Concatenated Source-Trial Window Provenance Revision ExecPlan.md`
- 범위 경계: additive pipeline change만 수행한다. `all_trial_window_metadata.csv` 의미는 바꾸지 않고 새 CSV를 추가한다.
- 목표 산출물 이름:
  - `outputs/runs/<run_id>/concatenated/all_concatenated_source_trial_windows.csv`
  - `outputs/runs/<run_id>/all_concatenated_source_trial_windows.csv`
- 기대 row 의미:
  - 한 row = 한 source trial window
  - `trial_num` = synthetic parent analysis unit key
  - `source_trial_num` = 실제 원본 trial 번호
- 검증 요약:
  - `conda run -n module python -m pytest tests/test_synergy_stats/test_concatenated_mode.py -q`
  - `conda run -n module python -m pytest tests/test_synergy_stats/test_artifacts.py -q`
  - `conda run -n module python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q`
  - `conda run -n module python main.py --config /tmp/codex_provenance_validation/global_config.yaml --mode concatenated --out /tmp/codex_provenance_validation/concat_run --overwrite`
  - `conda run -n module python main.py --config /tmp/codex_provenance_validation/global_config.yaml --mode both --out /tmp/codex_provenance_validation/both_run1 --overwrite`
  - `conda run -n module python main.py --config /tmp/codex_provenance_validation/global_config.yaml --mode both --out /tmp/codex_provenance_validation/both_run2 --overwrite`
- 검증 관찰:
  - 새 source-trial provenance CSV의 MD5는 두 rerun에서 완전히 동일했다.
  - curated MD5 스크립트는 `all_clustering_metadata.csv`의 `gap_sd_by_k_json` 안 미세한 부동소수점 차이 때문에 rerun diff를 보고했지만, 새 provenance 파일과는 무관했다.
