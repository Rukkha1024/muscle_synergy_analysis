# Rebuild paired-only clustering after a pipeline-side paired filter / main pipeline paired filter 이후 paired-only clustering 재구성

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

이 문서는 저장소 루트의 `.agents/PLANS.md`를 따르는 bilingual ExecPlan이다. 구현자는 이 문서 하나만 읽고도 왜 이 변경이 필요한지, 어떤 파일을 수정해야 하는지, 어떤 명령을 실행해야 하는지, 무엇을 관찰하면 성공인지 이해할 수 있어야 한다. 구현은 사용자가 이 계획을 승인한 뒤에만 시작하며, 구현 중 새로운 사실이 확인되면 living sections를 즉시 갱신한다.

This document is a bilingual ExecPlan maintained in accordance with `.agents/PLANS.md` at the repository root. A novice implementer must be able to read only this file and understand why the change matters, which files must be edited, what commands to run, and what observations prove success. Implementation begins only after user approval, and the living sections must be updated whenever new facts are discovered.

## Purpose / 목적

한국어: 이 변경이 끝나면 사용자는 analysis 단계에서 임의로 raw filtering을 다시 흉내 내지 않아도 된다. 대신 main pipeline이 `subject+velocity` 기준 paired filter를 source of truth로 적용해 paired-only `final_concatenated.parquet`를 만들고, 그 다음 `analysis/first_zero_duplicate_k_rerun/` 작업공간이 그 pipeline 산출물만 읽어 `first_zero_duplicate` reclustering, paired exact McNemar 통계, reviewer-facing Excel workbook 생성을 수행하게 된다.

English: After this change, the user no longer has to re-simulate raw filtering inside the analysis workspace. Instead, the main pipeline becomes the source of truth for the `subject+velocity` paired filter, producing a paired-only `final_concatenated.parquet`, and then the `analysis/first_zero_duplicate_k_rerun/` workspace consumes only that pipeline output to run `first_zero_duplicate` reclustering, paired exact McNemar statistics, and a reviewer-facing Excel workbook.

한국어: 이 작업의 핵심은 책임 분리다. Filtering은 production pipeline 변경이다. Reclustering, paired cluster statistics, 그리고 새 Excel workbook 생성은 `analysis/first_zero_duplicate_k_rerun/` 내부에서만 한다. 즉 analysis 코드는 raw event/meta selection을 다시 계산하면 안 되고, pipeline이 이미 확정한 paired-only final parquet를 읽어야 한다.

English: The core of this work is responsibility separation. Filtering is a production pipeline change. Reclustering, paired cluster statistics, and the new Excel workbook are performed only inside `analysis/first_zero_duplicate_k_rerun/`. The analysis code must not recompute raw event/meta selection; it must read the paired-only final parquet that the pipeline has already finalized.

## Progress / 진행 상황

- [x] (2026-03-22T00:00Z) 한국어: pairing 기준을 `subject+velocity`로 고정했다. English: Fixed the pairing key to `subject+velocity`.
- [x] (2026-03-22T00:10Z) 한국어: reclustering 규칙을 `concatenated + first_zero_duplicate`로 고정했다. English: Fixed the reclustering rule to `concatenated + first_zero_duplicate`.
- [x] (2026-03-22T00:15Z) 한국어: paired 주통계를 exact McNemar test로 고정했다. English: Fixed the paired primary statistical test to the exact McNemar test.
- [x] (2026-03-22T00:20Z) 한국어: 새 paired statistics workbook은 `analysis/first_zero_duplicate_k_rerun/` 내부에서만 생성하기로 고정했다. English: Locked the new paired statistics workbook to be generated only inside `analysis/first_zero_duplicate_k_rerun/`.
- [x] (2026-03-22T00:25Z) 한국어: standalone ExecPlan 초안을 작성했다. English: Authored the first standalone ExecPlan draft.
- [x] (2026-03-22T01:30Z) 한국어: 사용자 요구에 맞춰 아키텍처 경계를 다시 잠갔다. Filtering은 main pipeline 수정이고, 통계분석 및 Excel 생성은 analysis 폴더 내부에서만 수행한다. English: Re-locked the architecture boundary to match the user requirement. Filtering belongs to the main pipeline, while statistics and Excel generation happen only inside the analysis folder.
- [ ] 한국어: `src/emg_pipeline/io.py`에서 기존 selection semantics 뒤에 paired gate를 추가한다. English: Add the paired gate after the existing selection semantics in `src/emg_pipeline/io.py`.
- [ ] 한국어: isolated pipeline rerun으로 paired-only final parquet를 생성하고 paired key count를 검증한다. English: Produce a paired-only final parquet through an isolated pipeline rerun and verify the paired key count.
- [ ] 한국어: `analysis/first_zero_duplicate_k_rerun/` 내부에 paired reclustering + paired statistics entrypoint를 추가한다. English: Add a paired reclustering plus paired statistics entrypoint inside `analysis/first_zero_duplicate_k_rerun/`.
- [ ] 한국어: paired manifests, paired stats CSV, paired workbook, summary.json 확장을 구현한다. English: Implement the paired manifests, paired stats CSVs, paired workbook, and the expanded `summary.json`.
- [ ] 한국어: pipeline test, analysis test, reproducibility checksum, workbook validation을 완료한다. English: Finish the pipeline test, analysis test, reproducibility checksum, and workbook validation.

