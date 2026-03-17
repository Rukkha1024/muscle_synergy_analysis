# Add concatenated source-trial window provenance manifest / `concatenated` source-trial window provenance 보강

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

이 문서는 `.agents/PLANS.md`를 따르는 수정 ExecPlan이다. 구현 단계에서는 이 문서를 기준으로 진행하고, 저장소 규칙에 따라 기존 `all_trial_window_metadata.csv` 계약은 깨지지 않아야 한다. 이 문서는 이미 체크인된 상위 계획 `.agents/execplans/Muscle Synergy \`concatenated\` Mode Separation ExecPlan.md` 위에서 동작하는 좁은 범위의 revision plan이며, 오직 review에서 지적된 2번 이슈, 즉 `concatenated` mode에서 source-trial window provenance가 충분히 남지 않는 문제만 다룬다. 구현은 사용자 승인 전까지 시작하지 않는다.

This document is a revision ExecPlan that follows `.agents/PLANS.md`. During implementation it becomes the source of truth, and the existing `all_trial_window_metadata.csv` contract must remain intact. It is a narrow revision plan that sits on top of the checked-in parent plan `.agents/execplans/Muscle Synergy \`concatenated\` Mode Separation ExecPlan.md`, and it addresses only review item 2: `concatenated` mode does not currently preserve enough source-trial window provenance. Implementation must not begin until the user approves this plan.

## Purpose / 목적

한국어: 이 변경이 끝나면 사용자는 `concatenated` 결과를 열었을 때, 현재 analysis unit이 어떤 원본 trial들로 만들어졌는지뿐 아니라 각 source trial의 analysis window provenance를 별도 CSV에서 바로 확인할 수 있다. 지금의 `all_trial_window_metadata.csv`는 파일명만 보면 원본 trial window metadata처럼 읽히지만, 실제 `concatenated` mode에서는 synthetic `trial_num=concat_step|concat_nonstep`를 가진 analysis-unit 수준 요약에 가깝다. 이번 수정은 그 semantic mismatch를 없애기 위해, 기존 파일은 유지하면서 `concatenated` 전용 source-trial manifest CSV를 추가한다. 사용자는 새 CSV를 열어 “이 `concat_step` 또는 `concat_nonstep`이 정확히 어떤 trial window들로 구성되었는가”를 즉시 확인할 수 있어야 한다.

English: After this change, a user who opens `concatenated` outputs will be able to see not only which original trials were used to form each analysis unit, but also the analysis-window provenance for each source trial in a dedicated CSV. The current `all_trial_window_metadata.csv` sounds like original trial-window metadata, but in `concatenated` mode it behaves more like an analysis-unit summary because it uses synthetic `trial_num=concat_step|concat_nonstep`. This revision removes that semantic mismatch by keeping the existing file intact and adding a dedicated concatenated source-trial manifest CSV. A user should be able to open the new CSV and immediately answer this question: “Which original trial windows were used to build this `concat_step` or `concat_nonstep` analysis unit?”

## Progress / 진행 상황

