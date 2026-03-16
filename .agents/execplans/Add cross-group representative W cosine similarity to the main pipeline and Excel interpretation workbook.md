# Add cross-group representative W cosine similarity to the main pipeline and Excel interpretation workbook / 메인 파이프라인과 해석용 엑셀 워크북에 cross-group representative W cosine similarity 추가

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository contains `.agents/PLANS.md` guidance in the project tool bundle, and this document must be maintained in that spirit. This plan is written for a novice who only has the current working tree and this file.

이 ExecPlan은 살아 있는 문서다. 작업이 진행되면 `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective` 섹션을 계속 갱신해야 한다.

이 저장소 작업 방식은 프로젝트 도구 번들 안의 `.agents/PLANS.md` 지침을 따른다고 가정한다. 이 문서는 현재 워킹 트리와 이 파일만 가진 초보자도 그대로 따라갈 수 있게 작성한다.

## Purpose / Big Picture

After this change, the main pipeline will still cluster `global_step` and `global_nonstep` separately, but it will also compute a cross-group similarity layer after clustering. A user will be able to run the existing pipeline once and then inspect two new CSV files and several new Excel sheets that answer one practical question: which step clusters and non-step clusters share a similar muscle-weight pattern (`same_synergy`), and which clusters remain `group_specific_synergy`.

The observable behavior is simple. After running the pipeline, the run folder must contain a unique pairwise cosine table for all step-vs-nonstep representative `W` combinations, a one-row-per-cluster decision table, and new sheets inside `results_interpretation.xlsx` that show the long table, a matrix view, the final cluster decision, and a short human-readable summary. No new “different pair” artifact will be created. Clusters that fail the cosine threshold remain `group_specific_synergy`, but their cosine values must still be preserved.

이 변경이 끝나면 메인 파이프라인은 지금처럼 `global_step`과 `global_nonstep`을 따로 clustering한 뒤, 그 결과 위에 cross-group similarity 레이어를 추가로 계산한다. 사용자는 기존 파이프라인을 한 번만 실행해도, 새 CSV 2개와 엑셀 시트 몇 개를 통해 다음 질문에 답할 수 있어야 한다. “step cluster와 non-step cluster 중 어떤 것은 같은 근육 가중치 패턴(`same_synergy`)을 공유하고, 어떤 것은 각 전략에 특이적인 `group_specific_synergy`인가?”

눈으로 확인할 수 있는 결과는 단순하다. 파이프라인 실행 후 런 디렉터리에 모든 step-vs-nonstep representative `W` 조합의 cosine 값을 한 번씩만 담은 pairwise CSV가 생기고, cluster당 정확히 1행만 갖는 최종 decision CSV가 생기며, `results_interpretation.xlsx` 안에는 long table, matrix view, 최종 decision, 짧은 요약을 보여주는 새 시트가 추가되어야 한다. 별도의 “different pair” 산출물은 만들지 않는다. 임계값에 못 미친 cluster는 `group_specific_synergy`로 남기되, cosine 값은 보존해야 한다.

## Progress

- [x] (2026-03-16 01:49Z) User requirements finalized: compare representative `W`, use cosine similarity, keep assignment, classify only `same_synergy` and `group_specific_synergy`, keep cosine values, avoid duplicate CSV content, and extend Excel output.
- [x] (2026-03-16 01:49Z) Repository orientation completed from current public README and main orchestrator structure.
- [x] (2026-03-16 02:05Z) Implemented `src/synergy_stats/cross_group_similarity.py` with representative `W` matrix building, pairwise cosine computation, Hungarian assignment, pairwise annotation, cluster decision construction, matrix view generation, and summary generation.
- [x] (2026-03-16 02:08Z) Wired the new computation into `src/synergy_stats/artifacts.py` so the feature runs after representative `W` export and writes exactly two new CSV artifacts.
- [x] (2026-03-16 02:09Z) Added `cross_group_w_similarity` configuration to both `configs/synergy_stats_config.yaml` and `tests/fixtures/synergy_stats_config.yaml`.
- [x] (2026-03-16 02:11Z) Extended `results_interpretation.xlsx` generation in `src/synergy_stats/excel_results.py` with `cross_group_pairwise`, `cross_group_matrix`, `cross_group_decision`, and `cross_group_summary` sheets plus `table_guide` registration.
- [x] (2026-03-16 02:13Z) Added focused unit coverage in `tests/test_synergy_stats/test_cross_group_similarity.py` and updated workbook/end-to-end expectations in existing contract tests.
- [x] (2026-03-16 02:15Z) Ran targeted pytest coverage: `tests/test_synergy_stats/test_cross_group_similarity.py`, `tests/test_synergy_stats/test_excel_audit.py`, and `tests/test_synergy_stats -k 'not fixture_run_writes_global_group_artifacts'`.
- [~] (2026-03-16 02:16Z) Ran fixture-style pipeline validation with a temporary `sklearn_nmf` + `sklearn_kmeans` config because the local `module` env lacks `torch`. The new CSV files and workbook sheets were created as expected, but curated MD5 comparison did not stay byte-stable under the temporary sklearn fallback because cluster labels swapped across repeated runs.
- [x] (2026-03-16 02:17Z) Updated this ExecPlan with actual implementation and validation evidence.