## Surprises & Discoveries / 예상 밖 발견 사항

- Observation:
  한국어: 현재 full-sample `default_run`의 concatenated analysis unit은 `45`개이며, trial figure inventory를 `subject+velocity` 단위로 다시 세면 `24`개 key 중 `21`개만 `step`과 `nonstep`을 모두 가진다.
  English: The current full-sample `default_run` has `45` concatenated analysis units, and when the trial-figure inventory is reconstructed at the `subject+velocity` level, only `21` of `24` keys contain both `step` and `nonstep`.

  Evidence:
  한국어: `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/summary.json`에는 `trial_count = 45`가 기록되어 있고, 같은 파일의 `trial_figure_paths`를 `subject+velocity` 단위로 재집계하면 `paired_keys = 21`, `nonstep_only_keys = 3`이 나온다.
  English: `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/summary.json` records `trial_count = 45`, and regrouping its `trial_figure_paths` by `subject+velocity` yields `paired_keys = 21` and `nonstep_only_keys = 3`.

- Observation:
  한국어: pipeline의 canonical raw selection truth는 여전히 `src/emg_pipeline/io.py::_prepare_event_metadata()`다.
  English: The canonical raw selection truth in the pipeline remains `src/emg_pipeline/io.py::_prepare_event_metadata()`.

  Evidence:
  한국어: 이 함수는 `analysis_selected_group`, `analysis_is_step`, `analysis_is_nonstep`, surrogate window end, 그리고 `(subject, velocity)` 단위 major-step donor logic까지 확정한다.
  English: This function finalizes `analysis_selected_group`, `analysis_is_step`, `analysis_is_nonstep`, the surrogate window end, and the `(subject, velocity)`-level major-step donor logic.

- Observation:
  한국어: 현재 `analysis/first_zero_duplicate_k_rerun/` entrypoint는 이미 single parquet bundle을 읽어 no-gap rerun 요약과 artifact export를 만드는 구조를 갖고 있다.
  English: The current `analysis/first_zero_duplicate_k_rerun/` entrypoint already reads a single parquet bundle and produces no-gap rerun summaries plus exported artifacts.

  Evidence:
  한국어: `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`는 `--source-parquet`, `--out-dir`, `--overwrite` CLI를 제공하고 `summary.json`, `checksums.md5`, `final.parquet`, workbook, figure를 기록한다.
  English: `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py` exposes `--source-parquet`, `--out-dir`, and `--overwrite`, and writes `summary.json`, `checksums.md5`, `final.parquet`, workbooks, and figures.

- Observation:
  한국어: workbook validation contract는 이미 저장소에 구현되어 있다.
  English: The workbook validation contract is already implemented in the repository.

  Evidence:
  한국어: `src/synergy_stats/excel_results.py`는 save 후 reopen validation, `table_guide`, `[목적]`, `[핵심 컬럼]`, `[예시]` 검증 패턴을 제공한다.
  English: `src/synergy_stats/excel_results.py` already provides the save-then-reopen validation pattern, `table_guide`, and checks for `[목적]`, `[핵심 컬럼]`, and `[예시]`.

## Decision Log / 결정 로그

- Decision:
  한국어: filtering은 analysis helper가 아니라 main pipeline logic 수정으로 처리한다.
  English: Filtering is handled as a main pipeline logic change, not as an analysis helper.

  Rationale:
  한국어: 사용자가 filtering을 production source of truth로 옮기길 원했고, 저장소 아키텍처도 pipeline이 final parquet를 만들고 analysis가 그것을 소비하는 구조를 요구한다.
  English: The user wants filtering to live in the production source of truth, and the repository architecture requires the pipeline to produce the final parquet while analysis consumes it.

  Date/Author:
  2026-03-22 / GPT-5.4

- Decision:
  한국어: paired statistics와 새 Excel workbook 생성은 `analysis/first_zero_duplicate_k_rerun/` 내부에만 둔다.
  English: The paired statistics and the new Excel workbook generation live only inside `analysis/first_zero_duplicate_k_rerun/`.

  Rationale:
  한국어: 사용자가 통계분석 및 Excel 생성 범위를 analysis 폴더로 제한했고, 기존 pipeline workbook과 새 reviewer-facing paired workbook을 섞지 않는 편이 더 안전하다.
  English: The user restricted statistics and Excel generation to the analysis folder, and it is safer not to mix the new reviewer-facing paired workbook with the existing pipeline workbooks.

  Date/Author:
  2026-03-22 / GPT-5.4

- Decision:
  한국어: 기존 `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`는 full-sample no-gap rerun 경로로 남기고, paired workflow는 같은 폴더 안의 새 entrypoint로 추가한다.
  English: Keep the existing `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py` as the full-sample no-gap rerun path, and add the paired workflow as a new entrypoint inside the same folder.

  Rationale:
  한국어: 이번 요구는 기존 질문을 완전히 대체하는 bug fix라기보다 새 paired workflow 추가에 가깝다. 기존 entrypoint를 그대로 두면 legacy interpretation과 새 paired interpretation을 분리할 수 있다.
  English: This request is closer to adding a new paired workflow than replacing the old question entirely. Preserving the existing entrypoint keeps the legacy interpretation separate from the new paired interpretation.

  Date/Author:
  2026-03-22 / GPT-5.4