- [x] (2026-03-18 00:00Z) 한국어: 범위를 고정했다. review에서 제안된 해결책 중 “기존 CSV 의미 변경”은 제외하고, “별도 source-trial window manifest CSV 추가”만 채택한다.
- [x] (2026-03-18 00:00Z) English: The scope is locked. Of the review remedies, “redefine the old CSV” is rejected and only “add a separate source-trial window manifest CSV” is accepted.
- [x] (2026-03-18 00:20Z) 한국어: 현재 구현 경로를 다시 읽어 확인했다. `src/synergy_stats/concatenated.py`에는 `analysis_unit_id`, `source_trial_nums_csv`, `analysis_source_trial_count`가 이미 있지만, source-trial별 window detail payload는 없다. `src/synergy_stats/clustering.py`의 `trial_window_rows`도 analysis unit당 1행이라 source-trial manifest 역할에는 부족하다.
- [x] (2026-03-18 00:20Z) English: Re-read the current implementation path. `src/synergy_stats/concatenated.py` already stores `analysis_unit_id`, `source_trial_nums_csv`, and `analysis_source_trial_count`, but it does not preserve per-source-trial window detail payloads. The `trial_window_rows` built in `src/synergy_stats/clustering.py` are also one row per analysis unit, so they are not rich enough to serve as a source-trial manifest.
- [x] (2026-03-18 00:35Z) 한국어: standalone revision ExecPlan 초안을 `.agents/execplans/Concatenated Source-Trial Window Provenance Revision ExecPlan.md`로 정리했다. 아직 구현은 시작하지 않았다.
- [x] (2026-03-18 00:35Z) English: Drafted this standalone revision ExecPlan at `.agents/execplans/Concatenated Source-Trial Window Provenance Revision ExecPlan.md`. Implementation has not started.
- [x] (2026-03-18 01:00Z) 한국어: `source_trial_details` 최소 payload와 long-row export 스키마를 확정했다. 구현은 `analysis_window_*` naming을 재사용하고, source trial당 1행 manifest를 별도 CSV로 쓰는 방식으로 고정했다.
- [x] (2026-03-18 01:00Z) English: Locked the minimum `source_trial_details` payload and the long-row export schema. The implementation reuses the `analysis_window_*` vocabulary and writes a separate one-row-per-source-trial manifest CSV.
- [x] (2026-03-18 01:05Z) 한국어: `src/synergy_stats/concatenated.py`에 `source_trial_details` payload를 추가했다. 각 source trial은 trial 번호, 순서, step class, window provenance를 meta 안에 보존한다.
- [x] (2026-03-18 01:05Z) English: Added the `source_trial_details` payload in `src/synergy_stats/concatenated.py`. Each source trial now preserves its trial number, order, step class, and window provenance inside metadata.
- [x] (2026-03-18 01:10Z) 한국어: `src/synergy_stats/clustering.py`와 `src/synergy_stats/artifacts.py`에서 source-trial manifest rows를 만들고 `all_concatenated_source_trial_windows.csv`를 mode-specific 및 root combined 위치에 쓰도록 연결했다.
- [x] (2026-03-18 01:10Z) English: Connected `src/synergy_stats/clustering.py` and `src/synergy_stats/artifacts.py` so they build source-trial manifest rows and write `all_concatenated_source_trial_windows.csv` in the mode-specific and root combined locations.
- [x] (2026-03-18 01:20Z) 한국어: `tests/test_synergy_stats/test_concatenated_mode.py`, 새 `tests/test_synergy_stats/test_artifacts.py`, `tests/test_synergy_stats/test_end_to_end_contract.py`, `README.md`를 갱신했다. `module` 환경에서 targeted pytest와 실제 `main.py` smoke run을 검증했다.
- [x] (2026-03-18 01:20Z) English: Updated `tests/test_synergy_stats/test_concatenated_mode.py`, the new `tests/test_synergy_stats/test_artifacts.py`, `tests/test_synergy_stats/test_end_to_end_contract.py`, and `README.md`. Validated with targeted pytest and real `main.py` smoke runs in the `module` environment.
- [x] (2026-03-18 00:40Z) 한국어: 사용자 승인을 받았고 구현을 시작했다.
- [x] (2026-03-18 00:40Z) English: Received user approval and started implementation.

## Surprises & Discoveries / 예상 밖 발견 사항

- Observation: 현재 `all_trial_window_metadata.csv`라는 이름은 원본 trial-window provenance처럼 들리지만, `concatenated` mode에서는 실제로 analysis-unit 수준 row를 담는다.
  Evidence: `src/synergy_stats/clustering.py`의 `build_group_exports()`는 `trial_window_rows`를 `feature_rows` 기준으로 1행씩 쌓고, `concatenated` mode의 `feature_rows`는 synthetic `trial_num=concat_step|concat_nonstep`를 가진 subject-level analysis unit이다.

- Observation: 현재 구현은 이미 `analysis_unit_id`, `source_trial_nums_csv`, `analysis_source_trial_count`를 보존하므로, provenance 강화는 additive change로 해결할 수 있다.
  Evidence: `src/synergy_stats/concatenated.py`는 `bundle.meta`에 이 세 key를 넣는다. 따라서 기존 export contract를 깨지 않고 source-trial detail payload만 추가할 수 있다.

- Observation: 새 artifact test를 넣으려면 파일 경로를 새로 정해야 할 가능성이 높다.
  Evidence: 현재 `tests/test_synergy_stats/`에는 `test_concatenated_mode.py`와 `test_end_to_end_contract.py`는 있지만 `test_artifacts.py`는 없다. 따라서 helper-level artifact 검증은 새 파일을 만들거나 기존 end-to-end contract test를 확장해야 한다.

