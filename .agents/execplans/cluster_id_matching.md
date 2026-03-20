# Repair `component_index` integrity in `first_zero_duplicate_k_rerun` / `first_zero_duplicate_k_rerun`의 `component_index` 무결성 복구

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

이 문서는 저장소 루트의 `.agents/PLANS.md`를 따르는 bilingual revision ExecPlan이다. 구현자는 이 문서만 읽고도 왜 이 변경이 필요한지, 어느 파일을 어떻게 고쳐야 하는지, 무엇을 실행하고 무엇을 관찰해야 하는지 이해할 수 있어야 한다. 구현은 사용자가 이 계획을 승인한 뒤에만 시작하며, 구현 중 발견 사항이 생기면 이 문서의 living sections를 즉시 갱신한다.

This document is a bilingual revision ExecPlan maintained in accordance with `.agents/PLANS.md` at the repository root. A novice implementer should be able to read only this file and understand why the change matters, which files must be edited, what commands to run, and what observable results prove success. Implementation must begin only after user approval, and the living sections in this document must be updated as new facts are discovered.

## Purpose / 목적

한국어: 이 변경이 끝나면 `analysis/first_zero_duplicate_k_rerun/`가 다시 생성한 parquet, workbook, Figure 05, trial NMF figure에서 같은 trial component를 같은 key로 추적할 수 있다. 사용자는 `cluster_labels`, `minimal_W`, `minimal_H_long`에서 `(trial_id, component_index)`를 기준으로 component를 찾고, Figure 05에서는 같은 cluster mean이 더 이상 cross join으로 오염되지 않았음을 확인할 수 있으며, trial figure에서는 각 subplot이 어떤 component이며 어떤 cluster에 배정되었는지 동시에 읽을 수 있어야 한다.

English: After this change, the regenerated parquet, workbook, Figure 05, and trial NMF figures under `analysis/first_zero_duplicate_k_rerun/` will let a user trace the same trial component with one stable key. A user should be able to look up a component by `(trial_id, component_index)` in `cluster_labels`, `minimal_W`, and `minimal_H_long`, verify that Figure 05 is no longer contaminated by cross joins, and read each trial subplot as both a specific component and its assigned cluster.

한국어: 이 작업은 그림 한 장의 스타일 수정이 아니다. 이 저장소에서 `component_index`는 component-level assignment를 연결하는 기준 key다. 이 값이 무너지면 `labels`와 `minimal_W` 또는 `minimal_H_long`의 join이 many-to-many로 오염되고, cluster mean과 trial figure 해석이 동시에 잘못된다. 따라서 이 계획은 direct bug를 수정하고, 공용 export 경로에서 같은 종류의 key overwrite가 다시 퍼지지 않도록 최소 hardening을 추가한다.

English: This is not a cosmetic figure tweak. In this repository, `component_index` is the key that ties component-level assignments together. Once that value collapses, joins between `labels` and `minimal_W` or `minimal_H_long` become many-to-many, and both cluster means and trial-figure interpretation fail together. This plan therefore fixes the direct bug and adds minimal hardening in the shared export path so the same key-overwrite pattern cannot silently spread again.

## Progress / 진행 상황

- [x] (2026-03-20 02:00Z) 한국어: rerun artifact와 baseline production artifact를 비교해 직접 원인이 rerun reconstruction path에 있음을 재확인했다.
- [x] (2026-03-20 02:00Z) English: Reconfirmed by comparing rerun and baseline production artifacts that the direct bug lives in the rerun reconstruction path.
- [x] (2026-03-20 02:20Z) 한국어: Figure 05 W 문제뿐 아니라 H mean도 같은 join key 오염으로 함께 깨진다는 점을 범위에 포함했다.
- [x] (2026-03-20 02:20Z) English: Expanded the scope to include H means, because the same join-key corruption affects both W and H outputs.
- [x] (2026-03-20 02:35Z) 한국어: 기존 초안을 bilingual living ExecPlan 형식으로 다시 작성했다.
- [x] (2026-03-20 02:35Z) English: Rewrote the earlier draft into a bilingual living ExecPlan format.
- [x] (2026-03-20 10:35Z) 한국어: 계획 리뷰 결과를 반영해 trial figure 데이터 흐름, stronger validation, rerun command, checksum handling을 다시 설계했다.
- [x] (2026-03-20 10:35Z) English: Incorporated review findings and redesigned the trial-figure data flow, stronger validation, rerun command, and checksum handling.
- [x] (2026-03-20 10:14Z) 한국어: `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`에서 reconstruction metadata copy bug를 수정해 `component_index`가 trial-level metadata에 다시 들어가지 않도록 했다.
- [x] (2026-03-20 10:14Z) English: Fixed the reconstruction metadata-copy bug in `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py` so `component_index` no longer re-enters trial-level metadata.
- [x] (2026-03-20 10:14Z) 한국어: `src/synergy_stats/clustering.py`에서 metadata spread를 explicit row fields 앞으로 옮겨 export row builder를 harden했다.
- [x] (2026-03-20 10:14Z) English: Hardened `src/synergy_stats/clustering.py` by moving metadata spread ahead of explicit row fields.
- [x] (2026-03-20 10:14Z) 한국어: `src/synergy_stats/figure_rerender.py`와 `src/synergy_stats/figures.py`를 수정해 trial figure가 `component_index`를 row identity로 유지하고 assigned cluster를 annotation으로 표시하게 했다.
- [x] (2026-03-20 10:14Z) English: Updated `src/synergy_stats/figure_rerender.py` and `src/synergy_stats/figures.py` so trial figures keep `component_index` as the row identity and display the assigned cluster as an annotation.
- [x] (2026-03-20 10:14Z) 한국어: rerun을 다시 실행하고 parquet, workbook, Figure 04, Figure 05, trial figure, generated checksum manifest까지 검증했다.
- [x] (2026-03-20 10:14Z) English: Re-ran the analysis and validated the parquet, workbook, Figure 04, Figure 05, trial figures, and generated checksum manifest.