- Decision:
  한국어: paired gate는 기존 selection과 donor-window 계산이 끝난 뒤 마지막에 적용한다.
  English: Apply the paired gate at the end, after the existing selection and donor-window calculations finish.

  Rationale:
  한국어: `_prepare_event_metadata()` 안의 현재 step/nonstep 판정과 surrogate donor logic을 먼저 유지해야 semantic drift 없이 “기존 selection 결과 위에 paired 조건을 추가”할 수 있다.
  English: The current step/nonstep classification and surrogate donor logic inside `_prepare_event_metadata()` must run first so the paired condition remains an additive gate on top of the existing selection result without semantic drift.

  Date/Author:
  2026-03-22 / GPT-5.4

- Decision:
  한국어: exact McNemar test에서 discordant pair가 0개인 cluster는 `mcnemar_p = 1.0`으로 기록하고 `mcnemar_note = "no_discordant_pairs"`를 남긴다.
  English: For exact McNemar tests where the discordant pair count is zero, record `mcnemar_p = 1.0` and `mcnemar_note = "no_discordant_pairs"`.

  Rationale:
  한국어: 이 규칙을 문서 안에서 잠가 두어야 구현자마다 `NaN`, blank, `1.0`으로 다르게 쓰는 일을 막을 수 있다.
  English: Locking this rule in the plan prevents implementers from diverging between `NaN`, blank, and `1.0`.

  Date/Author:
  2026-03-22 / GPT-5.4

## Outcomes & Retrospective / 결과 및 회고

한국어: 구현은 아직 시작하지 않았다. 하지만 이 계획은 이전 초안과 달리 pipeline filtering과 analysis statistics의 책임 경계를 명시적으로 분리한다. 승인 후 implementer는 먼저 isolated pipeline rerun으로 paired-only final parquet를 만들고, 그 다음 analysis 폴더의 새 entrypoint로 reclustering, paired manifests, exact McNemar 통계, reviewer-facing workbook을 end-to-end로 생성해야 한다.

English: Implementation has not started yet. Unlike the earlier draft, this plan now explicitly separates pipeline filtering from analysis statistics. After approval, the implementer must first produce a paired-only final parquet through an isolated pipeline rerun and then use a new analysis-folder entrypoint to generate the reclustering, paired manifests, exact McNemar statistics, and reviewer-facing workbook end to end.

## Context and Orientation / 현재 맥락과 구조 설명

한국어: 이 저장소에서 pipeline은 `main.py`가 순서대로 `scripts/emg/01_load_emg_table.py`부터 `05_export_artifacts.py`까지 실행해 `outputs/` 아래 최종 산출물을 만든다. analysis 폴더는 그 최종 산출물을 읽어 별도의 질문을 탐색하는 공간이다. 이번 작업에서 filtering을 analysis로 끌어오면 이 경계가 깨지므로, paired filter는 반드시 pipeline에서 확정해야 한다.

English: In this repository, the pipeline runs through `main.py`, which executes `scripts/emg/01_load_emg_table.py` through `05_export_artifacts.py` in order and writes final outputs under `outputs/`. The analysis folder is a workspace for reading those final outputs and exploring separate questions. Pulling filtering back into analysis would break that boundary, so the paired filter must be finalized in the pipeline.

한국어: 이번 구현에서 “paired key”는 `(subject, velocity)`를 뜻한다. 어떤 paired key가 eligible하다는 뜻은 pipeline의 기존 selection semantics가 끝난 뒤 `analysis_selected_group=True`인 trial 중에 `step`이 하나 이상 있고 `nonstep`도 하나 이상 있다는 뜻이다. “paired-only final parquet”는 이런 eligible key에서 나온 trial만 반영한 pipeline 최종 bundle을 뜻한다. “cluster presence”는 analysis rerun 결과에서 어떤 paired key의 `concat_step` 또는 `concat_nonstep` analysis unit이 특정 cluster label을 한 번 이상 포함하는지를 뜻한다.

English: In this implementation, a “paired key” means `(subject, velocity)`. A paired key is eligible if, after the pipeline’s existing selection semantics finish, the trials with `analysis_selected_group=True` include at least one `step` and at least one `nonstep`. A “paired-only final parquet” is the pipeline’s final bundle containing only trials from those eligible keys. “Cluster presence” means whether the `concat_step` or `concat_nonstep` analysis unit for a paired key contains at least one instance of a given cluster label in the analysis rerun result.

한국어: 직접 수정해야 하는 핵심 파일은 다섯 개다. `src/emg_pipeline/io.py`는 canonical event preparation과 final selection flag를 만든다. `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`는 기존 full-sample no-gap rerun reference다. 새 workflow entrypoint는 `analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py`로 추가한다. `analysis/first_zero_duplicate_k_rerun/README.md`는 사용자 실행 경로를 설명하도록 갱신한다. 테스트는 `tests/test_emg_pipeline/test_event_preparation_contract.py`와 새 `tests/test_analysis/test_paired_refilter_reclustering.py`에 둔다.