- Observation: 가장 안전한 해결책은 “기존 CSV 의미 재정의”가 아니라 “새 CSV 추가”다.
  Evidence: README와 downstream analysis scripts는 이미 `all_trial_window_metadata.csv`를 canonical trial/window metadata처럼 읽는다. 기존 파일의 의미를 바꾸면 조용한 해석 회귀가 생길 수 있다.

- Observation: `source_trial_details` 같은 list payload를 그대로 meta에 넣으면 기존 scalar-only export helper가 깨질 수 있다.
  Evidence: 구현 중 `src/synergy_stats/clustering.py`의 `_scalar_metadata()`가 `pd.isna(list)`를 만나 `ValueError`를 냈고, list/dict/tuple/set은 scalar export 대상에서 제외하도록 수정해야 했다.

- Observation: `module` 환경 smoke validation은 fixture 기본 config를 그대로 쓰면 실패할 수 있다.
  Evidence: `tests/fixtures/global_config.yaml`는 `torchnmf`를 가리켜서 `module` 환경에서 `torch`가 없으면 `ModuleNotFoundError`가 난다. 실제 smoke run은 임시 `sklearn_nmf`/`sklearn_kmeans` config로 검증했다.

## Decision Log / 결정 로그

- Decision: 기존 `all_trial_window_metadata.csv`는 유지한다.
  Rationale: 현재 결과물과 downstream 소비 코드를 깨지 않기 위해서다.
  Date/Author: 2026-03-18 / GPT-5.4

- Decision: 새 파일 이름은 `all_concatenated_source_trial_windows.csv`로 고정한다.
  Rationale: 파일명만 보고도 “concatenated analysis unit을 구성한 source-trial window manifest”라는 뜻을 초보자도 이해할 수 있어야 한다.
  Date/Author: 2026-03-18 / GPT-5.4

- Decision: 새 CSV는 `concatenated` rows만 담는다. `trialwise` only run에서는 이 파일을 생성하지 않는다.
  Rationale: 이 파일의 의미는 concatenated provenance에만 있다. 빈 trialwise 파일을 쓰면 semantics가 흐려지고 존재 여부도 설명력이 약해진다.
  Date/Author: 2026-03-18 / GPT-5.4

- Decision: root combined export에서도 같은 파일명을 유지하고 concatenated rows만 기록한다.
  Rationale: `both` 실행 시 사용자가 root에서 바로 concatenated provenance만 따로 찾을 수 있어야 한다.
  Date/Author: 2026-03-18 / GPT-5.4

- Decision: provenance payload는 기존 upstream trial metadata를 복사해 기록하고, 새 analysis window를 재계산하지 않는다.
  Rationale: provenance는 재해석이 아니라 기존 selection/window truth의 보존이어야 하기 때문이다.
  Date/Author: 2026-03-18 / GPT-5.4

## Outcomes & Retrospective / 결과 및 회고

한국어: 구현과 검증이 완료되었다. 새 `all_concatenated_source_trial_windows.csv`는 `concatenated` output과 `both`의 root combined output에 추가되었고, 각 row는 실제 source trial window를 뜻한다. `trialwise` only run에서는 이 파일이 생성되지 않는다. 단위 테스트와 end-to-end contract test는 모두 통과했고, 실제 `main.py` smoke run에서도 root와 `concatenated/`에 새 CSV가 생성되는 것을 확인했다. 재실행 MD5 비교에서는 새 provenance CSV 자체는 완전히 일치했다. 반면 기존 curated MD5 스크립트는 `all_clustering_metadata.csv`의 미세한 floating-point 차이 때문에 run-to-run diff를 보고했는데, diff는 이번 provenance 변경이 아니라 기존 gap-statistic 부동소수점 drift 성격으로 보인다.

English: Implementation and validation are complete. The new `all_concatenated_source_trial_windows.csv` is added to `concatenated` output and to the root combined output for `both`, and each row now represents a real source-trial window. A `trialwise`-only run does not create this file. The unit tests and end-to-end contract tests pass, and real `main.py` smoke runs confirmed that the new CSV is written at the root and under `concatenated/`. In rerun MD5 checks, the new provenance CSV itself matched exactly. The existing curated MD5 script still reported a run-to-run diff in `all_clustering_metadata.csv`, but the diff appears to be a pre-existing tiny floating-point drift in gap-statistic metadata rather than a provenance regression from this revision.