## Surprises & Discoveries / 예상 밖 발견 사항

- Observation: rerun artifact의 문제는 Figure 05 W 패널 하나로 끝나지 않는다.
  Evidence: `src/synergy_stats/artifacts.py`의 `_build_pooled_cluster_strategy_W_means()`와 `_build_pooled_cluster_strategy_H_means_long()`는 모두 `group_id, trial_id, component_index`를 이용해 component assignment를 결합한다. rerun artifact에서 이 key가 깨지면 W mean과 H mean이 함께 오염된다.

- Observation: trial figure 경로는 현재 실제 cluster assignment를 읽지 않고 `component_index`를 `cluster_id`로 rename해서 사용한다.
  Evidence: `src/synergy_stats/figure_rerender.py`는 trial `minimal_w`와 `minimal_h_long`를 읽은 뒤 `component_index`를 `cluster_id`로 rename해서 `save_trial_nmf_figure()`에 넘긴다. 따라서 문구만 바꿔서는 “Component X (Cluster Y)”를 올바르게 표시할 수 없다.

- Observation: baseline production bundle은 이 문제가 없다.
  Evidence: `outputs/final_concatenated.parquet`에서는 `labels`, `minimal_W`, `minimal_H_long`의 `component_index`가 `0..6`처럼 유지된다. direct cause는 rerun reconstruction helper다.

- Observation: 공용 export helper는 upstream metadata가 오염되면 component key를 다시 덮어쓸 수 있다.
  Evidence: `src/synergy_stats/clustering.py`의 `build_group_exports()`는 `labels`, `minimal_W`, `minimal_H_long` row를 만들 때 explicit fields와 `trial_meta`를 같은 dict에 섞는다. metadata spread가 뒤에 오면 explicit key가 덮어써질 수 있다.

- Observation: checksum 파일은 이미 analysis script가 생성한다.
  Evidence: `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`는 rerun 완료 시 `_write_checksums(...)`를 호출해 `checksums.md5`를 기록한다. 따라서 계획서가 shell `md5sum > checksums.md5`를 다시 실행하라고 지시하면 generated manifest 형식과 encoding을 불필요하게 바꿀 수 있다.

- Observation: generated checksum manifest는 `md5sum -c`에 대해 유효하지만 첫 줄의 BOM 때문에 warning 한 줄이 출력된다.
  Evidence: rerun 후 `md5sum -c analysis/first_zero_duplicate_k_rerun/artifacts/default_run/checksums.md5`는 모든 artifact에 대해 `OK`를 반환했고, 동시에 `WARNING: 1 line is improperly formatted`를 출력했다. `checksums.md5`의 raw bytes를 확인하면 UTF-8 BOM으로 시작한다.

## Decision Log / 결정 로그

- Decision: direct bug fix는 `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`에서 한다.
  Rationale: baseline production bundle은 정상이고 rerun reconstruction 결과만 깨져 있으므로, primary fix point는 analysis-side reconstruction helper여야 한다.
  Date/Author: 2026-03-20 / GPT-5.4

- Decision: `src/synergy_stats/clustering.py`는 최소 hardening 대상으로 유지한다.
  Rationale: direct cause는 아니지만, shared export path에서 explicit component fields가 metadata에 덮이면 future upstream bug가 같은 형태로 다시 퍼질 수 있다.
  Date/Author: 2026-03-20 / GPT-5.4

- Decision: trial figure는 component identity를 버리지 않고 assigned cluster를 추가로 보여 준다.
  Rationale: workbook과 parquet의 canonical key는 `(trial_id, component_index)`다. figure가 이 key를 버리면 사용자가 workbook과 figure를 왕복할 때 대응 관계를 잃는다.
  Date/Author: 2026-03-20 / GPT-5.4

- Decision: trial figure 수정은 실제 `labels` join을 포함해야 한다.
  Rationale: 현재 path는 `component_index`를 `cluster_id`로 rename하는 shortcut을 쓰기 때문에, 제목 문자열만 바꾸면 잘못된 cluster id를 더 그럴듯하게 표시하는 회귀가 된다.
  Date/Author: 2026-03-20 / GPT-5.4