English: Five files are central to this work. `src/emg_pipeline/io.py` builds the canonical event preparation and final selection flag. `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py` is the existing full-sample no-gap rerun reference. The new workflow entrypoint is added as `analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py`. `analysis/first_zero_duplicate_k_rerun/README.md` must be updated to explain the user-facing run path. Tests belong in `tests/test_emg_pipeline/test_event_preparation_contract.py` and a new `tests/test_analysis/test_paired_refilter_reclustering.py`.

## Plan of Work / 작업 계획

### Milestone 1 / 마일스톤 1 — Add the paired gate inside the main pipeline

한국어: 첫 번째 마일스톤의 결과는 raw filtering source of truth가 pipeline 안에서 paired-only로 바뀌는 것이다. 구현자는 `src/emg_pipeline/io.py::_prepare_event_metadata()`의 현재 selection semantics를 유지한 채, 마지막 단계에 paired gate를 추가한다. 구체적으로는 먼저 기존 `analysis_selected_group` 결과를 `analysis_selected_group_prepaired`로 보존하고, 그 다음 `(subject, velocity)`별로 selected step 존재 여부와 selected nonstep 존재 여부를 집계해 `analysis_is_paired_key`, `analysis_pair_status`, `analysis_pair_key` 같은 audit column을 만든다. 마지막에 최종 `analysis_selected_group`는 “기존 selection 통과”이면서 “paired key eligible”인 경우에만 true가 되도록 덮어쓴다.

English: The first milestone ends with the raw-filtering source of truth becoming paired-only inside the pipeline. The implementer keeps the current selection semantics in `src/emg_pipeline/io.py::_prepare_event_metadata()` intact and adds the paired gate at the final stage. Concretely, preserve the current `analysis_selected_group` result as `analysis_selected_group_prepaired`, then aggregate selected-step presence and selected-nonstep presence per `(subject, velocity)` to build audit columns such as `analysis_is_paired_key`, `analysis_pair_status`, and `analysis_pair_key`. Finally, overwrite the final `analysis_selected_group` so it is true only when both the original selection passed and the paired key is eligible.

한국어: 이 단계에서 중요한 점은 donor-window 계산이나 step/nonstep 판정을 다시 설계하지 않는 것이다. paired gate는 기존 selection semantics 위에 덧붙는 additive rule이어야 한다. 현재 입력이 변하지 않았다면 isolated validation run의 concatenated output은 `21` paired key와 `42` analysis unit을 가져야 한다. 기존 full-sample `45` unit 중 `3` nonpaired key에서 온 `concat_nonstep` unit만 빠지는 구조여야 한다.

English: The important rule here is not to redesign donor-window logic or step/nonstep classification. The paired gate must remain an additive rule on top of the existing selection semantics. If the current inputs remain unchanged, the isolated validation run’s concatenated output should contain `21` paired keys and `42` analysis units. Relative to the existing full-sample `45` units, only the `concat_nonstep` units from the `3` nonpaired keys should disappear.

### Milestone 2 / 마일스톤 2 — Add a dedicated paired analysis entrypoint

한국어: 두 번째 마일스톤의 결과는 `analysis/first_zero_duplicate_k_rerun/`가 pipeline이 이미 paired-only로 만든 final parquet만 읽어 새 질문을 풀 수 있게 되는 것이다. 구현자는 기존 `analyze_first_zero_duplicate_k_rerun.py`를 full-sample reference로 남기고, 같은 폴더에 `analyze_paired_refilter_reclustering.py`를 추가한다. 이 새 script는 raw event/meta를 읽지 않는다. 오직 `--source-parquet`로 받은 pipeline final bundle을 읽고, paired-only concatenated unit을 다시 스캔해 `first_zero_duplicate` reclustering을 수행한다.

English: The second milestone ends with `analysis/first_zero_duplicate_k_rerun/` being able to answer the new question by reading only the final parquet that the pipeline has already made paired-only. The implementer keeps `analyze_first_zero_duplicate_k_rerun.py` as the full-sample reference and adds `analyze_paired_refilter_reclustering.py` in the same folder. This new script must not read raw event/meta inputs. It reads only the pipeline final bundle supplied by `--source-parquet`, rescans the paired-only concatenated units, and performs the `first_zero_duplicate` reclustering.

한국어: 이 script는 기존 rerun artifact를 유지하면서 paired workflow에 필요한 새 산출물을 추가로 기록해야 한다. 최소 산출물은 `paired_subset_manifest.csv`, `excluded_nonpaired_manifest.csv`, `paired_cluster_stats.csv`, `paired_cluster_detail.csv`, `paired_cluster_statistics.xlsx`, 확장된 `summary.json`, 그리고 no-gap rerun의 `final.parquet`/`final_concatenated.parquet`다. 새 `summary.json`에는 반드시 `paired_key_n`, `excluded_pair_key_n`, `analysis_unit_n_postpaired`, `paired_subset_manifest_path`, `excluded_nonpaired_manifest_path`, `paired_cluster_stats_csv_path`, `paired_cluster_detail_csv_path`, `paired_cluster_statistics_workbook_path`, `k_selected_first_zero_duplicate`가 들어가야 한다.