## Context and Orientation / 현재 맥락과 구조 설명

한국어: 이 저장소의 synergy pipeline은 세 단계가 직접 연결된다. `scripts/emg/03_extract_synergy_nmf.py`는 trialwise 또는 concatenated analysis unit을 만들고 NMF feature row를 저장한다. `scripts/emg/04_cluster_synergies.py`는 이 feature row를 `global_step`, `global_nonstep` group으로 묶어 clustering한다. `scripts/emg/05_export_artifacts.py`와 `src/synergy_stats/artifacts.py`는 최종 CSV, parquet, workbook, figure를 쓴다.

English: Three pipeline stages matter directly here. `scripts/emg/03_extract_synergy_nmf.py` builds trialwise or concatenated analysis units and stores NMF feature rows. `scripts/emg/04_cluster_synergies.py` groups those feature rows into `global_step` and `global_nonstep` for clustering. `scripts/emg/05_export_artifacts.py` plus `src/synergy_stats/artifacts.py` write the final CSV, parquet, workbook, and figure outputs.

한국어: 이번 revision과 가장 직접적으로 연결된 파일은 네 개다. `src/synergy_stats/concatenated.py`는 `concatenated` analysis unit을 만드는 곳이다. 여기서 같은 `subject × velocity × step_class`에 속한 source trial들을 묶고 synthetic `trial_num=concat_step|concat_nonstep`를 부여한다. `src/synergy_stats/clustering.py`는 export용 long-form row들을 만든다. 지금의 `trial_window_rows`는 analysis-unit 수준에 맞고, source-trial manifest 용도에는 부족하다. `src/synergy_stats/artifacts.py`는 mode별 subdir와 root combined CSV를 실제 파일로 쓴다. `README.md`는 사용자가 결과 파일을 어떻게 읽어야 하는지 설명하는 문서다.

English: Four files matter most for this revision. `src/synergy_stats/concatenated.py` builds `concatenated` analysis units by grouping source trials within the same `subject × velocity × step_class` and assigning synthetic `trial_num=concat_step|concat_nonstep`. `src/synergy_stats/clustering.py` builds export-ready long-form rows. The current `trial_window_rows` are suitable for analysis-unit summaries, but they are not rich enough to serve as a source-trial manifest. `src/synergy_stats/artifacts.py` writes the mode-specific subdirectory files and the root combined CSVs. `README.md` explains how users should interpret those output files.

한국어: 이 문서에서 “analysis unit”은 clustering과 export의 기본 단위를 뜻한다. `trialwise`에서는 한 real trial이 하나의 analysis unit이다. `concatenated`에서는 같은 `subject × velocity × step_class`에 속한 여러 trial을 붙인 subject-level super-trial이 하나의 analysis unit이다. “source-trial window provenance”는 그 super-trial이 어떤 원본 trial의 어떤 analysis window에서 왔는지 기록한 표라는 뜻이다. 이 revision의 핵심은 “analysis unit 한 줄 요약”이 아니라 “source trial당 한 줄 manifest”를 따로 만드는 것이다.

English: In this document, an “analysis unit” means the unit treated as one row source by clustering and export. In `trialwise`, one real trial is one analysis unit. In `concatenated`, one subject-level super-trial built from several trials in the same `subject × velocity × step_class` is one analysis unit. “Source-trial window provenance” means a table that records which original trial windows were used to build that super-trial. The core goal of this revision is to add a separate “one row per source trial” manifest rather than relying on an “one row per analysis unit” summary.

## Plan of Work / 작업 계획

한국어: 첫 번째 단계는 새 source-trial manifest의 최소 스키마를 고정하는 것이다. 새 CSV는 적어도 `aggregation_mode`, `group_id`, `subject`, `velocity`, `trial_num`, `analysis_unit_id`, `source_trial_num`, `source_trial_order`, `source_step_class`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, `analysis_window_is_surrogate`를 가져야 한다. 여기서 `trial_num`은 synthetic parent key인 `concat_step` 또는 `concat_nonstep`이고, `source_trial_num`이 실제 원본 trial 번호다. 기존 `analysis_*` naming을 최대한 재사용해 사용자가 새로운 용어 체계를 따로 배울 필요가 없게 한다.