- Decision: validation은 unique-value spot check만으로 끝내지 않고 join cardinality 확인을 포함한다.
  Rationale: 이 버그의 핵심 failure mode는 many-to-many contamination이므로, row count 기반 검증이 반드시 필요하다.
  Date/Author: 2026-03-20 / GPT-5.4

- Decision: checksum regeneration은 script-generated manifest를 검증 대상으로 삼고, 수동 shell overwrite는 계획에서 제외한다.
  Rationale: 이미 구현된 checksum writer가 있으므로, 계획서는 새로운 artifact 집합이 그 writer에 의해 올바르게 반영되었는지를 확인하면 충분하다.
  Date/Author: 2026-03-20 / GPT-5.4

- Decision: checksum writer의 BOM warning은 이번 revision 범위에 포함하지 않고 residual note로 남긴다.
  Rationale: 이번 작업의 acceptance criteria는 `component_index` integrity와 join-cardinality 복구다. generated manifest는 모든 artifact를 성공적으로 검증했고, warning은 별도 formatting 개선 작업으로 분리하는 편이 범위를 더 명확하게 유지한다.
  Date/Author: 2026-03-20 / GPT-5.4

## Outcomes & Retrospective / 결과 및 회고

한국어: 구현과 rerun validation이 끝났다. direct fix는 rerun reconstruction helper에서 `component_index`를 trial-level metadata에서 제외한 것이고, hardening은 shared export helper에서 explicit component fields가 metadata를 항상 덮어쓰도록 순서를 바꾼 것이다. trial figure path는 실제 `labels`를 join해 `assigned_cluster_id`를 붙이고, renderer는 `component_index`를 row identity로 유지하면서 `Component X (Cluster Y)` 형식의 제목을 그리게 되었다. regression test 11개와 추가 clustering/artifact test를 통과했고, regenerated `final_concatenated.parquet`에서 `labels`, `minimal_W`, `minimal_H_long`의 `component_index` unique set이 모두 `0..6`으로 복구되었다. pooled join cardinality도 `minimal_W 3536 == joined_W 3536`, `minimal_H_long 22100 == joined_H 22100`로 확인되어 Figure 05 contamination 조건이 해소되었다. workbook은 `cluster_labels`, `minimal_W`, `minimal_H`, `trial_windows`를 포함한 expected sheets를 유지했고, Figure 04/05 및 sample trial figure를 시각적으로 확인했을 때 component identity와 assigned cluster가 함께 표시되었다.

English: Implementation and rerun validation are complete. The direct fix excluded `component_index` from trial-level metadata in the rerun reconstruction helper, and the hardening change reordered the shared export helper so explicit component fields always override metadata. The trial-figure path now joins the real `labels` rows to add `assigned_cluster_id`, and the renderer keeps `component_index` as the row identity while titling rows in a `Component X (Cluster Y)` style. The updated code passed 11 focused regression tests plus the broader clustering/artifact test set, and the regenerated `final_concatenated.parquet` restored the unique `component_index` set `0..6` in `labels`, `minimal_W`, and `minimal_H_long`. Pooled join cardinality also validated as `minimal_W 3536 == joined_W 3536` and `minimal_H_long 22100 == joined_H 22100`, which is the observable sign that Figure 05 contamination is gone. The workbook retained the expected sheets including `cluster_labels`, `minimal_W`, `minimal_H`, and `trial_windows`, and a visual spot-check of Figure 04, Figure 05, and a sample trial figure confirmed that component identity and assigned cluster now appear together.

## Context and Orientation / 현재 맥락과 구조 설명

한국어: 이 저장소에서 synergy component는 여러 산출물 사이를 `(trial_id, component_index)`로 연결한다. `cluster_labels`는 각 component가 어떤 `cluster_id`에 배정되었는지 기록하고, `minimal_W`는 같은 component의 근육 가중치, `minimal_H_long`는 같은 component의 시간 activation 값을 저장한다. `pooled_strategy_w_means`와 `pooled_strategy_h_means`는 `labels`와 `minimal_*`를 join해 Figure 05용 cluster mean을 만든다. 따라서 `component_index`가 잘못되면 label lookup과 mean 계산이 동시에 깨진다.

English: In this repository, synergy components are connected across outputs by `(trial_id, component_index)`. `cluster_labels` records which `cluster_id` each component was assigned to, `minimal_W` stores the muscle weights for that same component, and `minimal_H_long` stores its time-series activation values. `pooled_strategy_w_means` and `pooled_strategy_h_means` are built by joining `labels` with the `minimal_*` tables to produce Figure 05 cluster means. If `component_index` is wrong, both label lookup and mean aggregation fail together.