English: This script must preserve the existing rerun artifacts while adding the new outputs required by the paired workflow. The minimum outputs are `paired_subset_manifest.csv`, `excluded_nonpaired_manifest.csv`, `paired_cluster_stats.csv`, `paired_cluster_detail.csv`, `paired_cluster_statistics.xlsx`, an expanded `summary.json`, and the no-gap rerun `final.parquet` plus `final_concatenated.parquet`. The new `summary.json` must include `paired_key_n`, `excluded_pair_key_n`, `analysis_unit_n_postpaired`, `paired_subset_manifest_path`, `excluded_nonpaired_manifest_path`, `paired_cluster_stats_csv_path`, `paired_cluster_detail_csv_path`, `paired_cluster_statistics_workbook_path`, and `k_selected_first_zero_duplicate`.

### Milestone 3 / 마일스톤 3 — Build paired exact-McNemar outputs inside the analysis folder

한국어: 세 번째 마일스톤의 결과는 paired key와 cluster의 관계를 reviewer가 바로 읽을 수 있는 CSV와 workbook으로 고정하는 것이다. `paired_cluster_detail.csv`는 “한 cluster x 한 paired key = 한 행” 구조를 가져야 한다. 필수 컬럼은 `cluster_id`, `subject`, `velocity`, `paired_key`, `step_present`, `nonstep_present`, `presence_label`이다. `presence_label`은 `both_present`, `step_only`, `nonstep_only`, `both_absent` 중 하나여야 한다. `both_absent`도 반드시 실제 행으로 남겨야 한다. 그래야 summary count와 detail count가 정확히 합쳐진다.

English: The third milestone ends with the paired key versus cluster relationship being fixed into reviewer-readable CSV and workbook outputs. `paired_cluster_detail.csv` must have exactly one row per “one cluster x one paired key”. Its required columns are `cluster_id`, `subject`, `velocity`, `paired_key`, `step_present`, `nonstep_present`, and `presence_label`. `presence_label` must be one of `both_present`, `step_only`, `nonstep_only`, or `both_absent`. The `both_absent` case must still be written as a real row so the summary counts reconcile exactly with the detail counts.

한국어: `paired_cluster_stats.csv`는 cluster별 요약 한 줄을 가져야 한다. 필수 컬럼은 `cluster_id`, `paired_key_n`, `step_present_n`, `nonstep_present_n`, `both_present_n`, `step_only_n`, `nonstep_only_n`, `both_absent_n`, `step_presence_rate`, `nonstep_presence_rate`, `presence_rate_diff_step_minus_nonstep`, `mcnemar_p`, `mcnemar_q_bh`, `mcnemar_note`, `interpretation_label`이다. exact McNemar는 discordant pair 집계 `step_only_n`과 `nonstep_only_n`로 계산한다. `step_only_n + nonstep_only_n == 0`이면 `mcnemar_p = 1.0`, `mcnemar_note = "no_discordant_pairs"`로 고정한다. 해석 라벨은 `q < 0.05`이면 `strategy_biased`, 그렇지 않고 absolute difference가 `<= 0.15`이면 `shared_candidate`, 나머지는 `uncertain_not_significant`다.

English: `paired_cluster_stats.csv` must contain one summary row per cluster. Its required columns are `cluster_id`, `paired_key_n`, `step_present_n`, `nonstep_present_n`, `both_present_n`, `step_only_n`, `nonstep_only_n`, `both_absent_n`, `step_presence_rate`, `nonstep_presence_rate`, `presence_rate_diff_step_minus_nonstep`, `mcnemar_p`, `mcnemar_q_bh`, `mcnemar_note`, and `interpretation_label`. The exact McNemar test is computed from the discordant counts `step_only_n` and `nonstep_only_n`. When `step_only_n + nonstep_only_n == 0`, lock `mcnemar_p = 1.0` and `mcnemar_note = "no_discordant_pairs"`. The interpretation label is `strategy_biased` when `q < 0.05`, `shared_candidate` when `q >= 0.05` and the absolute difference is `<= 0.15`, and `uncertain_not_significant` otherwise.

한국어: 새 workbook `paired_cluster_statistics.xlsx`는 `analysis/first_zero_duplicate_k_rerun/` 내부에서만 생성한다. 최소 시트는 `summary`, `cluster_stats`, `paired_detail`, `table_guide` 네 개다. 이 workbook의 생성과 검증은 기존 `src/synergy_stats/excel_results.py`의 패턴을 그대로 따른다. 즉 save 후 reopen validation을 수행하고, 모든 sheet에 `[목적]`, `[핵심 컬럼]`, `[예시]` block이 있으며, `table_guide`가 모든 table을 설명해야 한다. 다만 새 paired workbook builder 코드는 `src/synergy_stats/`가 아니라 analysis 폴더 안에 둔다.

English: The new workbook `paired_cluster_statistics.xlsx` is generated only inside `analysis/first_zero_duplicate_k_rerun/`. The minimum sheets are `summary`, `cluster_stats`, `paired_detail`, and `table_guide`. Its generation and validation must follow the existing pattern from `src/synergy_stats/excel_results.py`: save, reopen, validate; require `[목적]`, `[핵심 컬럼]`, and `[예시]` blocks on every important sheet; and require `table_guide` to document every table. However, the new paired workbook builder code lives in the analysis folder, not in `src/synergy_stats/`.

### Milestone 4 / 마일스톤 4 — Prove the workflow with tests, reruns, and documentation