## Surprises & Discoveries

- Observation: The public README documents execution examples with conda env `cuda`, but the local project rule in the tool bundle says to use conda env `module`.
  Evidence: Project-local AGENTS guidance says “Use conda env `module`,” while README examples show `conda run -n cuda ...`.
- Observation: The current pipeline already exports all representative `W` and `H` artifacts and already creates `results_interpretation.xlsx`, so the least risky change is to add a post-clustering comparison layer rather than rewriting clustering itself.
  Evidence: Existing outputs already include `all_representative_W_posthoc.csv`, `all_representative_H_posthoc_long.csv`, and `results_interpretation.xlsx`.
- Observation: The user explicitly rejected a `different_synergy pair` artifact. The final classification vocabulary must therefore stay binary at the cluster level: `same_synergy` or `group_specific_synergy`.
  Evidence: User decision in this conversation.
- Observation: The local `module` conda environment does not currently provide `torch`, so the existing fixture end-to-end test path that uses `torchnmf` fails before export logic runs.
  Evidence: `tests/test_synergy_stats/test_end_to_end_contract.py -q` failed in `scripts/emg/03_extract_synergy_nmf.py` with `ModuleNotFoundError: No module named 'torch'`.
- Observation: Under the temporary sklearn fallback used only for validation, repeated fixture-style runs produced stable schemas and the expected new artifacts, but not stable MD5s for some curated CSVs because cluster IDs swapped between repeated runs.
  Evidence: `scripts/emg/99_md5_compare_outputs.py` reported diffs in `all_cluster_labels.csv`, `all_clustering_metadata.csv`, `all_representative_H_posthoc_long.csv`, and `all_representative_W_posthoc.csv`, and row inspection showed label permutation rather than schema drift.

## Decision Log

- Decision: The comparison target is representative `W`, not minimal-unit trial `W`, and not `H`.
  Rationale: The research question is about whether the final representative synergy families overlap between step and non-step under the same perturbation intensity. This also matches the current pipeline architecture.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: The step and non-step clustering logic will remain unchanged.
  Rationale: The repository already clusters `global_step` and `global_nonstep` separately. Cross-group comparison must sit after clustering so that current selection, NMF, and clustering behavior remain stable.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Matching will use full 1:1 linear assignment on all pairwise cosine values first, then thresholding will be applied to the assigned pairs.
  Rationale: This exactly matches the user’s rule: an assigned pair with cosine `>= 0.8` becomes `same_synergy`; an assigned pair with cosine `< 0.8` does not become a “different pair” and both clusters instead become `group_specific_synergy`.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Final cluster labels will be only `same_synergy` and `group_specific_synergy`.
  Rationale: This simplifies downstream interpretation and matches the user’s requested biological story.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Duplicate CSV content will be minimized by producing exactly two new CSV files.
  Rationale: One file will hold all unique pairwise combinations. One file will hold one final decision row per cluster. Matrix presentation will exist only in Excel, not as an extra CSV.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: Cosine values must be preserved even for `group_specific_synergy`.
  Rationale: The user explicitly requested that cosine similarity values remain available. The decision table will therefore retain assigned and/or best-partner cosine values.
  Date/Author: 2026-03-16 / ChatGPT

## Outcomes & Retrospective

Implementation completed as an additive export-layer feature. The clustering path remains unchanged, while the run output now gains two new CSV artifacts:

    cross_group_w_pairwise_cosine.csv
    cross_group_w_cluster_decision.csv