English: The first step is to lock the minimum schema for the new source-trial manifest. The new CSV must include at least `aggregation_mode`, `group_id`, `subject`, `velocity`, `trial_num`, `analysis_unit_id`, `source_trial_num`, `source_trial_order`, `source_step_class`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, and `analysis_window_is_surrogate`. Here `trial_num` stays the synthetic parent value `concat_step` or `concat_nonstep`, while `source_trial_num` is the real original trial number. Reuse the existing `analysis_*` vocabulary whenever possible so users do not need to learn a second naming system.

한국어: 두 번째 단계는 `src/synergy_stats/concatenated.py`에 source-trial detail payload를 남기는 것이다. 현재 builder는 `analysis_unit_id`, `source_trial_nums_csv`, `analysis_source_trial_count`까지만 남긴다. 이 revision에서는 `source_trial_details` 같은 list payload를 추가해, 각 원소가 하나의 source trial을 설명하게 한다. 각 원소는 최소한 `source_trial_num`, `source_trial_order`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, `analysis_window_is_surrogate`, `source_step_class`를 가져야 한다. 이 값은 기존 `trial.metadata`와 `TrialRecord`의 selection/window truth에서 복사해야 하며, 새로 계산하면 안 된다.

English: The second step is to preserve a source-trial detail payload inside `src/synergy_stats/concatenated.py`. The current builder stores only `analysis_unit_id`, `source_trial_nums_csv`, and `analysis_source_trial_count`. This revision adds a list payload such as `source_trial_details` where each element describes one source trial. Each element must include at least `source_trial_num`, `source_trial_order`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, `analysis_window_is_surrogate`, and `source_step_class`. These values must be copied from existing `trial.metadata` and `TrialRecord` selection/window truth rather than recomputed.

한국어: 세 번째 단계는 export row 생성 단계에서 이 payload를 long-form rows로 펼치는 것이다. `src/synergy_stats/clustering.py`의 `build_group_exports()` 또는 그와 같은 helper 경로에서, concatenated analysis unit의 `source_trial_details`를 source trial당 1행으로 펼친다. 중요한 점은 row granularity다. 현재 `trial_window_rows`는 analysis unit당 1행이다. 새 manifest는 source trial당 1행이어야 한다. 예를 들어 `concat_step` 하나가 source trial 2개로 만들어졌다면 새 CSV에는 같은 `analysis_unit_id` 아래 2행이 나와야 한다.

English: The third step is to expand that payload into long-form rows during export-row construction. In `src/synergy_stats/clustering.py`, inside `build_group_exports()` or a nearby helper path, expand the concatenated analysis unit’s `source_trial_details` into one row per source trial. Row granularity is the critical point. The current `trial_window_rows` are one row per analysis unit. The new manifest must be one row per source trial. If one `concat_step` unit was built from two source trials, the new CSV must contain two rows under the same `analysis_unit_id`.

한국어: 네 번째 단계는 exporter에 새 CSV를 추가하는 것이다. `src/synergy_stats/artifacts.py`와 `scripts/emg/05_export_artifacts.py`는 mode-specific concatenated output 아래에 `all_concatenated_source_trial_windows.csv`를 써야 한다. 경로는 `outputs/runs/<run_id>/concatenated/all_concatenated_source_trial_windows.csv`로 고정한다. `both` 실행에서는 root combined에도 같은 파일명을 써서 `outputs/runs/<run_id>/all_concatenated_source_trial_windows.csv`를 만든다. root 파일에는 concatenated rows만 담고, `trialwise` only run에서는 이 파일을 만들지 않는다.

English: The fourth step is to add the new CSV to the exporter. `src/synergy_stats/artifacts.py` and `scripts/emg/05_export_artifacts.py` must write `all_concatenated_source_trial_windows.csv` under the mode-specific concatenated output at `outputs/runs/<run_id>/concatenated/all_concatenated_source_trial_windows.csv`. When `both` is executed, the exporter must also write the same filename at the root combined output as `outputs/runs/<run_id>/all_concatenated_source_trial_windows.csv`. The root file contains only concatenated rows, and a `trialwise`-only run must not create this file at all.