한국어: 네 번째 마일스톤의 결과는 다음 implementer나 reviewer가 “이게 정말 pipeline change + analysis-only statistics인가”를 바로 검증할 수 있게 되는 것이다. `tests/test_emg_pipeline/test_event_preparation_contract.py`에는 paired gate가 기존 selection 뒤에 적용되는지 검증하는 test를 추가한다. `tests/test_analysis/test_paired_refilter_reclustering.py`에는 synthetic single-parquet fixture를 사용해 paired manifests, exact McNemar 요약, `mcnemar_p = 1.0` 경계 사례, workbook validation을 검증하는 test를 추가한다. `analysis/first_zero_duplicate_k_rerun/README.md`는 full-sample legacy rerun과 새 paired-refilter workflow를 모두 설명하도록 갱신한다.

English: The fourth milestone ends with enough proof for the next implementer or reviewer to verify immediately that this is truly a pipeline change plus analysis-only statistics. Add a test to `tests/test_emg_pipeline/test_event_preparation_contract.py` to prove the paired gate is applied after the existing selection. Add `tests/test_analysis/test_paired_refilter_reclustering.py` using a synthetic single-parquet fixture to validate the paired manifests, the exact McNemar summary, the `mcnemar_p = 1.0` edge case, and workbook validation. Update `analysis/first_zero_duplicate_k_rerun/README.md` so it explains both the legacy full-sample rerun and the new paired-refilter workflow.

## Concrete Steps / 구체적 실행 단계

한국어: 모든 명령은 repo root인 `/home/alice/workspace/26-03-synergy-analysis`에서 실행한다. 기본 Python 환경은 `conda run --no-capture-output -n cuda python`이다. 아래 흐름을 그대로 따라야 한다.

English: Run all commands from the repo root `/home/alice/workspace/26-03-synergy-analysis`. The default Python environment is `conda run --no-capture-output -n cuda python`. Follow the steps below exactly.

1. 한국어: 수정할 위치를 다시 연다.
   English: Reopen the edit locations.

      cd /home/alice/workspace/26-03-synergy-analysis
      nl -ba src/emg_pipeline/io.py | sed -n '240,420p'
      nl -ba main.py | sed -n '1,140p'
      nl -ba analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py | sed -n '1,220p'
      nl -ba analysis/first_zero_duplicate_k_rerun/README.md | sed -n '1,220p'
      nl -ba src/synergy_stats/excel_results.py | sed -n '475,620p'

2. 한국어: pipeline paired gate를 구현한다.
   English: Implement the pipeline paired gate.

      Files to edit:
        src/emg_pipeline/io.py
        tests/test_emg_pipeline/test_event_preparation_contract.py

      Required behavior:
        Preserve the existing selection result as `analysis_selected_group_prepaired`.
        Add `analysis_pair_key`, `analysis_is_paired_key`, and `analysis_pair_status`.
        Set final `analysis_selected_group` to false for selected rows whose `(subject, velocity)` key lacks either selected `step` or selected `nonstep`.

3. 한국어: 기존 output을 덮어쓰지 않는 isolated pipeline validation run을 수행한다.
   English: Run an isolated pipeline validation run without overwriting the existing outputs.

      conda run --no-capture-output -n cuda python \
        main.py \
        --config configs/global_config.yaml \
        --out outputs/paired_refilter_pipeline \
        --overwrite

4. 한국어: pipeline output이 정말 paired-only인지 검증한다.
   English: Verify that the pipeline output is truly paired-only.

      conda run --no-capture-output -n cuda python - <<'PY'
      import json
      import pandas as pd
      from src.synergy_stats.single_parquet import load_single_parquet_bundle

      bundle = load_single_parquet_bundle("outputs/paired_refilter_pipeline/final_concatenated.parquet")
      trial_windows = bundle["trial_windows"].copy()
      selected = trial_windows.loc[trial_windows["analysis_selected_group"] == True].copy()
      summary = (
          selected.groupby(["subject", "velocity"], sort=False)
          .agg(
              has_step=("analysis_is_step", "any"),
              has_nonstep=("analysis_is_nonstep", "any"),
          )
          .reset_index()
      )
      paired = summary.loc[summary["has_step"] & summary["has_nonstep"]]
      excluded = summary.loc[~(summary["has_step"] & summary["has_nonstep"])]
      print({"paired_key_n": int(len(paired)), "excluded_key_n": int(len(excluded)), "analysis_unit_n": int(len(selected))})
      PY

      Expected observation when current inputs are unchanged:
        `paired_key_n = 21`
        `excluded_key_n = 0` inside the selected set because the final gate already removed nonpaired keys
        `analysis_unit_n = 42`

5. 한국어: 새 paired analysis entrypoint와 test를 추가한다.
   English: Add the new paired analysis entrypoint and its test.

      Files to create or edit:
        analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py
        analysis/first_zero_duplicate_k_rerun/README.md
        tests/test_analysis/test_paired_refilter_reclustering.py

      Required CLI:
        `--source-parquet`
        `--config`
        `--out-dir`
        `--overwrite`

6. 한국어: paired analysis full run을 수행한다.
   English: Run the paired analysis full workflow.

      conda run --no-capture-output -n cuda python \
        analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py \
        --source-parquet outputs/paired_refilter_pipeline/final_concatenated.parquet \
        --config configs/global_config.yaml \
        --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run \
        --overwrite