and four new interpretation workbook sheets:

    cross_group_pairwise
    cross_group_matrix
    cross_group_decision
    cross_group_summary

The strongest automated evidence is:

- `tests/test_synergy_stats/test_cross_group_similarity.py -q` passed.
- `tests/test_synergy_stats/test_excel_audit.py -q` passed.
- `tests/test_synergy_stats -k 'not fixture_run_writes_global_group_artifacts' -q` passed.
- A temporary fixture-style pipeline run using `sklearn_nmf` + `sklearn_kmeans` produced the new CSV files, a 4-row decision table, a 4-row pairwise table with unique `(step_cluster_id, nonstep_cluster_id)` pairs, and the expected new workbook sheets.

Known validation limit:

- The repository’s fixture end-to-end test still fails in the local `module` env before export because `torchnmf` requires `torch`, which is not installed there.
- The fallback sklearn validation run was enough to verify the new export/workbook feature path, but curated MD5 stability could not be demonstrated under sklearn because cluster labels permuted across repeated runs.

구현은 “가산적 export 기능”으로 마무리했다. clustering 로직은 그대로 두고, 런 결과에 CSV 2개와 해석용 엑셀 시트 4개를 추가했다.

남은 한계도 분명하다. 현재 로컬 `module` 환경에는 `torch`가 없어서 기존 fixture end-to-end 경로는 export 단계 전에 멈춘다. 그래서 기능 경로 자체는 임시 sklearn 검증 설정으로 확인했고, 새 artifact 생성과 workbook 확장은 검증했다. 다만 이 fallback 경로에서는 cluster label permutation 때문에 curated MD5 byte stability까지는 확보하지 못했다.

## Context and Orientation

The repository entry point is `main.py`. It loads YAML configuration, prepares the runtime output directory, and executes these fixed wrapper steps in order:

    scripts/emg/01_load_emg_table.py
    scripts/emg/02_extract_trials.py
    scripts/emg/03_extract_synergy_nmf.py
    scripts/emg/04_cluster_synergies.py
    scripts/emg/05_export_artifacts.py

The current architecture matters because this feature must be added after the step and non-step clusters already exist. Do not move the feature into trial extraction or NMF extraction. Do not merge step and non-step before clustering. Do not change `04_cluster_synergies.py` selection semantics.

In this repository, “representative `W`” means the muscle-weight pattern of a representative synergy cluster. Each cluster is stored in long format by muscle name and weight value. `H` is a time profile and is not part of this feature. “Pairwise cosine table” means one row per `(step cluster, nonstep cluster)` combination. “Decision table” means one final row per cluster, not one row per pair. “Assignment” means 1:1 matching between step clusters and non-step clusters, chosen to minimize total cost, where cost is `1 - cosine_similarity`.

이 저장소의 진입점은 `main.py`다. 이 파일은 YAML 설정을 읽고, 출력 디렉터리를 준비한 뒤, 아래 래퍼 스크립트를 순서대로 실행한다.

    scripts/emg/01_load_emg_table.py
    scripts/emg/02_extract_trials.py
    scripts/emg/03_extract_synergy_nmf.py
    scripts/emg/04_cluster_synergies.py
    scripts/emg/05_export_artifacts.py

이 구조가 중요한 이유는, 이번 기능이 step/non-step cluster가 이미 만들어진 뒤에 붙어야 하기 때문이다. 이 기능을 trial 절단이나 NMF 추출 단계로 옮기지 마라. step과 non-step을 clustering 전에 섞지 마라. `04_cluster_synergies.py`의 selection semantics도 바꾸지 마라.

이 저장소에서 “representative `W`”는 대표 synergy cluster의 근육 가중치 패턴을 뜻한다. 각 cluster는 muscle 이름과 weight 값을 갖는 long format으로 저장된다. `H`는 시간 프로파일이며 이번 기능 대상이 아니다. “Pairwise cosine table”은 `(step cluster, nonstep cluster)` 조합마다 한 행을 갖는 테이블이다. “Decision table”은 pair당 1행이 아니라 cluster당 최종 1행을 갖는 테이블이다. “Assignment”는 step cluster와 non-step cluster 사이의 1:1 매칭이며, cost=`1 - cosine_similarity`를 최소화하는 방식이다.