한국어: 이번 이슈와 직접 연결된 파일은 다섯 개다. `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`는 saved parquet bundle에서 feature rows를 다시 조립하는 analysis-side entrypoint다. `src/synergy_stats/clustering.py`는 clustering 결과를 export row들로 바꾸는 공용 helper다. `src/synergy_stats/artifacts.py`는 Figure 05용 pooled strategy mean을 만든다. `src/synergy_stats/figure_rerender.py`는 saved artifact에서 figure를 다시 그리는 진입점이고, `src/synergy_stats/figures.py`는 trial figure와 pooled figures의 실제 matplotlib 렌더러를 갖고 있다.

English: Five files matter directly for this issue. `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py` is the analysis-side entrypoint that rebuilds feature rows from a saved parquet bundle. `src/synergy_stats/clustering.py` is the shared helper that converts clustering results into export rows. `src/synergy_stats/artifacts.py` builds the pooled strategy means used by Figure 05. `src/synergy_stats/figure_rerender.py` is the entrypoint that redraws figures from saved artifacts, and `src/synergy_stats/figures.py` contains the actual matplotlib renderers for trial and pooled figures.

한국어: 현재 확인된 사실은 다음과 같다. baseline production bundle은 정상이다. rerun artifact만 깨져 있다. direct cause는 rerun reconstruction helper가 `trial_pdf.iloc[0]`의 scalar metadata를 복사할 때 `component_index`까지 `bundle.meta`에 넣는 것이다. 그 뒤 공용 export helper가 metadata를 spread하면서 각 component row의 explicit `component_index`를 덮어써 `0`으로 무너뜨린다. Figure 05는 이 잘못된 key로 `labels`와 `minimal_*`를 join하기 때문에 many-to-many contamination이 생긴다. trial figure는 이와 별도로, 현재부터 잘못된 shortcut을 사용해 `component_index`를 `cluster_id`로 rename한다.

English: The confirmed situation is this. The baseline production bundle is healthy. Only the rerun artifact is broken. The direct cause is that the rerun reconstruction helper copies scalar metadata from `trial_pdf.iloc[0]` and mistakenly stores `component_index` inside `bundle.meta`. The shared export helper then spreads that metadata and overwrites the explicit per-component `component_index`, collapsing it to `0`. Figure 05 joins `labels` with `minimal_*` using that bad key, so many-to-many contamination follows. Separately, the trial-figure path currently uses a misleading shortcut by renaming `component_index` to `cluster_id`.

## Plan of Work / 작업 계획

한국어: 첫 번째 단계는 `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`의 `_rebuild_feature_rows()`를 수정해 `component_index`가 trial-level scalar metadata에 들어가지 않게 하는 것이다. 현재 helper는 `trial_pdf.iloc[0]`의 거의 모든 컬럼을 `meta` dict에 복사한다. 이때 `component_index`가 포함되면 trial-level metadata 안에 “첫 번째 component 번호”가 들어가고, export 단계에서 이 값이 모든 component row에 재사용된다. 구현은 exclusion set에 `component_index`를 추가하는 최소 수정으로 제한한다.

English: The first step is to update `_rebuild_feature_rows()` in `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py` so `component_index` never enters the trial-level scalar metadata. The helper currently copies almost every column from `trial_pdf.iloc[0]` into `meta`. If `component_index` is included, the metadata incorrectly stores the first component number for the whole trial, and the export stage later reuses that value for every component row. Keep this implementation minimal by adding `component_index` to the metadata exclusion set.

한국어: 두 번째 단계는 `src/synergy_stats/clustering.py`의 `build_group_exports()`를 harden하는 것이다. 이 함수는 `labels_df`, `minimal_w_rows`, `minimal_h_rows`를 만들 때 explicit component fields와 `trial_meta`를 같은 dict literal에 섞는다. 이 revision에서는 metadata spread를 먼저 배치하고, `component_index`, `cluster_id`, `muscle`, `W_value`, `frame_idx`, `h_value` 같은 row-specific explicit fields를 마지막에 기록하도록 순서를 고정한다. 목표는 upstream metadata가 오염되더라도 export path에서 component key를 다시 덮지 못하게 만드는 것이다.

English: The second step is to harden `build_group_exports()` in `src/synergy_stats/clustering.py`. That function builds `labels_df`, `minimal_w_rows`, and `minimal_h_rows` by mixing explicit component fields with `trial_meta` in the same dict literal. In this revision, place the metadata spread first, then write row-specific explicit fields such as `component_index`, `cluster_id`, `muscle`, `W_value`, `frame_idx`, and `h_value` last. The goal is to prevent the export path from overwriting the component key even if upstream metadata is polluted.

한국어: 세 번째 단계는 trial figure path를 실행 가능한 구조로 바꾸는 것이다. 단순히 제목 문자열을 바꾸지 않는다. `src/synergy_stats/figure_rerender.py`에서 trial figure를 그릴 때 `artifacts["labels"]`에서 같은 `group_id`, `trial_id`의 `component_index -> cluster_id` mapping을 읽고, 이를 trial `minimal_W`와 `minimal_H_long`에 `group_id, trial_id, component_index`로 join해 `assigned_cluster_id` 같은 별도 컬럼을 만든다. 즉 trial figure input은 component identity를 나타내는 `component_index`를 유지하고, display-only cluster assignment를 추가로 가진다.