7. 한국어: analysis output contract를 확인한다.
   English: Confirm the analysis output contract.

      Expected files:
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/summary.json
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/paired_subset_manifest.csv
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/excluded_nonpaired_manifest.csv
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/paired_cluster_stats.csv
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/paired_cluster_detail.csv
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/paired_cluster_statistics.xlsx
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/final.parquet
        analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run/final_concatenated.parquet

8. 한국어: tests를 실행한다.
   English: Run the tests.

      conda run --no-capture-output -n cuda pytest \
        tests/test_emg_pipeline/test_event_preparation_contract.py \
        tests/test_analysis/test_paired_refilter_reclustering.py

9. 한국어: reproducibility checksum을 만든다.
   English: Build the reproducibility checksums.

      Pipeline rerun A:
        conda run --no-capture-output -n cuda python main.py --config configs/global_config.yaml --out outputs/paired_refilter_pipeline_a --overwrite

      Pipeline rerun B:
        conda run --no-capture-output -n cuda python main.py --config configs/global_config.yaml --out outputs/paired_refilter_pipeline_b --overwrite

      Analysis rerun A:
        conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py --source-parquet outputs/paired_refilter_pipeline_a/final_concatenated.parquet --config configs/global_config.yaml --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run_a --overwrite

      Analysis rerun B:
        conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py --source-parquet outputs/paired_refilter_pipeline_b/final_concatenated.parquet --config configs/global_config.yaml --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run_b --overwrite

      Compare deterministic artifacts only:
        final.parquet
        final_concatenated.parquet
        paired_subset_manifest.csv
        excluded_nonpaired_manifest.csv
        paired_cluster_stats.csv
        paired_cluster_detail.csv
        summary.json
        k_scan.json
        PNG figures

      Do not require workbook MD5 equality because `.xlsx` metadata may vary across runs. Require workbook structural validation instead.

## Validation and Acceptance / 검증 및 완료 기준

한국어: 이 작업의 acceptance는 pipeline correctness, analysis correctness, workbook correctness 세 축으로 나뉜다. 첫째, pipeline correctness는 isolated pipeline run의 `final_concatenated.parquet`가 실제로 paired-only selection을 반영하는지로 정의한다. 현재 입력이 바뀌지 않았다면 selected `(subject, velocity)` key는 `21`개이고 concatenated analysis unit은 `42`개여야 한다. `trial_windows`의 final `analysis_selected_group=True` 집합에는 `step`만 있거나 `nonstep`만 있는 key가 남아 있으면 실패다.

English: Acceptance is divided into three axes: pipeline correctness, analysis correctness, and workbook correctness. First, pipeline correctness is defined by whether the isolated pipeline run’s `final_concatenated.parquet` truly reflects paired-only selection. If the current inputs are unchanged, the selected `(subject, velocity)` key count must be `21` and the concatenated analysis unit count must be `42`. It is a failure if any key remains in the final `analysis_selected_group=True` set with only `step` or only `nonstep`.

한국어: 둘째, analysis correctness는 새 entrypoint가 pipeline output만 읽어 paired rerun과 paired stats를 끝까지 생성하는지로 정의한다. `paired_subset_manifest.csv`에는 `21`개 paired key가 있어야 하고, `excluded_nonpaired_manifest.csv`에는 현재 입력 기준으로 기존 full-sample reference에서 탈락한 `3`개 key가 기록되어야 한다. `paired_cluster_detail.csv`는 “cluster x paired key” 완전 그리드를 가져야 하므로 각 cluster마다 정확히 `21`행이 있어야 한다. `paired_cluster_stats.csv`에는 `mcnemar_p`, `mcnemar_q_bh`, `mcnemar_note`, `interpretation_label`이 모두 존재해야 한다.

English: Second, analysis correctness is defined by the new entrypoint being able to read only the pipeline output and finish the paired rerun plus paired stats end to end. `paired_subset_manifest.csv` must contain `21` paired keys, and `excluded_nonpaired_manifest.csv` must record the `3` keys that disappeared relative to the current full-sample reference for the current inputs. `paired_cluster_detail.csv` must contain the complete “cluster x paired key” grid, so each cluster must have exactly `21` rows. `paired_cluster_stats.csv` must include `mcnemar_p`, `mcnemar_q_bh`, `mcnemar_note`, and `interpretation_label`.

한국어: 셋째, workbook correctness는 `paired_cluster_statistics.xlsx`를 save 후 reopen validation했을 때 sheet, table, guide block, `table_guide` row가 모두 존재하는지로 정의한다. `summary`, `cluster_stats`, `paired_detail`, `table_guide` 네 시트가 모두 있어야 한다. `cluster_stats`와 `paired_detail` table 안에 Excel error token이나 required blank cell이 있으면 실패다. `step_only_n + nonstep_only_n == 0`인 cluster는 `mcnemar_p = 1.0`과 `mcnemar_note = "no_discordant_pairs"`를 가져야 한다.

English: Third, workbook correctness is defined by whether `paired_cluster_statistics.xlsx` passes save-then-reopen validation with every required sheet, table, guide block, and `table_guide` row present. The workbook must contain `summary`, `cluster_stats`, `paired_detail`, and `table_guide`. Any Excel error token or required blank cell inside the `cluster_stats` or `paired_detail` tables is a failure. Any cluster with `step_only_n + nonstep_only_n == 0` must have `mcnemar_p = 1.0` and `mcnemar_note = "no_discordant_pairs"`.