The most relevant files for this change are:

    main.py
    configs/synergy_stats_config.yaml
    scripts/emg/05_export_artifacts.py
    src/synergy_stats/artifacts.py
    src/synergy_stats/excel_results.py
    src/synergy_stats/__init__.py
    tests/test_synergy_stats/test_end_to_end_contract.py
    tests/test_synergy_stats/test_clustering_contract.py

Create one new module:

    src/synergy_stats/cross_group_similarity.py

If `src/synergy_stats/excel_results.py` already defines hard-coded workbook sheet registrations, extend that registration instead of creating an ad-hoc writer somewhere else.

If workbook writing requires editing spreadsheet code, follow `/home/oai/skills/spreadsheets/SKILL.md`. Use the repository’s existing Python workbook path and `openpyxl`-style editing. Do not use LibreOffice or any GUI spreadsheet tool.

워크북 로직을 고쳐야 한다면 `/home/oai/skills/spreadsheets/SKILL.md` 규칙을 따른다. 저장소의 기존 Python 기반 워크북 생성 경로와 `openpyxl` 방식 편집을 유지하고, LibreOffice나 GUI 스프레드시트 도구는 사용하지 마라.

## Plan of Work

### 1. Add a new YAML configuration block

Edit `configs/synergy_stats_config.yaml` and add a new top-level block or the closest existing section that logically owns export-time comparison settings.

Required keys:

    cross_group_w_similarity:
      enabled: true
      metric: cosine
      threshold: 0.8
      assignment: linear_sum_assignment
      output_pairwise_csv: true
      output_cluster_decision_csv: true
      output_excel_sheets: true

Do not add user-facing options that are not required by this feature. The threshold is fixed by user decision and must default to `0.8`.

### 2. Create a dedicated computation module

Create `src/synergy_stats/cross_group_similarity.py`.

This module must be small and explicit. It should not know anything about raw EMG time series. Its job is to receive representative `W` rows and return comparison artifacts.

Define these functions with stable names:

    build_cluster_w_matrix(rep_w_long, muscle_order) -> tuple[step_df, nonstep_df]

This function takes long-format representative `W` rows and returns one row per cluster for `global_step` and `global_nonstep`. Each row must contain `group_id`, `cluster_id`, and one numeric column per muscle in a fixed muscle order from config.

The function must defensively L2-normalize each cluster vector even if the upstream export already normalized it. This is an idempotent safety step.

    compute_pairwise_cosine(step_df, nonstep_df) -> pandas.DataFrame | polars.DataFrame

Return a long table with exactly one row per `(step_cluster_id, nonstep_cluster_id)` pair. Include:

    step_cluster_id
    nonstep_cluster_id
    cosine_similarity

You may include `step_group_id` and `nonstep_group_id`, but because the groups are fixed, keep the schema minimal.

    solve_assignment(pairwise_df) -> pandas.DataFrame | polars.DataFrame

Build a rectangular cosine matrix, convert it to a cost matrix with `1 - cosine_similarity`, and solve 1:1 assignment across all currently available step and non-step clusters. Return only the assigned edges:

    step_cluster_id
    nonstep_cluster_id
    assigned_cosine_similarity

Do not threshold inside this function. Thresholding comes later because the user explicitly wants assignment first, interpretation second.

    build_cluster_decision(step_df, nonstep_df, pairwise_df, assigned_df, threshold) -> pandas.DataFrame | polars.DataFrame

Return one final row per cluster. This is the most important table in the feature.

Required columns:

    group_id
    cluster_id
    final_label
    match_id
    assigned_partner_cluster_id
    assigned_cosine_similarity
    best_partner_cluster_id
    best_partner_cosine_similarity

Interpretation rules are strict:

1. If a cluster belongs to an assigned pair and the assigned cosine is `>= threshold`, then both clusters get:
   `final_label = "same_synergy"`
   and they share the same `match_id`.

2. If a cluster belongs to an assigned pair and the assigned cosine is `< threshold`, then:
   `final_label = "group_specific_synergy"`
   `assigned_partner_cluster_id` stays filled
   `assigned_cosine_similarity` stays filled
   `match_id` must be null
   and there is no “different pair” artifact.