English: The third step is to make the trial-figure path executable as written. Do not merely change title strings. In `src/synergy_stats/figure_rerender.py`, when drawing a trial figure, read the `component_index -> cluster_id` mapping for the same `group_id` and `trial_id` from `artifacts["labels"]`, then join that mapping into the trial `minimal_W` and `minimal_H_long` frames on `group_id, trial_id, component_index`, producing a separate display column such as `assigned_cluster_id`. In other words, the trial-figure input must keep `component_index` as the component identity and add cluster assignment only as display metadata.

한국어: 네 번째 단계는 `src/synergy_stats/figures.py`의 trial figure renderer를 그 구조에 맞게 바꾸는 것이다. 현재 `_render_component_grid()`는 `cluster_id` 컬럼만 row identity로 사용한다. 이번 변경에서는 이 함수를 일반화해 row identity 컬럼을 인수로 받게 하고, trial figure path에서는 `component_index`를 row identity로, `assigned_cluster_id`를 title annotation용 display field로 사용한다. 즉 `save_trial_nmf_figure()`는 `_render_component_grid()`를 호출할 때 `row_id_column="component_index"`와 `cluster_annotation_column="assigned_cluster_id"`에 해당하는 인수를 넘기고, pooled cluster figure path는 기존 기본값 `cluster_id`를 계속 사용한다. 이렇게 하면 pooled figure 동작은 유지하면서 trial figure만 key-preserving label을 얻는다.

English: The fourth step is to adapt the trial-figure renderer in `src/synergy_stats/figures.py` to that structure. Right now `_render_component_grid()` uses only a `cluster_id` column as the row identity. In this revision, generalize that function so it accepts the row-identity column as an argument, and for the trial-figure path use `component_index` as the row identity while using `assigned_cluster_id` as a title-annotation display field. In practice, `save_trial_nmf_figure()` should call `_render_component_grid()` with arguments equivalent to `row_id_column="component_index"` and `cluster_annotation_column="assigned_cluster_id"`, while the pooled cluster figure path continues to use the default `cluster_id`. This preserves pooled figure behavior while giving the trial figure a key-preserving label.

한국어: 다섯 번째 단계는 Figure 05 validation을 W와 H 모두에 대해 강화하는 것이다. `_build_pooled_cluster_strategy_W_means()`와 `_build_pooled_cluster_strategy_H_means_long()` 자체를 직접 수정하지 않아도 될 가능성이 높다. join key가 복구되면 mean 계산도 정상화되기 때문이다. 대신 validation에서는 pooled `labels`와 pooled `minimal_W` 또는 pooled `minimal_H_long`의 inner join row count가 원본 row count와 일치하는지 확인해야 한다. 이는 “same component joins exactly once”를 관찰 가능한 방식으로 증명한다.

English: The fifth step is to strengthen Figure 05 validation for both W and H. It may not be necessary to edit `_build_pooled_cluster_strategy_W_means()` or `_build_pooled_cluster_strategy_H_means_long()` directly, because those means should normalize once the join key is repaired. However, validation must confirm that the inner-join row counts between pooled `labels` and pooled `minimal_W` or pooled `minimal_H_long` match the original row counts. This is the observable proof that each component joins exactly once.

한국어: 여섯 번째 단계는 rerun execution과 checksum validation을 현재 저장소의 실제 실행 방식에 맞추는 것이다. 실행 명령은 repo root에서 `conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py --source-parquet outputs/final_concatenated.parquet --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run --overwrite`로 고정한다. 이 스크립트가 완료되면 `checksums.md5`를 스스로 생성하므로, 계획서는 그 manifest가 새 artifact 집합을 반영하는지 검증하되 shell `md5sum`으로 덮어쓰지 않는다.

English: The sixth step is to align rerun execution and checksum validation with the repository’s real workflow. Fix the execution command to run from the repo root as `conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py --source-parquet outputs/final_concatenated.parquet --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run --overwrite`. When that script finishes, it already writes `checksums.md5`, so this plan validates that manifest against the new artifact set and does not overwrite it with a shell `md5sum` command.

## Concrete Steps / 구체적 실행 단계

한국어: 구현자는 아래 순서대로 진행한다. 각 단계는 같은 작업 디렉터리에서 다시 실행해도 안전해야 한다.

English: The implementer should proceed in the following order. Each step should be safe to rerun from the same working directory.

1. 한국어: 저장소 루트에서 현재 관련 파일과 line 위치를 다시 열어 수정 지점을 확인한다.
   English: From the repository root, reopen the affected files and confirm the exact edit locations.

      cd /home/alice/workspace/26-03-synergy-analysis
      nl -ba analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py | sed -n '300,335p'
      nl -ba src/synergy_stats/clustering.py | sed -n '936,1006p'
      nl -ba src/synergy_stats/figure_rerender.py | sed -n '403,430p'
      nl -ba src/synergy_stats/figures.py | sed -n '131,205p'
      nl -ba src/synergy_stats/artifacts.py | sed -n '280,340p'