## Idempotence and Recovery / 멱등성과 복구

한국어: 이 작업은 additive change로 설계한다. 기존 `outputs/`와 `analysis/first_zero_duplicate_k_rerun/artifacts/default_run`을 직접 덮어쓰지 말고, 검증은 `outputs/paired_refilter_pipeline*`과 `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run*` 같은 분리된 경로에서 수행한다. `--overwrite`를 사용해도 같은 validation path 내부에서만 정리되도록 한다. 사용자가 중간 산출물을 지워도 pipeline rerun과 analysis rerun을 다시 수행하면 같은 구조의 artifact를 복원할 수 있어야 한다.

English: This work is designed as an additive change. Do not overwrite the existing `outputs/` or `analysis/first_zero_duplicate_k_rerun/artifacts/default_run` directly; perform validation in isolated paths such as `outputs/paired_refilter_pipeline*` and `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_run*`. Even with `--overwrite`, cleanup must stay confined to the chosen validation path. If the user deletes intermediate outputs, rerunning the pipeline and then the analysis must restore the same artifact structure.

## Artifacts and Notes / 산출물과 비고

한국어: 구현이 끝나면 가장 중요한 사용자-facing artifact는 세 묶음이다. 첫째, pipeline이 만든 paired-only `final_concatenated.parquet`다. 둘째, analysis 폴더가 만든 `paired_subset_manifest.csv`, `excluded_nonpaired_manifest.csv`, `paired_cluster_stats.csv`, `paired_cluster_detail.csv`다. 셋째, reviewer-facing workbook `paired_cluster_statistics.xlsx`다. 기존 `analysis/first_zero_duplicate_k_rerun`의 no-gap rerun figure와 workbooks는 유지하되, 새 paired workbook은 이름과 경로로 명확히 구분해야 한다.

English: At the end of implementation, the most important user-facing artifacts come in three groups. First is the paired-only `final_concatenated.parquet` produced by the pipeline. Second are the analysis-folder CSVs: `paired_subset_manifest.csv`, `excluded_nonpaired_manifest.csv`, `paired_cluster_stats.csv`, and `paired_cluster_detail.csv`. Third is the reviewer-facing workbook `paired_cluster_statistics.xlsx`. Keep the existing no-gap rerun figures and workbooks from `analysis/first_zero_duplicate_k_rerun`, but distinguish the new paired workbook clearly by name and path.

한국어: `paired_cluster_stats.csv`의 예시 row shape는 다음 semantics를 가져야 한다.

English: An example row shape for `paired_cluster_stats.csv` must have the following semantics.

    cluster_id=10
    paired_key_n=21
    step_present_n=13
    nonstep_present_n=4
    both_present_n=3
    step_only_n=10
    nonstep_only_n=1
    both_absent_n=7
    step_presence_rate=0.6190
    nonstep_presence_rate=0.1905
    presence_rate_diff_step_minus_nonstep=0.4286
    mcnemar_p=0.0123
    mcnemar_q_bh=0.0345
    mcnemar_note=ok
    interpretation_label=strategy_biased

## Interfaces and Dependencies / 인터페이스와 의존성

한국어: pipeline 쪽 canonical function은 `src.emg_pipeline.io._prepare_event_metadata`다. analysis 쪽 parquet 입출력은 `src.synergy_stats.single_parquet.load_single_parquet_bundle`와 기존 rerun script의 artifact export pattern을 그대로 따른다. workbook validation contract는 `src.synergy_stats.excel_results.write_results_interpretation_workbook`와 `src.synergy_stats.excel_results.validate_results_interpretation_workbook`의 구조를 reference로 삼는다. paired workbook의 실제 builder 코드는 analysis 폴더 안에 두되, validation rule은 이 contract와 동일하게 맞춘다.

English: The canonical pipeline function is `src.emg_pipeline.io._prepare_event_metadata`. The analysis-side parquet I/O should follow `src.synergy_stats.single_parquet.load_single_parquet_bundle` and the artifact-export pattern of the existing rerun script. The workbook validation contract should use the structure of `src.synergy_stats.excel_results.write_results_interpretation_workbook` and `src.synergy_stats.excel_results.validate_results_interpretation_workbook` as the reference. The actual paired workbook builder code stays inside the analysis folder, but its validation rules must match that contract.

Revision Note / 수정 메모

한국어: 2026-03-22에 이 계획을 전면 재작성했다. 이유는 사용자 요구가 “filtering은 main pipeline 수정, 통계분석과 Excel 생성은 analysis 폴더 내부”로 더 명확해졌기 때문이다. 이전 초안에서 analysis 쪽 raw filtering replay로 열어 두었던 부분을 제거하고, pipeline paired gate와 analysis-only paired statistics workflow로 책임을 다시 나눴다.

English: This plan was fully rewritten on 2026-03-22. The reason is that the user clarified the boundary: filtering belongs in the main pipeline, while statistics and Excel generation belong inside the analysis folder. The earlier draft left room for analysis-side raw-filtering replay; this rewrite removes that ambiguity and re-splits the work into a pipeline paired gate plus an analysis-only paired statistics workflow.