3. If a cluster is not assigned because the cost matrix is rectangular and the opposite side has fewer clusters, then:
   `final_label = "group_specific_synergy"`
   `assigned_partner_cluster_id` is null
   `assigned_cosine_similarity` is null
   but `best_partner_cluster_id` and `best_partner_cosine_similarity` must still be filled from the pairwise table whenever an opposite-side cluster exists.

4. If one side is empty, fail loudly before writing artifacts. This should already fail earlier in the pipeline, so treat it as a defensive error path.

### 3. Integrate the new module into export time, not cluster time

Edit `scripts/emg/05_export_artifacts.py` and/or `src/synergy_stats/artifacts.py`, depending on how the current repository organizes export orchestration.

The new feature must run after representative `W` artifacts are already available in memory or can be constructed from the same export-time inputs. Do not re-run clustering. Do not read CSVs back from disk just to compute this result if the same data is already available in memory.

Preferred flow:

1. Build or reuse the aggregate representative `W` long table.
2. Pass it into `build_cluster_w_matrix(...)`.
3. Compute `pairwise_df`.
4. Compute `assigned_df`.
5. Compute `cluster_decision_df`.
6. Write the two new CSV files.
7. Hand all three data objects to the Excel workbook writer.

### 4. Produce exactly two new CSV files and no duplicate matrix CSV

Write these files in the run root, next to the existing `all_*.csv` artifacts:

    cross_group_w_pairwise_cosine.csv
    cross_group_w_cluster_decision.csv

The pairwise file is the canonical machine-readable edge table. It must contain every unique step-vs-nonstep combination exactly once. Never write the reverse direction again.

Add these optional helper columns to `cross_group_w_pairwise_cosine.csv` so that downstream users can trace assignment without a separate pair file:

    selected_in_assignment
    passes_threshold
    match_id

Rules for these helper columns:

- `selected_in_assignment = true` only for assigned edges.
- `passes_threshold = true` only when an assigned edge has cosine `>= 0.8`.
- `match_id` is filled only for assigned edges that pass threshold.

Do not write these additional CSV files:

    cross_group_w_same_synergy_pairs.csv
    cross_group_w_different_pairs.csv
    cross_group_w_matrix.csv
    cross_group_w_summary.csv

Those would duplicate information already present in the canonical pairwise and decision tables.

### 5. Extend the Excel interpretation workbook

Edit `src/synergy_stats/excel_results.py` or the existing workbook writer path used by `results_interpretation.xlsx`.

Add these sheets:

    cross_group_pairwise
    cross_group_matrix
    cross_group_decision
    cross_group_summary

Sheet intent:

- `cross_group_pairwise`: the long table from `cross_group_w_pairwise_cosine.csv`, rendered as an Excel Table.
- `cross_group_matrix`: a pivoted matrix view with step clusters on rows, non-step clusters on columns, values = cosine similarity.
- `cross_group_decision`: the one-row-per-cluster final decision table.
- `cross_group_summary`: a short human-readable sheet showing at least:
  number of step clusters
  number of non-step clusters
  number of accepted same-synergy matches
  number of group-specific step clusters
  number of group-specific non-step clusters
  threshold used

Also extend the workbook `table_guide` sheet so a human reader can understand the new sheets without reading source code.

엑셀 시트 의미는 다음과 같다.

- `cross_group_pairwise`: `cross_group_w_pairwise_cosine.csv`의 long table을 Excel Table로 그대로 보여준다.
- `cross_group_matrix`: 행=step cluster, 열=non-step cluster, 값=cosine similarity인 matrix view다.
- `cross_group_decision`: cluster당 최종 1행만 갖는 decision table이다.
- `cross_group_summary`: 사람 읽기용 짧은 요약 시트다. 최소한 다음 값을 넣는다.
  step cluster 개수
  non-step cluster 개수
  수용된 same-synergy match 개수
  group-specific step cluster 개수
  group-specific non-step cluster 개수
  사용한 threshold

### 6. Keep existing schemas stable unless the added feature requires otherwise

Do not rename or remove existing artifacts such as:

    final_summary.csv
    all_clustering_metadata.csv
    all_trial_window_metadata.csv
    all_cluster_labels.csv
    all_representative_W_posthoc.csv
    all_representative_H_posthoc_long.csv
    results_interpretation.xlsx

Do not add the cross-group result into `outputs/final.parquet` unless the current export code architecture absolutely requires it. This feature is interpretive and cluster-level, not a minimal-unit reuse format.