2. 한국어: analysis-side reconstruction helper를 수정한다.
   English: Edit the analysis-side reconstruction helper.

      Working directory: /home/alice/workspace/26-03-synergy-analysis
      Change `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py` so the metadata copy excludes `component_index`.

3. 한국어: shared export helper를 harden한다.
   English: Harden the shared export helper.

      Working directory: /home/alice/workspace/26-03-synergy-analysis
      Change `src/synergy_stats/clustering.py` so metadata spread occurs before explicit row fields in `labels_df`, `minimal_w_rows`, and `minimal_h_rows`.

4. 한국어: trial figure input에 실제 cluster assignment를 join한다.
   English: Join the real cluster assignment into the trial-figure input.

      Working directory: /home/alice/workspace/26-03-synergy-analysis
      Update `src/synergy_stats/figure_rerender.py` so the per-trial `labels` rows are joined to `minimal_W` and `minimal_H_long` by `group_id`, `trial_id`, and `component_index`, producing a display column such as `assigned_cluster_id` instead of renaming `component_index`.

5. 한국어: trial figure renderer가 component identity와 assigned cluster를 함께 그리도록 수정한다.
   English: Update the trial-figure renderer so it displays both component identity and assigned cluster.

      Working directory: /home/alice/workspace/26-03-synergy-analysis
      Update `src/synergy_stats/figures.py` so trial figures render one row per `component_index` and title each row as `Component {component_index} (Cluster {assigned_cluster_id})` or an equivalent label. Preserve the pooled cluster figure path.

6. 한국어: rerun analysis를 다시 실행한다.
   English: Re-run the analysis.

      cd /home/alice/workspace/26-03-synergy-analysis
      python3 -m py_compile \
        analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
        src/synergy_stats/clustering.py \
        src/synergy_stats/figure_rerender.py \
        src/synergy_stats/figures.py

   한국어: 기대 결과는 syntax error 없이 종료되는 것이다.
   English: The expected result is that the command exits without a syntax error.

7. 한국어: rerun analysis를 다시 실행한다.
   English: Re-run the analysis.

      cd /home/alice/workspace/26-03-synergy-analysis
      conda run --no-capture-output -n cuda python \
        analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
        --source-parquet outputs/final_concatenated.parquet \
        --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run \
        --overwrite

8. 한국어: regenerated parquet에서 component key가 복구됐는지 확인한다.
   English: Confirm that the component key is restored in the regenerated parquet.

      cd /home/alice/workspace/26-03-synergy-analysis
      python3 - <<'PY'
      import polars as pl

      df = pl.read_parquet("analysis/first_zero_duplicate_k_rerun/artifacts/default_run/final_concatenated.parquet")
      for kind in ["labels", "minimal_W", "minimal_H_long"]:
          sub = df.filter(pl.col("artifact_kind") == kind)
          uniq = sub.get_column("component_index").drop_nulls().unique().sort().to_list()
          print(kind, uniq[:10], "count=", len(uniq))
      PY

   한국어: 기대 결과는 세 artifact 모두에서 `component_index`가 여러 값으로 나타나는 것이다.
   English: The expected result is that all three artifact kinds show multiple `component_index` values rather than a single collapsed value.

9. 한국어: pooled Figure 05 join cardinality를 검증한다.
   English: Validate the pooled Figure 05 join cardinality.

      cd /home/alice/workspace/26-03-synergy-analysis
      python3 - <<'PY'
      import polars as pl

      df = pl.read_parquet("analysis/first_zero_duplicate_k_rerun/artifacts/default_run/final_concatenated.parquet")
      labels = df.filter((pl.col("artifact_kind") == "labels") & (pl.col("group_id") == "pooled_step_nonstep"))
      minimal_w = df.filter((pl.col("artifact_kind") == "minimal_W") & (pl.col("group_id") == "pooled_step_nonstep"))
      minimal_h = df.filter((pl.col("artifact_kind") == "minimal_H_long") & (pl.col("group_id") == "pooled_step_nonstep"))
      keys = ["group_id", "trial_id", "component_index"]

      joined_w = minimal_w.join(labels.select(keys + ["cluster_id"]), on=keys, how="inner")
      joined_h = minimal_h.join(labels.select(keys + ["cluster_id"]), on=keys, how="inner")

      print("minimal_w_rows", minimal_w.height, "joined_w_rows", joined_w.height)
      print("minimal_h_rows", minimal_h.height, "joined_h_rows", joined_h.height)
      PY

   한국어: 기대 결과는 `joined_w_rows == minimal_w_rows`이고 `joined_h_rows == minimal_h_rows`인 것이다. 값이 더 크면 many-to-many contamination이 남아 있다는 뜻이다.
   English: The expected result is `joined_w_rows == minimal_w_rows` and `joined_h_rows == minimal_h_rows`. If either joined count is larger, many-to-many contamination is still present.