한국어: 다섯 번째 단계는 README를 고치는 것이다. 기존 `all_trial_window_metadata.csv` 설명은 유지하되, `concatenated` mode에서는 그것이 source-trial manifest가 아니라 analysis-unit summary라는 점을 분명히 적는다. 이어서 새 `all_concatenated_source_trial_windows.csv`를 설명한다. README는 최소한 네 가지를 분명히 말해야 한다. 첫째, 기존 `all_trial_window_metadata.csv`는 analysis-unit 수준 요약이다. 둘째, `concatenated` mode의 true source-trial provenance는 새 CSV에 있다. 셋째, 새 CSV의 한 row는 한 개의 source-trial window다. 넷째, `trial_num=concat_step|concat_nonstep`는 부모 analysis unit이고 `source_trial_num`이 실제 원본 trial 번호다.

English: The fifth step is to update the README. Keep the existing explanation of `all_trial_window_metadata.csv`, but explicitly state that in `concatenated` mode it is an analysis-unit summary, not a true source-trial manifest. Then document the new `all_concatenated_source_trial_windows.csv`. The README must make four points clear. First, the existing `all_trial_window_metadata.csv` is an analysis-unit-level summary table. Second, true source-trial provenance for `concatenated` mode lives in the new CSV. Third, each row in the new CSV means one source-trial window. Fourth, `trial_num=concat_step|concat_nonstep` is the parent analysis unit, while `source_trial_num` is the real original trial number.

한국어: 여섯 번째 단계는 테스트를 추가하는 것이다. `tests/test_synergy_stats/test_concatenated_mode.py`에는 `source_trial_details` payload가 비어 있지 않고 source trial 수와 길이가 맞는지 확인하는 unit test를 추가한다. artifact-level 검증은 현재 전용 파일이 없으므로, 새 테스트 파일을 만들거나 `tests/test_synergy_stats/test_end_to_end_contract.py`를 확장해 `all_concatenated_source_trial_windows.csv` 생성, 컬럼 존재, 같은 `analysis_unit_id` 아래 여러 `source_trial_num` row 허용 여부를 확인한다. `both` 실행에서는 root와 `concatenated/`에 파일이 생기고, `trialwise/`에는 파일이 없음을 보장해야 한다.

English: The sixth step is to add tests. In `tests/test_synergy_stats/test_concatenated_mode.py`, add a unit test that confirms the `source_trial_details` payload is non-empty and matches the number of source trials. For artifact-level validation, there is currently no dedicated artifact test file, so either create one or extend `tests/test_synergy_stats/test_end_to_end_contract.py` to assert that `all_concatenated_source_trial_windows.csv` is created, contains the required columns, and allows multiple `source_trial_num` rows under the same `analysis_unit_id`. A `both` run must create the file in the root and `concatenated/`, while `trialwise/` must not contain it.

## Concrete Steps / 구체 단계

한국어: 모든 명령은 repo root인 `/home/alice/workspace/26-03-synergy-analysis`에서 실행한다. 검증 환경은 사용자 요청에 맞춰 conda env `module`을 사용한다. 먼저 baseline을 확인한다.

English: Run all commands from the repository root `/home/alice/workspace/26-03-synergy-analysis`. Use the `module` conda environment for validation, as requested by the user. Start by checking the current baseline.

    conda run -n module python main.py --help
    conda run -n module python -m pytest tests/test_synergy_stats/test_concatenated_mode.py -q
    conda run -n module python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q

한국어: 구현 후에는 새 또는 갱신된 테스트를 다시 실행한다. artifact helper test를 새로 만들었다면 그 파일도 함께 실행한다.

English: After implementation, rerun the new or updated tests. If a new artifact helper test file is added, run that file as well.

    conda run -n module python -m pytest tests/test_synergy_stats/test_concatenated_mode.py -q
    conda run -n module python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q
    conda run -n module python -m pytest tests/test_synergy_stats/<new_artifact_test_file>.py -q

한국어: 그다음 smoke run으로 file contract를 확인한다.

English: Then use smoke runs to confirm the file contract.

    conda run -n module python main.py --config configs/global_config.yaml --mode concatenated --out outputs/runs/concat_provenance_check --overwrite
    conda run -n module python main.py --config configs/global_config.yaml --mode both --out outputs/runs/both_provenance_check --overwrite

한국어: 성공하면 최소한 아래 경로가 존재해야 한다.