### 7. Respect library and environment rules

Use `polars` before `pandas` when it is convenient for long-table manipulation. If the current workbook writer or export path already expects pandas objects, convert only at the boundary.

Use conda env `module` for local implementation commands because the local project rule overrides the older public README examples.

For spreadsheet work, follow the spreadsheet skill guidance. Use Python-based workbook editing only.

### 8. Add focused tests

Create:

    tests/test_synergy_stats/test_cross_group_similarity.py

This test file must include at least three cases.

Case A: clean same-synergy match.
Use a tiny toy matrix where two assigned pairs both exceed `0.8`.
Expect:
- pairwise table has all combinations exactly once
- cluster decision table has only `same_synergy`
- both accepted pairs share non-null `match_id`s

Case B: assigned below threshold becomes group-specific.
Use a toy matrix where assignment exists but one assigned edge is `< 0.8`.
Expect:
- that edge is still marked `selected_in_assignment = true` in pairwise
- `passes_threshold = false`
- both clusters become `group_specific_synergy`
- no `match_id` is created for that pair

Case C: rectangular cluster count leaves one cluster unmatched.
Use more step clusters than non-step clusters.
Expect:
- unmatched side gets `group_specific_synergy`
- `assigned_partner_cluster_id` is null
- `best_partner_cosine_similarity` is preserved

Then update:

    tests/test_synergy_stats/test_end_to_end_contract.py

Add fixture-run assertions for:

    cross_group_w_pairwise_cosine.csv exists
    cross_group_w_cluster_decision.csv exists
    results_interpretation.xlsx contains the four new sheets

Only update `tests/test_synergy_stats/test_clustering_contract.py` if workbook or artifact registration changes require it.

### 9. MD5 and regression discipline

Inspect:

    scripts/emg/99_md5_compare_outputs.py

If the comparator only checks a curated set of existing stable outputs, preserve that behavior and verify that those existing outputs still match.

If the comparator automatically picks up every CSV in the run root, then extend it carefully so that the new files are included intentionally, regenerate the reference baseline once, and document that change in this ExecPlan.

The preferred outcome is additive behavior: old tracked files remain byte-stable when possible, new files are the only additions.

## Concrete Steps

Work from repository root.

1. Read the relevant files before editing.

    conda run -n module python - <<'PY'
    from pathlib import Path
    files = [
        "main.py",
        "configs/synergy_stats_config.yaml",
        "scripts/emg/05_export_artifacts.py",
        "src/synergy_stats/artifacts.py",
        "src/synergy_stats/excel_results.py",
        "tests/test_synergy_stats/test_end_to_end_contract.py",
        "scripts/emg/99_md5_compare_outputs.py",
    ]
    for f in files:
        p = Path(f)
        print(f"\n===== {f} =====")
        print(p.exists())
    PY

2. Implement the new module and wiring.

    conda run -n module python -m pytest tests/test_synergy_stats/test_cross_group_similarity.py -q

At first this test should fail because the new module does not yet exist. After implementation it should pass.

3. Run the fixture pipeline.

    conda run -n module python main.py \
      --config tests/fixtures/global_config.yaml \
      --out outputs/runs/fixture_run \
      --overwrite

Expected high-level result:
- pipeline exits successfully
- run directory exists
- the two new CSV files exist
- `results_interpretation.xlsx` exists and includes four new sheets

4. Run the full relevant test suite.

    conda run -n module python -m pytest tests/test_synergy_stats -q

5. Run MD5 comparison.

    conda run -n module python main.py \
      --config tests/fixtures/global_config.yaml \
      --out tests/reference_outputs/reference_baseline \
      --overwrite

    conda run -n module python main.py \
      --config tests/fixtures/global_config.yaml \
      --out outputs/runs/fixture_run \
      --overwrite

    conda run -n module python scripts/emg/99_md5_compare_outputs.py \
      --base tests/reference_outputs/reference_baseline \
      --new outputs/runs/fixture_run

Interpretation:
- Best case: existing tracked files match and only new files are additive.
- Acceptable fallback: if the comparator intentionally tracks all run-root CSV files, update the comparator and baseline once, then rerun until it passes.

## Validation and Acceptance

The feature is accepted only if all of the following are true.