10. 한국어: Figure 04와 Figure 05를 나란히 검토한다.
   English: Review Figure 04 and Figure 05 side by side.

      Compare:
      - `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/concatenated/figures/04_pooled_cluster_representatives.png`
      - `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/concatenated/figures/05_within_cluster_strategy_overlay.png`

   한국어: 기대 결과는 Figure 05의 cluster 4 W mean이 더 이상 flat artifact처럼 보이지 않고, Figure 04의 representative W에서 보이는 dominant muscle pattern과 해석상 모순되지 않는 것이다. H panel도 과도한 평균화 흔적 없이 strategy별 shape 차이를 유지해야 한다.
   English: The expected result is that cluster 4 in Figure 05 no longer looks like a flat artifact and is no longer inconsistent with the dominant-muscle pattern visible in Figure 04. The H panel should also preserve strategy-specific shape differences rather than an over-averaged curve.

11. 한국어: trial figure를 검토한다.
    English: Review the trial figures.

      Confirm that a multi-component trial still renders one subplot row per component, that the row order follows `component_index`, and that each title shows both component identity and assigned cluster.

12. 한국어: workbook과 checksum manifest를 확인한다.
    English: Check the workbook and checksum manifest.

      Confirm that `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/concatenated/results_interpretation.xlsx` still contains the sheets `cluster_labels`, `minimal_W`, `minimal_H`, and `trial_windows`, and that those sheets still expose `trial_id`, `component_index`, and `cluster_id` where applicable. Also confirm that `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/checksums.md5` was regenerated by the script and contains the updated artifact paths.

## Validation and Acceptance / 검증 및 승인 기준

한국어: 이 revision은 아래 관찰 가능한 결과를 모두 만족해야 완료로 본다.

English: This revision is complete only if all of the following observable outcomes are satisfied.

- `labels`, `minimal_W`, `minimal_H_long`에서 같은 `trial_id` 아래 `component_index`가 `0, 1, 2, ...`처럼 구분된다.
- pooled `labels`와 pooled `minimal_W`의 inner join row count는 `minimal_W` 원본 row count와 같아야 한다.
- pooled `labels`와 pooled `minimal_H_long`의 inner join row count는 `minimal_H_long` 원본 row count와 같아야 한다.
- Figure 05의 W 패널은 Figure 04의 representative W 해석과 모순되지 않는다. 특히 기존 flat artifact로 보이던 cluster 4가 dominant-muscle pattern과 다시 연결되어야 한다.
- Figure 05의 H 패널은 cross-joined frame mean이 아니라 실제 cluster membership 기반 mean으로 계산되어야 한다.
- trial figure는 component 개수만큼 subplot row를 유지한다.
- trial figure의 각 제목 또는 subtitle은 `component_index`와 assigned `cluster_id`를 동시에 보여 준다.
- Figure 04 representative W/H는 control path이므로 의미 있는 변화가 없어야 한다. 의미 있는 변화가 보이면 regression으로 본다.
- rerun script가 생성한 `checksums.md5`가 새 artifact 집합을 반영해야 한다. 계획 수행 중 shell `md5sum`으로 해당 파일을 수동 덮어쓰지 않는다.
- `python3 -m py_compile analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py src/synergy_stats/clustering.py src/synergy_stats/figure_rerender.py src/synergy_stats/figures.py`가 syntax error 없이 통과해야 한다.

한국어: 구현 중 추가 자동 테스트가 들어가면, 그 명령과 기대 결과도 이 섹션에 후속 업데이트로 적는다.

English: If automated tests are added during implementation, their commands and expected outcomes must be added to this section as a follow-up update.

## Idempotence and Recovery / 반복 실행과 복구 방법

한국어: 주요 실행 경로는 `--overwrite` 기반 rerun이다. 같은 입력과 같은 output directory에 대해 반복 실행 가능해야 한다. 실행 도중 일부 artifact만 생성되고 실패하면, 같은 repo-root command를 다시 실행해 output directory 전체를 덮어쓰면 된다.

English: The main execution path is a rerun with `--overwrite`. It should be safe to repeat against the same inputs and output directory. If the run fails after creating only some artifacts, rerun the same repo-root command and let it overwrite the whole output directory again.

한국어: pre-fix와 post-fix 비교가 중요하므로, 구현 전에 `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/`를 side directory로 복사해 두는 편이 안전하다. 단, 비교용 복사본은 최종 정리 단계에서 더 이상 필요 없으면 제거한다.

English: Because pre-fix versus post-fix comparison matters here, it is safer to copy `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/` to a side directory before implementation. However, remove that comparison copy during final cleanup if it is no longer needed.

한국어: `src/` hardening은 additive change여야 한다. rerun fix만으로 artifact가 정상화되더라도 explicit-field precedence hardening은 유지하는 편이 재발 방지에 유리하다. 반대로 hardening이 rerun 범위를 넘어 production behavior를 바꾸는 것으로 보이면, 그 영향은 이 문서의 `Decision Log`와 `Surprises & Discoveries`에 기록하고 사용자와 다시 맞춘다.