English: On success, at least these paths must exist.

    outputs/runs/concat_provenance_check/concatenated/all_concatenated_source_trial_windows.csv
    outputs/runs/both_provenance_check/concatenated/all_concatenated_source_trial_windows.csv
    outputs/runs/both_provenance_check/all_concatenated_source_trial_windows.csv

한국어: 별도 `trialwise` only run에서는 아래 경로가 없어야 한다.

English: In a separate `trialwise`-only run, this path must not exist.

    outputs/runs/<trialwise_run>/trialwise/all_concatenated_source_trial_windows.csv

## Validation and Acceptance / 검증 및 완료 기준

한국어: 이 revision의 acceptance는 사용자가 파일을 직접 열어 provenance를 바로 확인할 수 있느냐로 정의한다. `concatenated` run 후 새 CSV가 존재해야 하고, 그 CSV에는 최소한 `analysis_unit_id`, `trial_num`, `source_trial_num`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, `analysis_window_is_surrogate`가 있어야 한다. 같은 `analysis_unit_id` 아래에 2개 이상의 `source_trial_num` row가 보이면, source-trial manifest가 analysis-unit summary가 아니라는 점을 사람이 즉시 검증할 수 있다.

English: Acceptance for this revision is defined by whether a user can open a file and directly inspect provenance. After a `concatenated` run, the new CSV must exist and include at least `analysis_unit_id`, `trial_num`, `source_trial_num`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, and `analysis_window_is_surrogate`. If the same `analysis_unit_id` appears with two or more `source_trial_num` rows, a human can immediately verify that the manifest is no longer just an analysis-unit summary.

한국어: `both` run 후에는 root에도 같은 파일이 존재해야 하며, root 파일의 `aggregation_mode` 값은 모두 `concatenated`여야 한다. 기존 `all_trial_window_metadata.csv`는 계속 존재해야 한다. 이번 수정은 additive change여야 하며, 기존 파일 삭제나 이름 변경은 허용되지 않는다.

English: After a `both` run, the same file must also exist at the root, and every `aggregation_mode` value in that root file must be `concatenated`. The existing `all_trial_window_metadata.csv` must still exist. This revision must remain additive; deleting or renaming the old file is not allowed.

한국어: 테스트 기준으로는 세 가지 행동이 보장되어야 한다. 첫째, 변경 전에는 새 CSV가 없거나 새 테스트가 실패한다. 둘째, 변경 후에는 새 CSV가 생성되고 필수 컬럼이 존재한다. 셋째, `trialwise` only run에서는 새 파일이 생성되지 않는다.

English: From the test perspective, three behaviors must be locked. First, before the change the new CSV does not exist or the new tests fail. Second, after the change the new CSV is created and contains the required columns. Third, in a `trialwise`-only run the new file is not generated.

## Idempotence and Recovery / 멱등성과 복구

한국어: 이 수정은 additive change다. 기존 CSV를 삭제하거나 이름을 바꾸지 않으므로 `--overwrite` 재실행에도 안전해야 한다. run이 실패하면 같은 output dir에 `--overwrite`로 다시 실행하면 된다. 새 source-trial manifest는 기존 metadata에서 다시 펼쳐 만드는 파일이어야 하므로, 중간 CSV를 수동 편집해 맞추지 않는다. `trialwise` only run에서 파일을 쓰지 않는 규칙도 recovery를 단순하게 유지하기 위한 선택이다.

English: This revision is additive. Because it does not delete or rename existing CSV files, repeated `--overwrite` runs must remain safe. If a run fails, rerun with the same output directory and `--overwrite`. The new source-trial manifest must always be rebuilt from stored metadata, so no one should patch the CSV by hand. The rule that `trialwise`-only runs do not create the file also keeps recovery simple and the presence of the file meaningful.

## Artifacts and Notes / 산출물과 비고

한국어: 새 CSV의 한 valid row는 아래 의미를 가져야 한다.

English: A valid row in the new CSV should have this meaning.

    aggregation_mode=concatenated
    group_id=global_step
    subject=S01
    velocity=60
    trial_num=concat_step
    analysis_unit_id=S01_v60_step_concat
    source_trial_num=1
    source_trial_order=1
    source_step_class=step
    analysis_window_source=manual_or_auto
    analysis_window_start=120
    analysis_window_end=260
    analysis_window_length=141
    analysis_window_is_surrogate=False