1. Running the fixture pipeline produces:

    outputs/runs/fixture_run/cross_group_w_pairwise_cosine.csv
    outputs/runs/fixture_run/cross_group_w_cluster_decision.csv
    outputs/runs/fixture_run/results_interpretation.xlsx

2. `cross_group_w_pairwise_cosine.csv` contains every `(step_cluster_id, nonstep_cluster_id)` pair exactly once, with no reverse-duplicate rows.

3. `cross_group_w_cluster_decision.csv` contains exactly one row per cluster from both groups combined.

4. The only final labels in `cross_group_w_cluster_decision.csv` are:

    same_synergy
    group_specific_synergy

5. Every cluster has at least one preserved cosine value:
- assigned clusters preserve `assigned_cosine_similarity`
- unassigned clusters preserve `best_partner_cosine_similarity` whenever the opposite group exists

6. The workbook `results_interpretation.xlsx` contains:

    cross_group_pairwise
    cross_group_matrix
    cross_group_decision
    cross_group_summary

7. Existing pipeline steps and existing clustering semantics remain unchanged.

8. Relevant pytest tests pass.

9. MD5 verification is completed and documented.

## Idempotence and Recovery

The implementation steps are additive and safe to rerun. Re-running the pipeline with `--overwrite` is the normal recovery path.

If workbook sheet creation fails halfway, delete only the broken run directory and rerun the pipeline. Do not manually patch generated xlsx files by hand.

If tests fail after partial edits, do not roll back unrelated files. Fix forward. The local project rule explicitly forbids reverting code that you did not modify yourself.

이 계획은 여러 번 다시 실행해도 안전하도록 설계했다. 파이프라인 재실행은 `--overwrite`를 사용하는 것이 정상 복구 경로다.

엑셀 시트 생성이 중간에 실패하면 깨진 런 디렉터리만 지우고 파이프라인을 다시 돌려라. 생성된 xlsx를 수동으로 뜯어고치지 마라.

부분 수정 뒤 테스트가 실패해도, 내가 직접 수정하지 않은 다른 파일을 되돌리지 마라. 앞으로 고치는 방식으로 해결한다.

## Artifacts and Notes

Expected new artifact names:

    cross_group_w_pairwise_cosine.csv
    cross_group_w_cluster_decision.csv

Expected key columns in pairwise CSV:

    step_cluster_id
    nonstep_cluster_id
    cosine_similarity
    selected_in_assignment
    passes_threshold
    match_id

Expected key columns in decision CSV:

    group_id
    cluster_id
    final_label
    match_id
    assigned_partner_cluster_id
    assigned_cosine_similarity
    best_partner_cluster_id
    best_partner_cosine_similarity

Example interpretation:

    If step cluster 1 is assigned to non-step cluster 2 with cosine 0.84,
    then both rows in the decision CSV are labeled same_synergy and share the same match_id.

    If step cluster 3 is assigned to non-step cluster 0 with cosine 0.73,
    then both rows remain group_specific_synergy, match_id is null,
    but assigned_partner_cluster_id and assigned_cosine_similarity stay visible.

    If step cluster 4 has no assigned partner because the non-step side has fewer clusters,
    then it is group_specific_synergy, assigned fields are null,
    but best_partner_cluster_id and best_partner_cosine_similarity should still show the closest opposite-side cluster.

## Interfaces and Dependencies

Define in `src/synergy_stats/cross_group_similarity.py`:

    def build_cluster_w_matrix(rep_w_long, muscle_order):
        ...

    def compute_pairwise_cosine(step_df, nonstep_df):
        ...

    def solve_assignment(pairwise_df):
        ...

    def build_cluster_decision(step_df, nonstep_df, pairwise_df, assigned_df, threshold):
        ...

If the repository already has an artifact bundle or aggregate frame registry, return these new tables through that registry rather than inventing a second export path.

If the workbook writer registers sheet configs centrally, extend that registry with:

    cross_group_pairwise
    cross_group_matrix
    cross_group_decision
    cross_group_summary

Do not add a second workbook file. Extend `results_interpretation.xlsx`.

## Revision Note

Initial version of this ExecPlan created on 2026-03-16 to implement a post-clustering cross-group representative `W` cosine similarity layer with binary final labels (`same_synergy`, `group_specific_synergy`), preserved cosine values, non-duplicated CSV outputs, and Excel integration.