English: The `src/` hardening must remain additive. Even if the rerun fix alone restores the artifacts, preserving explicit-field precedence is valuable for preventing recurrence. If that hardening appears to change production behavior beyond the rerun scope, record the impact in `Decision Log` and `Surprises & Discoveries` and re-align with the user before proceeding.

## Artifacts and Notes / 산출물과 메모

한국어: 현재까지 확인된 핵심 증거는 아래와 같다.

English: The key evidence confirmed so far is below.

- rerun artifact `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/final_concatenated.parquet`
  - `labels`, `minimal_W`, `minimal_H_long`의 `component_index`가 모두 `0`으로 무너져 있었다.
  - Figure 05 cluster 4는 representative W와 모순되는 flat pattern으로 보였다.

- baseline artifact `outputs/final_concatenated.parquet`
  - `labels`, `minimal_W`, `minimal_H_long`의 `component_index`가 `0..6`으로 유지된다.
  - 따라서 대규모 pipeline refactor는 필요하지 않고, rerun reconstruction bug와 export hardening이 핵심 범위다.

- H contamination proof
  - 한 trial 기준으로 `minimal_H_long` 700행과 `labels` 7행의 join이 4,900행으로 불어나는 예시를 확인했다.
  - 이것은 frame당 49 row가 생기는 many-to-many contamination이다.

- trial figure rendering caveat
  - 현재 rerender path는 trial `minimal_*` row에서 `component_index`를 `cluster_id`로 rename하는 shortcut을 사용한다.
  - 따라서 이번 revision은 실제 `labels` join을 통해 assigned cluster를 별도 display field로 공급해야 한다.

한국어: 구현 후에는 여기에 실제 command output 일부, 전후 checksum note, figure observation memo를 짧게 추가한다.

English: After implementation, extend this section with short command-output excerpts, before/after checksum notes, and concise figure-observation notes.

## Interfaces and Dependencies / 인터페이스와 의존성

한국어: 이 revision은 새로운 라이브러리를 추가하지 않는다. 기존 Python, polars, pandas, numpy, matplotlib 경로 안에서 끝내야 한다. public contract도 가능하면 유지한다. `scan_first_zero_duplicate_k()`의 입력 타입, `build_group_exports()`의 반환 frame key, rerun script CLI 인수 형식은 바꾸지 않는다. 필요한 변경은 metadata precedence, trial figure data join, trial figure labeling에 국한한다.

English: This revision introduces no new libraries. It must stay within the existing Python, polars, pandas, numpy, and matplotlib stack. Preserve public contracts wherever possible. Do not change the input type of `scan_first_zero_duplicate_k()`, the returned frame keys of `build_group_exports()`, or the rerun script CLI shape. The required changes are limited to metadata precedence, trial-figure data joining, and trial-figure labeling.

한국어: 구현이 끝난 시점에는 다음 조건이 참이어야 한다.

English: By the end of implementation, the following conditions must be true.

- `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`의 `_rebuild_feature_rows()`는 `component_index`를 `bundle.meta`에 저장하지 않는다.
- `src/synergy_stats/clustering.py`의 export row builders는 explicit component fields가 metadata보다 우선한다.
- `src/synergy_stats/figure_rerender.py`는 trial figure input을 만들 때 `labels`에서 실제 `component_index -> cluster_id` mapping을 join한다.
- `src/synergy_stats/figures.py`의 trial figure path는 `component_index`를 row identity로 유지하면서 assigned cluster를 표시한다.
- regenerated rerun artifact에서 `component_index`는 trial 내부 component 구분 key로 다시 사용할 수 있다.
- script-generated `checksums.md5`는 rerun output을 반영하고, 수동 shell overwrite 없이 그대로 검증된다.

## Revision Note / 개정 메모

한국어: 2026-03-20 10:35Z에 이 문서를 다시 개정했다. 이전 개정본은 direct bug와 hardening 범위는 잘 잡았지만, trial figure가 실제 cluster assignment를 어디서 가져오는지 문서화하지 않았고, Figure 05 H contamination을 unique-value spot check만으로 검증하게 적었으며, checksum 파일을 shell `md5sum`으로 다시 덮어쓰게 했다. 이번 개정은 이 세 가지 실행 리스크를 제거하고, repo-root rerun command와 script-generated checksum flow를 기준 경로로 고정하기 위해 작성되었다.

English: This document was revised again at 2026-03-20 10:35Z. The previous revision correctly separated the direct bug from the hardening scope, but it did not document where trial figures obtain the real cluster assignment, it validated Figure 05 H contamination too weakly with only a unique-value spot check, and it instructed the implementer to overwrite the checksum file with a shell `md5sum` command. This revision removes those three execution risks and fixes the repo-root rerun command plus script-generated checksum flow as the canonical path.