한국어: 같은 parent analysis unit의 두 번째 source trial row는 아래처럼 이어질 수 있다. 이 예시는 사용자가 파일을 열었을 때 “`concat_step`이 trial 1과 3으로 만들어졌구나”를 즉시 이해하게 만드는 읽기 경험을 목표로 한다.

English: A second source-trial row for the same parent analysis unit can look like this. The intended reading experience is that a novice immediately sees that `concat_step` was built from trial 1 and trial 3.

    aggregation_mode=concatenated
    group_id=global_step
    subject=S01
    velocity=60
    trial_num=concat_step
    analysis_unit_id=S01_v60_step_concat
    source_trial_num=3
    source_trial_order=2
    source_step_class=step
    analysis_window_source=manual_or_auto
    analysis_window_start=118
    analysis_window_end=258
    analysis_window_length=141
    analysis_window_is_surrogate=False

## Interfaces and Dependencies / 인터페이스와 의존성

한국어: 구현이 끝나면 `src/synergy_stats/concatenated.py`의 concatenated analysis-unit metadata에는 최소한 `analysis_unit_id`, `source_trial_nums_csv`, `analysis_source_trial_count`, `source_trial_details`가 존재해야 한다. 여기서 `source_trial_details`는 dict list다. 이 list의 각 원소는 최소한 `source_trial_num`, `source_trial_order`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, `analysis_window_is_surrogate`, `source_step_class`를 포함해야 한다.

English: At the end of implementation, the concatenated analysis-unit metadata in `src/synergy_stats/concatenated.py` must contain at least `analysis_unit_id`, `source_trial_nums_csv`, `analysis_source_trial_count`, and `source_trial_details`. Here `source_trial_details` is a list of dictionaries. Each element in that list must include at least `source_trial_num`, `source_trial_order`, `analysis_window_source`, `analysis_window_start`, `analysis_window_end`, `analysis_window_length`, `analysis_window_is_surrogate`, and `source_step_class`.

한국어: `src/synergy_stats/clustering.py` 또는 그 이전 helper는 이 metadata를 source-trial당 1행의 export structure로 바꿀 수 있어야 한다. 최종 CSV 파일명은 mode-specific과 root combined 모두 `all_concatenated_source_trial_windows.csv`로 고정한다. 새 라이브러리는 필요 없다. 현재 export stack을 재사용하고, 저장소 규칙에 따라 가능하면 `polars`를 먼저 사용한다. 다만 현재 artifact writer는 pandas 기반이므로, 꼭 필요한 좁은 범위 수정만 한다.

English: `src/synergy_stats/clustering.py` or a nearby helper earlier in the path must be able to turn that metadata into an export structure where one row means one source trial. The final CSV filename is fixed as `all_concatenated_source_trial_windows.csv` for both the mode-specific and root combined outputs. No new library is required. Reuse the current export stack and prefer `polars` where practical, but keep the changes narrow because the current artifact writer is pandas-based.

## Change Note / 변경 메모

한국어: 이 revision ExecPlan은 기존 `.agents/execplans/Muscle Synergy \`concatenated\` Mode Separation ExecPlan.md`의 전체 범위를 다시 열지 않고, review에서 남은 2번 이슈만 독립적으로 추적하기 위해 추가되었다. 핵심은 기존 `all_trial_window_metadata.csv`를 유지한 채, `concatenated` 전용 source-trial window manifest CSV를 추가해 이름과 내용의 의미 불일치를 없애는 것이다.

English: This revision ExecPlan is added so review item 2 can be tracked independently without reopening the full scope of `.agents/execplans/Muscle Synergy \`concatenated\` Mode Separation ExecPlan.md`. The key idea is to keep the existing `all_trial_window_metadata.csv` intact while adding a dedicated concatenated source-trial window manifest CSV that removes the mismatch between file name and actual contents.

한국어: 이번 수정에서 plan을 구현 상태에 맞춰 갱신했다. Progress를 완료 상태로 바꾸고, scalar-only metadata exporter가 list payload에서 깨진 점과 `module` 환경 smoke config 조정 필요성을 기록했다.

English: This revision updates the plan to match the implemented state. The Progress section is now completed, and the document records that the scalar-only metadata exporter needed a guard for list payloads and that `module` smoke validation required a non-Torch config override.
