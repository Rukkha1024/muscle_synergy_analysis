# ExecPlan: Analysis-only pooled step/nonstep synergy clustering in `analysis/`

## Source Notes

### Korean

이 계획은 아래 두 저장소 문서를 기준으로 작성한다. 첫째, 저장소 README는 현재 기본 방법론이 `platform_onset ~ analysis_window_end` 창을 사용하며, step trial은 실제 `step_onset`, nonstep trial은 같은 subject의 평균 step latency를 이용한 surrogate 종료점을 사용한다고 설명한다. 또한 trial-level NMF는 `VAF >= 0.90`로 rank를 고르고, global clustering은 현재 `global_step`과 `global_nonstep`을 분리해서 수행하며, K 선택은 gap statistic과 zero-duplicate constraint를 따른다고 적어 둔다.

둘째, `analysis/compare_professor/README.md`는 analysis 공간에서 별도 스크립트로 trial-level NMF를 다시 수행하고, 이벤트 기반 step/nonstep 라벨이 baseline의 `all_trial_window_metadata.csv`와 완전히 일치하는지 검증하는 선례를 보여 준다. 이번 작업도 같은 "analysis 전용 검증 실험" 패턴을 따른다.

셋째, 기존 파이프라인의 figure 생성 모듈 `src/synergy_stats/figures.py`는 cluster figure를 W bar chart(파란 `#5C7CFA`) + H line plot(초록 `#2F9E44`) 그리드 레이아웃으로 렌더링하며, matplotlib Agg backend, DPI 150, Korean font 지원, `bbox_inches="tight"` 설정을 공통 규칙으로 사용한다. 이번 pooled 분석의 figure도 동일한 시각적 규칙을 따른다.

### English

This plan is grounded in two repository documents. First, the repository README states that the default analysis window is `platform_onset ~ analysis_window_end`, where step trials end at the actual `step_onset` and nonstep trials end at a surrogate time computed from the subject's mean step latency. The same README also states that trial-level NMF rank is selected with `VAF >= 0.90`, that the current pipeline clusters `global_step` and `global_nonstep` separately, and that cluster count selection follows gap statistic plus a zero-duplicate constraint.

Second, `analysis/compare_professor/README.md` shows an established precedent for re-running trial-level NMF inside `analysis/` and validating that event-based step/nonstep labels exactly match the baseline `all_trial_window_metadata.csv`. This work will follow that same "analysis-only validation experiment" pattern.

Third, the existing pipeline figure module `src/synergy_stats/figures.py` renders cluster figures as W bar charts (blue `#5C7CFA`) + H line plots (green `#2F9E44`) in a grid layout, using matplotlib Agg backend, DPI 150, Korean font support, and `bbox_inches="tight"`. The pooled analysis figures will follow the same visual conventions.

## Purpose / 목적

### Korean

이 변경이 끝나면 사용자는 기존 파이프라인을 건드리지 않고 `analysis/` 안에서만 별도 스크립트를 실행하여, step과 nonstep에서 추출된 모든 시너지 구조 벡터 `W`를 한 번에 풀링한 뒤 공통 클러스터 공간을 만들 수 있다. 그 결과 사용자는 현재 파이프라인처럼 "step 대표 시너지"와 "nonstep 대표 시너지"를 서로 독립적으로 보는 대신, 같은 `cluster_id` 안에서 step과 nonstep이 얼마나 점유하는지, 몇 명의 subject에서 나타나는지, 그리고 같은 클러스터 안의 step 평균 `H`와 nonstep 평균 `H`가 어떻게 다른지를 직접 비교할 수 있게 된다.

이 계획의 목적은 구현보다 먼저 "무엇을 만들고 어떤 출력이 성공의 증거인지"를 초보자도 바로 따라 할 수 있게 적어 두는 것이다. 구현이 완료되면 사용자는 analysis 스크립트 하나를 실행하고, CSV 4개(`pooled_cluster_members.csv`, `pooled_cluster_summary.csv`, `pooled_representative_W.csv`, `pooled_representative_H_long.csv`), figure 6개, 그리고 `report.md`를 보고 pooled 해석이 성립하는지 판단할 수 있어야 한다.

### English

After this change, a user will be able to stay entirely inside `analysis/`, run one standalone script, pool all step and nonstep synergy structure vectors `W` into a single clustering space, and inspect them with a common cluster definition. Instead of treating "representative step synergies" and "representative nonstep synergies" as unrelated outputs, the user will be able to compare step occupancy, nonstep occupancy, subject coverage, and condition-specific representative `H` profiles within the same `cluster_id`.

The purpose of this plan is to define, before coding begins, exactly what will be built and what outputs will count as proof that it works. Once implementation is complete, a novice should be able to run one analysis script and evaluate the result by inspecting four CSVs (`pooled_cluster_members.csv`, `pooled_cluster_summary.csv`, `pooled_representative_W.csv`, `pooled_representative_H_long.csv`), six figures, and `report.md`.

## Progress / 진행 상황

- [x] (2026-03-15 02:30Z) User approved the v1 scope: analysis-only, no Phase 4, trial-level NMF re-extraction inside `analysis/`, pooled clustering for step+nonstep, and K selection by gap statistic plus zero-duplicate constraint.
- [x] (2026-03-15) User approved figure generation scope: 6 figures based on existing pipeline style + pooled-specific comparison figures.
- [x] (2026-03-15 11:40Z) Create `analysis/pooled_shared_specific_synergy/` and add the main analysis entrypoint.
- [x] (2026-03-15 11:45Z) Implement baseline metadata loading and validation against baseline trial window outputs.
- [x] (2026-03-15 11:50Z) Implement trial-level NMF re-extraction from pipeline-aligned inputs.
- [x] (2026-03-15 11:55Z) Implement pooled clustering with gap-statistic search and zero-duplicate selection.
- [x] (2026-03-15 12:00Z) Implement pooled summary outputs for occupancy, subject coverage, sub-centroid similarity, and representative `H`.
- [x] (2026-03-15 12:05Z) Generate 6 analysis figures (pooled clusters, step vs nonstep W, step vs nonstep H, occupancy summary, K selection diagnostic, sub-centroid similarity heatmap).
- [x] (2026-03-15 12:10Z) Write `report.md` and record all analysis assumptions and observed outputs.
- [x] (2026-03-15 12:20Z) Validation completed: `py_compile`, dry-run, full run, schema/file checks, and rerun MD5 comparison for required deliverables.

## Surprises & Discoveries / 발견 사항

### Korean

- Observation: 현재 저장소의 공식 파이프라인은 `global_step`과 `global_nonstep`을 서로 섞지 않고 별도 clustering 하므로, 같은 `cluster_id`를 조건 간에 직접 정렬된 공통 ID로 해석하면 안 된다.
  Evidence: README가 현재 grouping이 `global_step`과 `global_nonstep` 두 집단으로 고정되고, step과 nonstep의 같은 `cluster_id`를 직접 대응시키면 안 된다고 명시한다.

- Observation: analysis 공간에는 이미 "baseline을 유지한 채 별도 로직을 재실행하고 baseline label과 일치 여부를 검증하는" 작업 패턴이 존재한다.
  Evidence: `analysis/compare_professor/README.md`가 analysis 스크립트 안에서 NMF를 다시 수행하고 baseline `analysis_step_class`와 event 기반 라벨의 완전 일치를 확인한다고 적어 둔다.

- Observation: 기존 파이프라인의 figure 생성은 `src/synergy_stats/figures.py`의 `_render_component_grid()` 함수가 핵심이며, `save_group_cluster_figure()`가 global cluster figure를 W bar + H line 2열 그리드로 생성한다. DPI 150, Agg backend, Korean font(NanumGothic), `bbox_inches="tight"`가 공통 규칙이다.
  Evidence: `src/synergy_stats/figures.py` 코드 직접 확인.

### English

- Observation: The official pipeline currently clusters `global_step` and `global_nonstep` separately, so a matching `cluster_id` across conditions must not be interpreted as a shared cluster identity.
  Evidence: The README explicitly states that grouping is fixed to `global_step` and `global_nonstep`, and that the same `cluster_id` must not be directly matched between step and nonstep.

- Observation: There is already an analysis-space pattern for re-running logic without changing the baseline pipeline and for validating analysis labels against the baseline window metadata.
  Evidence: `analysis/compare_professor/README.md` states that it re-runs NMF in `analysis/` and checks exact agreement between baseline `analysis_step_class` and event-based labels.

- Observation: The existing pipeline figure generation centers on `_render_component_grid()` in `src/synergy_stats/figures.py`, with `save_group_cluster_figure()` producing global cluster figures as W bar + H line 2-column grids. DPI 150, Agg backend, Korean font (NanumGothic), and `bbox_inches="tight"` are the shared conventions.
  Evidence: Direct inspection of `src/synergy_stats/figures.py`.

- Observation: The active `module` environment did not guarantee the GPU-first stack required by the repository defaults (`torchnmf`, `torch_kmeans`) for a quick validation run.
  Evidence: The implementation added runtime fallback support and the validation run completed with `--nmf-backend sklearn_nmf --clustering-algorithm sklearn_kmeans`.

- Observation: User-facing pooled artifacts were deterministic across reruns, but `run_metadata.json` retained tiny floating-point differences in diagnostic fields.
  Evidence: `diff -u /tmp/dev_run_no_meta.md5 /tmp/dev_run_ref_no_meta.md5` returned no differences, while `run_metadata.json` changed only in low-magnitude floating-point diagnostic values.

## Decision Log / 의사결정 로그

- Decision: v1 will stop at descriptive pooled clustering outputs and will not include permutation tests, mixed models, residual-specific synergies, or shared-only reconstruction scoring.
  Rationale: The user explicitly requested to omit the former "Phase 4" discussion and first establish the pooled analysis outputs themselves.
  Date/Author: 2026-03-15 / User + GPT-5.2 Pro

- Decision: The analysis script will be created under `analysis/` and will not modify the existing `scripts/emg/*` pipeline.
  Rationale: The goal is to validate a new analytical interpretation without destabilizing the official pipeline outputs.
  Date/Author: 2026-03-15 / User + GPT-5.2 Pro

- Decision: Trial-level NMF will be re-extracted inside the analysis script using the same pipeline-aligned EMG parquet and event workbook semantics, and its trial selection will be validated against the baseline run's `all_trial_window_metadata.csv`.
  Rationale: This matches the existing `analysis/compare_professor` precedent and preserves analysis isolation while keeping trial definitions anchored to the baseline.
  Date/Author: 2026-03-15 / User + GPT-5.2 Pro

- Decision: Nonstep representative `H` will be derived from the same surrogate step window rule already used by the baseline methodology.
  Rationale: The repository's default method defines nonstep windows with a subject-specific surrogate step endpoint so that step and nonstep are compared on a matched time basis.
  Date/Author: 2026-03-15 / User + GPT-5.2 Pro

- Decision: Pooled clustering will ignore the step/nonstep label during fitting and will use the label only after clustering for summary and visualization.
  Rationale: The point of pooled clustering is to create one common cluster space first and then compare conditions inside that shared space.
  Date/Author: 2026-03-15 / User + GPT-5.2 Pro

- Decision: Cluster count selection will follow the current repository rule: gap statistic first, then the smallest `K` at or above the gap-based recommendation that has zero within-trial duplicates.
  Rationale: This preserves the current clustering philosophy while changing only the grouping from separate condition pools to one pooled set.
  Date/Author: 2026-03-15 / User + GPT-5.2 Pro

- Decision: 6 figures will be generated following existing pipeline visual conventions (W bar `#5C7CFA`, H line `#2F9E44`, DPI 150, Agg backend, Korean font) plus pooled-specific comparison layouts (step vs nonstep overlay, occupancy bar, K diagnostic, similarity heatmap).
  Rationale: The user requested figures based on existing pipeline style with additional pooled-analysis-specific comparison figures to support visual interpretation of condition differences.
  Date/Author: 2026-03-15 / User + Claude Opus 4.6

- Decision: The analysis entrypoint will support backend and search-count overrides so validation can complete even when the active environment is better suited to CPU sklearn paths than the default GPU-first configuration.
  Rationale: This keeps the analysis logic aligned with the ExecPlan while making end-to-end verification practical in the local `module` environment.
  Date/Author: 2026-03-15 / GPT-5 Codex

- Decision: `pooled_cluster_members.csv` will export only flat columns, while list-valued `w_vector` and `h_vector` stay in memory for summary and figure generation.
  Rationale: CSV output must remain Polars-compatible and novice-friendly; nested list columns blocked CSV export and were not required by the final deliverable contract.
  Date/Author: 2026-03-15 / GPT-5 Codex

## Outcomes & Retrospective / 기대 결과와 회고 기준

### Korean

이 계획이 성공적으로 구현되면, 사용자는 "step과 nonstep이 정말 다른 `W` 구조를 쓰는가, 아니면 공통 `W`를 다른 비율과 다른 시간 패턴으로 recruit하는가"를 현재 파이프라인보다 더 직접적으로 확인할 수 있어야 한다. 성공의 기준은 통계적 유의성 검정이 아니라, 먼저 공통 클러스터 공간이 안정적으로 만들어지고, 각 클러스터가 step과 nonstep에서 어떤 점유율과 coverage를 보이는지, 그리고 같은 클러스터 내부의 조건별 대표 `H`가 어떻게 다른지 명확하게 표, 리포트, 그리고 figure로 드러나는 것이다.

특히 figure는 CSV 테이블만으로는 즉시 파악하기 어려운 패턴(step과 nonstep의 W 구조 유사성, H temporal profile 차이, occupancy 불균형)을 시각적으로 전달하는 역할을 한다.

### English

If this plan is implemented successfully, the user should be able to ask a more direct question than the current pipeline allows: "Do step and nonstep really use different `W` structures, or do they recruit a shared `W` dictionary with different frequencies and time profiles?" Success is not defined by inferential statistics at this stage. It is defined by building a stable common clustering space and by making condition-specific occupancy, subject coverage, and representative `H` differences visible in explicit tables, figures, and a written report.

The figures specifically serve to convey patterns that are difficult to grasp from CSV tables alone: W structural similarity between step and nonstep, H temporal profile differences, and occupancy imbalance.

Implementation outcome on 2026-03-15: the analysis-only workflow was added under `analysis/pooled_shared_specific_synergy/`, dry-run validation passed with `125` selected trials and `24` selected subjects, and the full validation run produced `486` pooled components with `k_lb=7`, `k_gap_raw=13`, `k_selected=16`, and zero duplicates at the selected `K`. The planned CSVs, 6 figures, and generated artifact `report.md` were all produced under `analysis/pooled_shared_specific_synergy/artifacts/dev_run/`.

Implementation outcome on 2026-03-15: rerun MD5 comparison showed that the required deliverables (4 CSVs, 6 figures, and `report.md`) matched across two executions with the same arguments. Only `run_metadata.json` retained small floating-point differences in diagnostic values, which did not affect the user-facing analysis outputs.

## Context and Orientation / 현재 맥락과 방향 설명

### Korean

이 저장소에서 "trial-level NMF"는 각 `subject-velocity-trial` 단위 trial window에서 EMG 행렬을 분해해 여러 개의 시너지 component를 얻는 절차다. 여기서 `W`는 "근육 가중치 벡터"이고, 한 component가 어떤 근육 조합으로 구성되는지를 보여 준다. `H`는 그 component가 시간축에서 얼마나 활성화되는지를 나타내는 activation profile이다. 현재 기본 방법론에서는 각 trial에 대해 rank를 1부터 올리며 NMF를 반복하고, `VAF >= 0.90`를 처음 만족하는 최소 rank를 채택한다. representative `H`는 원시 길이 그대로 저장하는 것이 아니라 export 시점에 100-window 길이로 보간하여 해석한다.

이 저장소에서 "duplicate"는 같은 trial에서 나온 둘 이상의 component가 같은 cluster에 배정되는 상황을 뜻한다. 현재 파이프라인은 이런 해를 post-hoc으로 억지 보정하지 않고, gap statistic으로 얻은 구조 기준 K 이상에서 duplicate가 0이 되는 첫 번째 K를 최종 K로 채택한다. 따라서 pooled 분석에서도 duplicate의 정의와 선택 철학은 그대로 유지해야 한다.

이번 작업은 `scripts/emg/*`를 수정하는 것이 아니라 `analysis/` 안에 독립적인 실험 스크립트를 추가하는 것이다. 이 스크립트는 baseline run의 `all_trial_window_metadata.csv`를 읽어 어떤 trial이 선택되었고 step/nonstep class가 무엇인지 확인한다. 그 다음 `configs/global_config.yaml`이 가리키는 EMG parquet와 event workbook을 사용해 동일한 window semantics로 trial-level NMF를 재수행한다. 이 접근은 기존 `analysis/compare_professor`와 같은 구조다.

이번 계획에서 "surrogate step window"는 nonstep trial에 실제 step event가 없기 때문에, 같은 subject의 selected step trial 평균 step latency를 적용해 종료점을 인공적으로 정의하는 규칙을 말한다. step trial은 실제 `step_onset`까지 자르고, nonstep trial은 `platform_onset + mean(step_onset - platform_onset)`까지 자른다. pooled 분석에서도 nonstep의 `H`는 이 surrogate 종료점까지의 신호에서만 계산해야 step과 nonstep이 같은 시간 의미를 갖는다.

이번 계획에서 "occupancy"는 한 cluster가 step과 nonstep에서 얼마나 많이 사용되는지를 뜻한다. 그러나 raw component count만 보면 step 쪽에서 trial당 component 수가 많을 때 차이가 과장될 수 있다. 그래서 반드시 raw count와 함께 "subject-normalized occupancy"를 같이 계산한다. subject-normalized occupancy란, 같은 subject와 같은 strategy 안에서 그 subject의 전체 component 중 특정 cluster가 차지하는 비율을 먼저 계산하고, 그 비율을 subject들 사이에서 평균 내는 방식이다. "subject coverage"는 특정 cluster가 해당 strategy의 몇 명의 subject에게서 최소 한 번 이상 나타났는지를 뜻한다.

### English

In this repository, "trial-level NMF" means decomposing the EMG matrix from each `subject-velocity-trial` window into several synergy components. Here, `W` is the "muscle weight vector," describing which muscles participate in one component, and `H` is the "activation profile," describing how strongly that component is expressed over time. The current method increases rank from 1 upward, repeats NMF, and selects the smallest rank that first satisfies `VAF >= 0.90`. Representative `H` is not interpreted at raw sequence length; it is interpolated to 100 windows at export time.

In this repository, a "duplicate" means that two or more components from the same trial are assigned to the same cluster. The current pipeline does not repair this post hoc. Instead, after gap statistic proposes a structural `K`, the final `K` is the first value at or above that recommendation with zero within-trial duplicates. The pooled analysis must preserve that exact meaning of duplicate and that same selection logic.

This task does not modify `scripts/emg/*`. It adds an independent experiment inside `analysis/`. The script will read the baseline run's `all_trial_window_metadata.csv` to determine which trials were selected and what their step/nonstep class is. It will then use the EMG parquet and event workbook pointed to by `configs/global_config.yaml` to re-run trial-level NMF with the same window semantics. This matches the existing `analysis/compare_professor` pattern.

In this plan, "surrogate step window" means the rule used for nonstep trials that do not have an actual step event. The endpoint is defined using the subject's mean step latency from the selected step trials. Step trials are cut at their actual `step_onset`, while nonstep trials are cut at `platform_onset + mean(step_onset - platform_onset)`. The pooled analysis must compute nonstep `H` only within this surrogate endpoint so that step and nonstep retain the same time meaning.

In this plan, "occupancy" means how heavily one cluster is used in step versus nonstep. Raw component counts alone can be misleading because one condition may produce more components per trial. Therefore the plan requires both raw counts and "subject-normalized occupancy." Subject-normalized occupancy means: within each subject and each strategy, compute the proportion of that subject's components assigned to one cluster, then summarize those proportions across subjects. "Subject coverage" means how many subjects in a strategy show at least one member in that cluster.

## Plan of Work / 작업 계획

### Korean

첫 번째 편집은 새 분석 작업 공간을 만드는 것이다. `analysis/pooled_shared_specific_synergy/` 폴더를 만들고, 그 안에 메인 스크립트 `analyze_pooled_shared_specific_synergy.py`와 결과 요약 문서 `report.md`를 둔다. 이 폴더는 baseline 파이프라인과 독립적으로 돌아가며, 어떠한 기존 pipeline script도 수정하지 않는다.

두 번째 편집은 "baseline 정렬 계층"이다. 메인 스크립트 안에 `load_baseline_trial_windows()` 같은 함수를 만들고, baseline run 디렉터리의 `all_trial_window_metadata.csv`를 읽는다. 이 함수는 최소한 `subject`, `velocity`, `trial_num`, `analysis_step_class`, `analysis_window_start`, `analysis_window_end`, `analysis_window_source`, `analysis_window_is_surrogate`를 읽어야 한다. 그리고 선택된 mixed comparison trial 집합의 key 목록을 만든다. 이 baseline key 집합은 이후 모든 분석 출력이 맞춰야 하는 기준이 된다.

세 번째 편집은 "analysis 재추출 계층"이다. 메인 스크립트는 `configs/global_config.yaml`을 읽어 EMG parquet 경로와 event workbook 경로를 가져온다. 그 다음 baseline과 같은 window semantics로 event metadata를 다시 준비하고, baseline key에 해당하는 trial만 잘라서 EMG 행렬 `X(time × muscles)`를 만든다. 여기서 nonstep은 반드시 surrogate step window 종료점을 사용해야 한다. 이 단계는 baseline의 `analysis_step_class`와 event 기반 step/nonstep 라벨이 완전히 같은지 검증해야 하며, 조금이라도 다르면 바로 실패해야 한다.

네 번째 편집은 trial-level NMF 추출 계층이다. 각 selected trial에 대해 rank를 1부터 증가시키며 NMF를 수행하고, `VAF >= 0.90`를 처음 만족하는 최소 rank를 채택한다. 각 component에 대해 최소한 `subject`, `velocity`, `trial_num`, `step_TF`, `component_idx`, `w_vector`, `h_vector`, `n_components_selected`를 저장한다. `W` 정규화 방식은 baseline과 일관되게 유지해야 하며, 이 단계의 출력은 "한 row = 한 component"인 pooled component table의 재료가 된다.

다섯 번째 편집은 pooled clustering 계층이다. 모든 step/nonstep component의 `W`를 한 번에 모아 행렬 `X_pool(components × muscles)`을 만든다. 이때 clustering 입력에는 step/nonstep label을 넣지 않는다. `k_lb`는 selected trial들 안에서 subject별 최대 component 수의 최댓값 이상이어야 하며, `k_max`는 config와 전체 component 수를 고려해 안전하게 제한한다. 후보 `K`마다 gap statistic을 계산해 구조 기준 `k_gap_raw`를 찾고, 그 이후 `duplicate_trial_count == 0`을 처음 만족하는 `k_selected`를 최종 채택한다. 여기서 duplicate란 같은 `(subject, velocity, trial_num)` 안의 둘 이상 component가 같은 cluster로 들어가는 경우다.

여섯 번째 편집은 pooled summary 계층이다. `pooled_cluster_members.csv`에는 모든 component의 cluster label을 저장한다. `pooled_cluster_summary.csv`에는 cluster별 `n_members_total`, `n_members_step`, `n_members_nonstep`, `subject_coverage_step`, `subject_coverage_nonstep`, `subject_norm_occupancy_step_mean`, `subject_norm_occupancy_nonstep_mean`, `step_nonstep_subcentroid_cosine`, `step_nonstep_subcentroid_corr`를 저장한다. 여기서 sub-centroid는 한 cluster 안에서 step member만 평균 낸 `W`와 nonstep member만 평균 낸 `W`를 뜻한다. pooled centroid 자체만 보는 것이 아니라, 같은 cluster 안의 step 평균 구조와 nonstep 평균 구조가 얼마나 비슷한지까지 같이 남겨야 한다.

일곱 번째 편집은 representative `H` export 계층이다. 각 cluster에 대해 member들의 `H`를 export 시점에 100-window 길이로 보간한다. 그 다음 step member만 평균한 `mean_H_step`과 nonstep member만 평균한 `mean_H_nonstep`를 따로 계산한다. 저장 형식은 long table로 두고, 최소 컬럼은 `cluster_id`, `strategy`, `time_bin`, `h_mean`, `h_sd`, `n_members`가 필요하다. 이 파일은 `pooled_representative_H_long.csv`로 저장한다.

여덟 번째 편집은 figure 생성 계층이다. 모든 figure는 기존 파이프라인의 시각적 규칙(matplotlib Agg backend, DPI 150, Korean font NanumGothic, W bar `#5C7CFA`, H line `#2F9E44`, `bbox_inches="tight"`)을 따른다. 총 6개의 figure를 `figures/` 하위 디렉터리에 저장한다.

- **Figure 1: `pooled_clusters.png`** — pooled centroid 기반 클러스터 overview. 기존 `global_step_clusters.png`와 동일한 레이아웃으로, 클러스터당 1행에 W bar chart(pooled centroid)와 pooled H line plot을 배치한다. 각 행의 타이틀에 `cluster_id`, total member count, step/nonstep member count, subject coverage를 표시한다.

- **Figure 2: `step_vs_nonstep_W.png`** — 클러스터별 step sub-centroid와 nonstep sub-centroid W를 나란히 비교하는 figure. 클러스터당 1행, 2열(왼쪽: step sub-centroid W bar, 오른쪽: nonstep sub-centroid W bar). 각 행 타이틀에 sub-centroid cosine similarity를 표시한다. 이 figure는 "같은 cluster 안에서 step과 nonstep의 근육 조합이 얼마나 비슷한가"를 시각적으로 보여 주는 핵심 비교 figure다.

- **Figure 3: `step_vs_nonstep_H.png`** — 같은 cluster 내에서 step representative H(실선, `#5C7CFA` 파란)와 nonstep representative H(점선, `#E64980` 분홍)를 오버레이한 figure. 클러스터당 1 subplot, x축은 0~100 normalized time bin, y축은 activation magnitude. 각 subplot 타이틀에 `cluster_id`, step/nonstep member count를 표시한다. 실선/점선 주변에 ±1 SD shaded area를 표시한다.

- **Figure 4: `occupancy_summary.png`** — 클러스터별 step vs nonstep 점유율을 비교하는 grouped bar chart. 상단 subplot: raw member count (step 파란 bar, nonstep 분홍 bar). 하단 subplot: subject-normalized occupancy mean ± SD (같은 색상). x축은 `cluster_id`, 각 bar 위에 subject coverage 수를 annotation으로 표시한다.

- **Figure 5: `k_selection_diagnostic.png`** — K 선택 과정을 보여 주는 2-panel diagnostic figure. 상단 panel: k vs gap statistic 라인 플롯, `k_gap_raw` 위치에 수직 점선 마킹. 하단 panel: k vs duplicate trial count 라인 플롯, `k_selected` 위치에 수직 점선 마킹(초록). 두 panel 모두 `k_lb` 위치에 회색 수직선을 표시한다.

- **Figure 6: `subcentroid_similarity_heatmap.png`** — 모든 클러스터의 step sub-centroid와 nonstep sub-centroid 사이 cosine similarity를 정방 히트맵으로 시각화. 행은 step sub-centroids, 열은 nonstep sub-centroids. 대각선 값이 높으면 "step과 nonstep이 같은 근육 조합을 공유한다"는 증거가 된다. 색상 스케일은 0~1, annotate=True로 셀 안에 수치를 표시한다.

아홉 번째 편집은 자동 리포트 계층이다. `report.md`에는 입력 경로, baseline 검증 결과, selected trial 수, subject 수, selected `K`, `duplicate_trial_count_by_k`, cluster별 occupancy/coverage 요약, 높은 sub-centroid similarity를 보이는 cluster 목록, step/nonstep 대표 `H` 차이가 큰 cluster 목록을 텍스트로 정리한다. 또한 생성된 6개 figure 파일명과 각 figure가 보여 주는 핵심 해석을 한 문장씩 기록한다. 이 문서는 사람이 바로 읽는 결과 요약이며, v1에서는 통계 검정 수치보다 descriptive interpretation을 우선한다.

### English

The first edit is to create a new analysis workspace. Create `analysis/pooled_shared_specific_synergy/` and place two files there: the main script `analyze_pooled_shared_specific_synergy.py` and a result summary document `report.md`. This folder runs independently from the baseline pipeline and does not modify any existing pipeline script.

The second edit is the "baseline alignment layer." Inside the main script, define a function such as `load_baseline_trial_windows()` that reads `all_trial_window_metadata.csv` from a baseline run directory. At minimum it must load `subject`, `velocity`, `trial_num`, `analysis_step_class`, `analysis_window_start`, `analysis_window_end`, `analysis_window_source`, and `analysis_window_is_surrogate`. It must then build the key set of selected mixed-comparison trials. This baseline key set becomes the reference that every downstream analysis output must match.

The third edit is the "analysis re-extraction layer." The main script reads `configs/global_config.yaml` to resolve the EMG parquet path and event workbook path. It then reconstructs event metadata using the same window semantics as the baseline, cuts only the baseline-selected trials, and builds an EMG matrix `X(time × muscles)` for each trial. Nonstep must always use the surrogate step window endpoint. This layer must validate exact agreement between baseline `analysis_step_class` and event-derived step/nonstep labels and must fail immediately if any mismatch exists.

The fourth edit is the trial-level NMF extraction layer. For each selected trial, increase rank from 1 upward, fit NMF, and select the smallest rank that first satisfies `VAF >= 0.90`. For every component, store at least `subject`, `velocity`, `trial_num`, `step_TF`, `component_idx`, `w_vector`, `h_vector`, and `n_components_selected`. The `W` normalization rule must remain consistent with the baseline method. The output of this layer becomes the raw material for a pooled component table with "one row = one component."

The fifth edit is the pooled clustering layer. Pool every step and nonstep component `W` into one matrix `X_pool(components × muscles)`. Do not include the step/nonstep label in the clustering input. `k_lb` must be at least the maximum subject-level maximum component count among the selected trials, and `k_max` must be safely bounded by config and by the total number of pooled components. For each candidate `K`, compute gap statistic to get the structural recommendation `k_gap_raw`, then select the first `K` with `duplicate_trial_count == 0` as `k_selected`. Here, a duplicate means that two or more components from the same `(subject, velocity, trial_num)` are assigned to the same cluster.

The sixth edit is the pooled summary layer. `pooled_cluster_members.csv` stores the cluster label of every component. `pooled_cluster_summary.csv` stores, for every cluster, `n_members_total`, `n_members_step`, `n_members_nonstep`, `subject_coverage_step`, `subject_coverage_nonstep`, `subject_norm_occupancy_step_mean`, `subject_norm_occupancy_nonstep_mean`, `step_nonstep_subcentroid_cosine`, and `step_nonstep_subcentroid_corr`. A sub-centroid means the average `W` using only step members inside a cluster or only nonstep members inside a cluster. The analysis must preserve not only the pooled centroid but also how similar the step-only and nonstep-only structures are within that cluster.

The seventh edit is the representative `H` export layer. For each cluster, interpolate member `H` profiles to 100 windows at export time. Then compute `mean_H_step` using only step members and `mean_H_nonstep` using only nonstep members. Store the result as a long table with at least `cluster_id`, `strategy`, `time_bin`, `h_mean`, `h_sd`, and `n_members`. Save this file as `pooled_representative_H_long.csv`.

The eighth edit is the figure generation layer. All figures follow the existing pipeline visual conventions (matplotlib Agg backend, DPI 150, Korean font NanumGothic, W bar `#5C7CFA`, H line `#2F9E44`, `bbox_inches="tight"`). A total of 6 figures are saved under a `figures/` subdirectory.

- **Figure 1: `pooled_clusters.png`** — Pooled centroid cluster overview. Same layout as `global_step_clusters.png`: one row per cluster with W bar chart (pooled centroid) and pooled H line plot. Each row title shows `cluster_id`, total member count, step/nonstep member counts, and subject coverage.

- **Figure 2: `step_vs_nonstep_W.png`** — Side-by-side comparison of step sub-centroid and nonstep sub-centroid W for each cluster. One row per cluster, 2 columns (left: step sub-centroid W bar, right: nonstep sub-centroid W bar). Each row title shows the sub-centroid cosine similarity. This is the key comparison figure showing "how similar are the muscle compositions within the same cluster across conditions."

- **Figure 3: `step_vs_nonstep_H.png`** — Overlay of step representative H (solid line, blue `#5C7CFA`) and nonstep representative H (dashed line, pink `#E64980`) within the same cluster. One subplot per cluster, x-axis 0–100 normalized time bins, y-axis activation magnitude. Each subplot title shows `cluster_id` and step/nonstep member counts. ±1 SD shaded area around each line.

- **Figure 4: `occupancy_summary.png`** — Grouped bar chart comparing step vs nonstep occupancy per cluster. Top subplot: raw member counts (step blue bars, nonstep pink bars). Bottom subplot: subject-normalized occupancy mean ± SD (same colors). X-axis is `cluster_id`, subject coverage counts annotated above each bar.

- **Figure 5: `k_selection_diagnostic.png`** — 2-panel diagnostic figure for K selection. Top panel: k vs gap statistic line plot with vertical dashed line at `k_gap_raw`. Bottom panel: k vs duplicate trial count line plot with vertical dashed green line at `k_selected`. Both panels show a gray vertical line at `k_lb`.

- **Figure 6: `subcentroid_similarity_heatmap.png`** — Square heatmap of cosine similarity between all step sub-centroids (rows) and all nonstep sub-centroids (columns). High diagonal values indicate shared muscle compositions between step and nonstep. Color scale 0–1, `annotate=True` to display numeric values in cells.

The ninth edit is the automated report layer. `report.md` must summarize the input paths, baseline validation results, selected trial count, subject count, selected `K`, `duplicate_trial_count_by_k`, cluster-wise occupancy and coverage, the clusters with high sub-centroid similarity, and the clusters with large differences between step and nonstep representative `H`. It must also list the 6 generated figure filenames with a one-sentence interpretation of each. This report is meant for immediate human interpretation and in v1 should prioritize descriptive interpretation over inferential testing.

## Figure Style Reference / Figure 스타일 참조

### Korean

모든 figure는 아래 공통 스타일 규칙을 따른다. 이 규칙은 기존 파이프라인 `src/synergy_stats/figures.py`의 `_render_component_grid()` 함수에서 확인된 관례를 pooled 분석에 맞게 확장한 것이다.

| 항목 | 값 |
|------|-----|
| Backend | `matplotlib.use("Agg")` (headless) |
| DPI | 150 |
| 저장 형식 | PNG |
| savefig 옵션 | `bbox_inches="tight"` |
| Korean font | NanumGothic (fallback: AppleGothic, Noto Sans KR) |
| W bar chart 색상 | `#5C7CFA` (파란) |
| H line plot 색상 (pooled/step) | `#2F9E44` (초록, pooled clusters figure) / `#5C7CFA` (파란, step vs nonstep figure) |
| H line plot 색상 (nonstep) | `#E64980` (분홍, step vs nonstep overlay에서만 사용) |
| Nonstep line style | dashed (`--`) (step vs nonstep overlay에서만) |
| Shaded area (±1 SD) | `alpha=0.2`, 해당 line과 같은 색상 |
| Figure sizing | `figsize=(14, 3.5 * n_clusters)` (cluster grid), 고정 크기는 figure별 정의 |
| Heatmap | `annotate=True`, colormap `Blues` 또는 `RdYlGn`, scale 0~1 |
| Bar annotation | subject coverage 수를 bar 위에 텍스트로 표시 |
| Occupancy bar 색상 | step: `#5C7CFA`, nonstep: `#E64980` |
| Diagnostic line plot | 기본 matplotlib 색상, marker 포함, 수직 점선으로 선택 지점 마킹 |

### English

All figures follow the shared style rules below. These rules extend the conventions found in `_render_component_grid()` of `src/synergy_stats/figures.py` for the pooled analysis context.

| Item | Value |
|------|-------|
| Backend | `matplotlib.use("Agg")` (headless) |
| DPI | 150 |
| Save format | PNG |
| savefig option | `bbox_inches="tight"` |
| Korean font | NanumGothic (fallback: AppleGothic, Noto Sans KR) |
| W bar chart color | `#5C7CFA` (blue) |
| H line plot color (pooled/step) | `#2F9E44` (green, for pooled clusters figure) / `#5C7CFA` (blue, for step vs nonstep figure) |
| H line plot color (nonstep) | `#E64980` (pink, only in step vs nonstep overlay) |
| Nonstep line style | dashed (`--`) (only in step vs nonstep overlay) |
| Shaded area (±1 SD) | `alpha=0.2`, same color as the corresponding line |
| Figure sizing | `figsize=(14, 3.5 * n_clusters)` (cluster grids), fixed sizes defined per figure |
| Heatmap | `annotate=True`, colormap `Blues` or `RdYlGn`, scale 0–1 |
| Bar annotation | subject coverage count displayed as text above each bar |
| Occupancy bar colors | step: `#5C7CFA`, nonstep: `#E64980` |
| Diagnostic line plot | default matplotlib colors, markers, vertical dashed lines at selection points |

## Concrete Steps / 구체적 실행 단계

### Korean

작업 디렉터리는 저장소 루트다. 모든 실행은 로컬 규칙에 맞게 `conda run -n module python ...` 형식을 사용한다.

처음 확인은 dry-run이다. 아직 구현 전이라 실제 transcript는 없지만, 구현이 끝나면 아래 명령이 baseline trial alignment와 입력 경로만 검증하고 종료해야 한다.

    conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
      --dry-run

예상 출력 예시는 아래 형태다.

    [OK] loaded baseline trial window metadata
    [OK] resolved EMG parquet and event workbook from config
    [OK] baseline/event step label validation passed
    [OK] selected trials: <N>
    [OK] selected subjects: <S>
    [OK] dry-run complete

실제 분석 실행은 아래 명령이다.

    conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
      --overwrite

예상 출력 예시는 아래 형태다.

    [OK] loaded baseline trial window metadata
    [OK] trial-level NMF extraction complete
    [OK] pooled components: <M>
    [OK] k_lb=<...>, k_gap_raw=<...>, k_selected=<...>
    [OK] duplicate_trial_count(k_selected)=0
    [OK] wrote pooled_cluster_members.csv
    [OK] wrote pooled_cluster_summary.csv
    [OK] wrote pooled_representative_W.csv
    [OK] wrote pooled_representative_H_long.csv
    [OK] wrote figures/pooled_clusters.png
    [OK] wrote figures/step_vs_nonstep_W.png
    [OK] wrote figures/step_vs_nonstep_H.png
    [OK] wrote figures/occupancy_summary.png
    [OK] wrote figures/k_selection_diagnostic.png
    [OK] wrote figures/subcentroid_similarity_heatmap.png
    [OK] wrote report.md

구현 중에는 최소한 아래 순서로 중간 검증을 한다.

    conda run -n module python -m py_compile analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py

그 다음 생성된 산출물 열 이름과 figure 파일 존재를 빠르게 확인한다.

    conda run -n module python - <<'PY'
    import polars as pl
    from pathlib import Path
    base = Path("analysis/pooled_shared_specific_synergy/artifacts/dev_run")
    for csv in ["pooled_cluster_members.csv", "pooled_cluster_summary.csv", "pooled_representative_H_long.csv"]:
        df = pl.read_csv(base / csv)
        print(csv, df.columns)
    fig_dir = base / "figures"
    expected = [
        "pooled_clusters.png", "step_vs_nonstep_W.png", "step_vs_nonstep_H.png",
        "occupancy_summary.png", "k_selection_diagnostic.png", "subcentroid_similarity_heatmap.png",
    ]
    for f in expected:
        ok = "OK" if (fig_dir / f).exists() else "MISSING"
        print(f"[{ok}] figures/{f}")
    PY

### English

The working directory is the repository root. All commands use the local rule `conda run -n module python ...`.

The first check is a dry run. There is no transcript yet because the code is not written, but once implemented the following command must validate only the baseline trial alignment and input paths, then exit.

    conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
      --dry-run

The expected output should look like this.

    [OK] loaded baseline trial window metadata
    [OK] resolved EMG parquet and event workbook from config
    [OK] baseline/event step label validation passed
    [OK] selected trials: <N>
    [OK] selected subjects: <S>
    [OK] dry-run complete

The full analysis run is this command.

    conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
      --config configs/global_config.yaml \
      --baseline-run outputs/runs/default_run \
      --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
      --overwrite

The expected output should look like this.

    [OK] loaded baseline trial window metadata
    [OK] trial-level NMF extraction complete
    [OK] pooled components: <M>
    [OK] k_lb=<...>, k_gap_raw=<...>, k_selected=<...>
    [OK] duplicate_trial_count(k_selected)=0
    [OK] wrote pooled_cluster_members.csv
    [OK] wrote pooled_cluster_summary.csv
    [OK] wrote pooled_representative_W.csv
    [OK] wrote pooled_representative_H_long.csv
    [OK] wrote figures/pooled_clusters.png
    [OK] wrote figures/step_vs_nonstep_W.png
    [OK] wrote figures/step_vs_nonstep_H.png
    [OK] wrote figures/occupancy_summary.png
    [OK] wrote figures/k_selection_diagnostic.png
    [OK] wrote figures/subcentroid_similarity_heatmap.png
    [OK] wrote report.md

During implementation, perform at least this compile-level check.

    conda run -n module python -m py_compile analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py

Then quickly inspect the output schemas and figure file existence.

    conda run -n module python - <<'PY'
    import polars as pl
    from pathlib import Path
    base = Path("analysis/pooled_shared_specific_synergy/artifacts/dev_run")
    for csv in ["pooled_cluster_members.csv", "pooled_cluster_summary.csv", "pooled_representative_H_long.csv"]:
        df = pl.read_csv(base / csv)
        print(csv, df.columns)
    fig_dir = base / "figures"
    expected = [
        "pooled_clusters.png", "step_vs_nonstep_W.png", "step_vs_nonstep_H.png",
        "occupancy_summary.png", "k_selection_diagnostic.png", "subcentroid_similarity_heatmap.png",
    ]
    for f in expected:
        ok = "OK" if (fig_dir / f).exists() else "MISSING"
        print(f"[{ok}] figures/{f}")
    PY

## Validation and Acceptance / 검증 및 수용 기준

### Korean

이 기능은 아래 행동 기준을 만족해야 한다.

첫째, baseline trial alignment가 정확해야 한다. `all_trial_window_metadata.csv`의 selected mixed comparison trial key와 analysis script가 다시 구성한 trial key가 완전히 같아야 한다. 차이가 하나라도 있으면 성공이 아니다.

둘째, baseline label validation이 정확해야 한다. baseline의 `analysis_step_class`와 analysis script가 event workbook으로부터 재구성한 step/nonstep 라벨이 완전히 일치해야 한다. 차이가 하나라도 있으면 스크립트는 실패해야 한다.

셋째, pooled clustering 결과는 zero-duplicate constraint를 만족해야 한다. 최종 `k_selected`에 대해 duplicate trial count가 0이어야 한다. 0이 아니면 스크립트는 실패해야 한다.

넷째, `pooled_cluster_summary.csv`에는 raw occupancy와 subject-normalized occupancy가 모두 들어 있어야 한다. 이 두 값을 구분하지 않으면 해석이 편향될 수 있으므로 성공으로 간주하지 않는다.

다섯째, `pooled_representative_H_long.csv`에는 step과 nonstep이 분리된 대표 `H`가 100-window 기준으로 저장되어야 한다. 같은 cluster에 대해 `strategy == step`과 `strategy == nonstep` 두 집합이 모두 존재하는 cluster는 직접 비교 가능해야 한다.

여섯째, 6개 figure 파일이 모두 `figures/` 하위 디렉터리에 생성되어야 한다. 각 figure는 아래 조건을 만족해야 한다.
- `pooled_clusters.png`: 클러스터 수만큼의 행이 존재하고, 각 행에 W bar와 H line이 있어야 한다.
- `step_vs_nonstep_W.png`: 클러스터 수만큼의 행, 행당 2열(step/nonstep)이 있어야 한다.
- `step_vs_nonstep_H.png`: 클러스터 수만큼의 subplot이 있고, 각 subplot에 두 조건의 H가 오버레이되어야 한다.
- `occupancy_summary.png`: 2-panel 구조(raw count + normalized occupancy)이고, 모든 cluster가 표시되어야 한다.
- `k_selection_diagnostic.png`: 2-panel 구조(gap statistic + duplicate count)이고, 선택 지점이 마킹되어야 한다.
- `subcentroid_similarity_heatmap.png`: 정방 히트맵이고, 셀 안에 수치가 표시되어야 한다.

일곱째, `report.md`는 사람이 열어서 바로 이해할 수 있어야 한다. 최소한 selected trial 수, selected subject 수, `k_lb`, `k_gap_raw`, `k_selected`, cluster별 occupancy, cluster별 subject coverage, 높은 sub-centroid similarity cluster 목록을 문장으로 설명해야 한다. 또한 6개 figure 각각에 대한 한 문장 해석을 포함해야 한다.

### English

This feature must satisfy the following behavior-based acceptance criteria.

First, baseline trial alignment must be exact. The selected mixed-comparison trial keys in `all_trial_window_metadata.csv` must exactly match the trial keys reconstructed by the analysis script. Any mismatch is a failure.

Second, baseline label validation must be exact. The baseline `analysis_step_class` must exactly match the step/nonstep labels reconstructed by the analysis script from the event workbook. Any mismatch must cause the script to fail.

Third, the pooled clustering result must satisfy the zero-duplicate constraint. For the final `k_selected`, the duplicate trial count must be 0. Any nonzero value is a failure.

Fourth, `pooled_cluster_summary.csv` must contain both raw occupancy and subject-normalized occupancy. Without both, the interpretation can be biased, so the output is not considered complete.

Fifth, `pooled_representative_H_long.csv` must store condition-specific representative `H` at 100 windows. For any cluster that has both strategies represented, the file must contain directly comparable `strategy == step` and `strategy == nonstep` rows.

Sixth, all 6 figure files must be generated under the `figures/` subdirectory. Each figure must satisfy the following conditions:
- `pooled_clusters.png`: Must have as many rows as clusters, each row containing a W bar and H line.
- `step_vs_nonstep_W.png`: Must have as many rows as clusters, 2 columns per row (step/nonstep).
- `step_vs_nonstep_H.png`: Must have as many subplots as clusters, each with two overlaid condition H profiles.
- `occupancy_summary.png`: Must be a 2-panel structure (raw count + normalized occupancy) showing all clusters.
- `k_selection_diagnostic.png`: Must be a 2-panel structure (gap statistic + duplicate count) with selection points marked.
- `subcentroid_similarity_heatmap.png`: Must be a square heatmap with numeric values displayed in cells.

Seventh, `report.md` must be readable by a human without opening the code. At minimum it must describe the selected trial count, selected subject count, `k_lb`, `k_gap_raw`, `k_selected`, cluster-wise occupancy, cluster-wise subject coverage, and the list of clusters with high sub-centroid similarity. It must also include a one-sentence interpretation of each of the 6 figures.

## Idempotence and Recovery / 반복 실행과 복구

### Korean

이 작업은 `analysis/` 전용이므로 baseline pipeline 산출물을 덮어쓰지 않는다. 출력 디렉터리는 항상 `--outdir` 아래에만 생성한다. `--overwrite`가 없으면 기존 결과가 존재할 때 실패하도록 구현한다. 따라서 같은 입력과 같은 seed로 다시 실행해도 기존 baseline을 손상시키지 않고 안전하게 반복할 수 있다.

실패 복구는 단순해야 한다. `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/` 폴더만 지우고 다시 실행하면 된다. 이 계획은 기존 `outputs/runs/default_run/`을 수정하지 않으므로 git rollback이나 pipeline rollback은 필요하지 않다.

### English

This work is analysis-only, so it must never overwrite baseline pipeline artifacts. All outputs go only under `--outdir`. If `--overwrite` is not given and the output directory already exists, the script should fail. That makes reruns safe and keeps the baseline untouched for repeated experiments with the same inputs and the same seed.

Recovery should be simple. Delete only `analysis/pooled_shared_specific_synergy/artifacts/<run_name>/` and rerun. Because the plan never modifies `outputs/runs/default_run/`, no git rollback or pipeline rollback should be necessary.

## Artifacts and Notes / 산출물과 메모

### Korean

최소 산출물은 CSV 4개, figure 6개, report 1개로 총 11개다.

**CSV 산출물:**

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_cluster_members.csv
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_cluster_summary.csv
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_representative_W.csv
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_representative_H_long.csv

**Figure 산출물:**

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/pooled_clusters.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/step_vs_nonstep_W.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/step_vs_nonstep_H.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/occupancy_summary.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/k_selection_diagnostic.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/subcentroid_similarity_heatmap.png

**Report:**

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/report.md

`pooled_cluster_members.csv`는 "한 row = 한 trial-level synergy component" 구조를 가져야 한다. 최소 컬럼은 다음과 같다.

    subject
    velocity
    trial_num
    step_TF
    component_idx
    n_components_selected
    cluster_id
    group_id
    source_trial_key

`pooled_cluster_summary.csv`의 최소 컬럼은 다음과 같다.

    cluster_id
    n_members_total
    n_members_step
    n_members_nonstep
    subject_coverage_step
    subject_coverage_nonstep
    subject_norm_occupancy_step_mean
    subject_norm_occupancy_step_sd
    subject_norm_occupancy_nonstep_mean
    subject_norm_occupancy_nonstep_sd
    step_nonstep_subcentroid_cosine
    step_nonstep_subcentroid_corr

`pooled_representative_W.csv`는 최소한 `cluster_id`, `muscle`, `weight_mean`, `weight_sd`, `strategy_view`를 포함해야 한다. `strategy_view`는 `pooled`, `step_only`, `nonstep_only` 중 하나다.

`pooled_representative_H_long.csv`는 최소한 아래 컬럼을 포함해야 한다.

    cluster_id
    strategy
    time_bin
    h_mean
    h_sd
    n_members

**Figure 명세:**

| Figure | 레이아웃 | 핵심 정보 |
|--------|----------|----------|
| `pooled_clusters.png` | K행 × 2열 (W bar + H line) | pooled centroid, coverage, member counts |
| `step_vs_nonstep_W.png` | K행 × 2열 (step W + nonstep W) | sub-centroid cosine similarity |
| `step_vs_nonstep_H.png` | K개 subplot (overlay) | step H(실선) vs nonstep H(점선), ±1 SD |
| `occupancy_summary.png` | 2 panel (raw + normalized) | step/nonstep bar, coverage annotation |
| `k_selection_diagnostic.png` | 2 panel (gap + dup) | k_gap_raw, k_selected 마킹 |
| `subcentroid_similarity_heatmap.png` | K × K 정방 히트맵 | cosine similarity, 대각선 = 같은 cluster |

### English

The minimum artifacts are 4 CSVs, 6 figures, and 1 report, totaling 11 files.

**CSV artifacts:**

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_cluster_members.csv
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_cluster_summary.csv
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_representative_W.csv
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/pooled_representative_H_long.csv

**Figure artifacts:**

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/pooled_clusters.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/step_vs_nonstep_W.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/step_vs_nonstep_H.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/occupancy_summary.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/k_selection_diagnostic.png
    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/figures/subcentroid_similarity_heatmap.png

**Report:**

    analysis/pooled_shared_specific_synergy/artifacts/<run_name>/report.md

`pooled_cluster_members.csv` must have a "one row = one trial-level synergy component" shape. Its minimum columns are:

    subject
    velocity
    trial_num
    step_TF
    component_idx
    n_components_selected
    cluster_id
    group_id
    source_trial_key

The minimum columns for `pooled_cluster_summary.csv` are:

    cluster_id
    n_members_total
    n_members_step
    n_members_nonstep
    subject_coverage_step
    subject_coverage_nonstep
    subject_norm_occupancy_step_mean
    subject_norm_occupancy_step_sd
    subject_norm_occupancy_nonstep_mean
    subject_norm_occupancy_nonstep_sd
    step_nonstep_subcentroid_cosine
    step_nonstep_subcentroid_corr

`pooled_representative_W.csv` must include at least `cluster_id`, `muscle`, `weight_mean`, `weight_sd`, and `strategy_view`. `strategy_view` must be one of `pooled`, `step_only`, or `nonstep_only`.

`pooled_representative_H_long.csv` must include at least:

    cluster_id
    strategy
    time_bin
    h_mean
    h_sd
    n_members

**Figure specifications:**

| Figure | Layout | Key information |
|--------|--------|----------------|
| `pooled_clusters.png` | K rows × 2 cols (W bar + H line) | pooled centroid, coverage, member counts |
| `step_vs_nonstep_W.png` | K rows × 2 cols (step W + nonstep W) | sub-centroid cosine similarity |
| `step_vs_nonstep_H.png` | K subplots (overlay) | step H (solid) vs nonstep H (dashed), ±1 SD |
| `occupancy_summary.png` | 2 panels (raw + normalized) | step/nonstep bars, coverage annotation |
| `k_selection_diagnostic.png` | 2 panels (gap + dup) | k_gap_raw, k_selected marked |
| `subcentroid_similarity_heatmap.png` | K × K square heatmap | cosine similarity, diagonal = same cluster |

## Interfaces and Dependencies / 인터페이스와 의존성

### Korean

이 작업은 먼저 `polars`를 사용하고, 정말 필요한 경우에만 `pandas`를 사용한다. 수치 계산은 `numpy`, NMF는 `sklearn.decomposition.NMF`, k-means는 우선 기존 pipeline helper를 재사용할 수 있는지 확인한다. 만약 analysis 공간에서 그 helper가 GPU 전용 의존성 때문에 import 불가하면, 같은 seed 규칙과 같은 gap-statistic/duplicate-selection 논리를 유지한 채 `sklearn.cluster.KMeans`로 대체한다. 이 차이는 반드시 `report.md`에 기록해야 한다. Figure 생성은 `matplotlib`를 사용하며, heatmap에는 `seaborn`이 필요할 수 있다.

메인 스크립트가 끝날 때 아래 함수 또는 동등한 책임의 함수들이 존재해야 한다.

    def load_config(config_path: str) -> dict:
        ...

    def load_baseline_trial_windows(baseline_run: str) -> pl.DataFrame:
        ...

    def resolve_analysis_inputs(config: dict) -> dict:
        ...

    def rebuild_selected_trial_table(config: dict, baseline_windows: pl.DataFrame) -> pl.DataFrame:
        ...

    def extract_trial_matrix(emg_df: pl.DataFrame, trial_row: dict, muscle_cols: list[str]) -> np.ndarray:
        ...

    def fit_trial_nmf_with_vaf(X: np.ndarray, max_components: int, vaf_threshold: float, random_state: int) -> dict:
        ...

    def build_component_table(trial_results: list[dict]) -> pl.DataFrame:
        ...

    def search_pooled_k(component_df: pl.DataFrame, config: dict, random_state: int) -> dict:
        ...

    def fit_pooled_clusters(component_df: pl.DataFrame, k_selected: int, random_state: int) -> pl.DataFrame:
        ...

    def summarize_cluster_outputs(component_df: pl.DataFrame, labels_df: pl.DataFrame) -> dict:
        ...

    def interpolate_h_to_100(h_vec: np.ndarray) -> np.ndarray:
        ...

    def generate_figures(outdir: str, artifacts: dict) -> None:
        ...

    def export_outputs(outdir: str, artifacts: dict) -> None:
        ...

이 함수명은 고정이 아니어도 되지만, 책임 분리는 고정이다. baseline 정렬, NMF 재추출, pooled K 검색, pooled label 부여, summary export, figure 생성은 반드시 분리된 단계로 보이도록 구현해야 한다. `generate_figures()`는 모든 CSV export가 완료된 후에 호출되어야 하며, CSV 데이터를 직접 읽거나 artifacts dict에서 받아 figure를 생성한다.

### English

This work uses `polars` first and `pandas` only when truly necessary. Numerical work uses `numpy`, NMF uses `sklearn.decomposition.NMF`, and k-means should first attempt to reuse the existing pipeline helper if it can be imported cleanly. If that helper is not usable inside `analysis/` because of GPU-only dependencies, the script may fall back to `sklearn.cluster.KMeans` while preserving the same seed rule and the same gap-statistic and duplicate-selection logic. Any such difference must be documented in `report.md`. Figure generation uses `matplotlib`, and `seaborn` may be needed for heatmaps.

By the end of the work, the main script must define functions with responsibilities equivalent to the following.

    def load_config(config_path: str) -> dict:
        ...

    def load_baseline_trial_windows(baseline_run: str) -> pl.DataFrame:
        ...

    def resolve_analysis_inputs(config: dict) -> dict:
        ...

    def rebuild_selected_trial_table(config: dict, baseline_windows: pl.DataFrame) -> pl.DataFrame:
        ...

    def extract_trial_matrix(emg_df: pl.DataFrame, trial_row: dict, muscle_cols: list[str]) -> np.ndarray:
        ...

    def fit_trial_nmf_with_vaf(X: np.ndarray, max_components: int, vaf_threshold: float, random_state: int) -> dict:
        ...

    def build_component_table(trial_results: list[dict]) -> pl.DataFrame:
        ...

    def search_pooled_k(component_df: pl.DataFrame, config: dict, random_state: int) -> dict:
        ...

    def fit_pooled_clusters(component_df: pl.DataFrame, k_selected: int, random_state: int) -> pl.DataFrame:
        ...

    def summarize_cluster_outputs(component_df: pl.DataFrame, labels_df: pl.DataFrame) -> dict:
        ...

    def interpolate_h_to_100(h_vec: np.ndarray) -> np.ndarray:
        ...

    def generate_figures(outdir: str, artifacts: dict) -> None:
        ...

    def export_outputs(outdir: str, artifacts: dict) -> None:
        ...

The exact names are flexible, but the separation of responsibilities is not. Baseline alignment, NMF re-extraction, pooled K search, pooled label assignment, summary export, and figure generation must remain visibly separate stages. `generate_figures()` must be called after all CSV exports are complete and must either read the CSV data directly or receive it from the artifacts dict.

## Change Note / 변경 메모

### Korean

초안 작성 기준 변경 사항은 다음과 같다. 사용자가 "Phase 4 이야기는 굳이 할 필요 없다"고 명시했으므로, permutation test, mixed model, residual-specific synergy, shared reconstruction score는 이번 ExecPlan의 범위에서 제거했다. 대신 analysis-only pooled clustering v1의 구현과 검증 절차만 남겼다.

두 번째 변경 사항: 사용자가 "기존 파이프라인 figure 참조 + 추가 figure"를 요청했으므로, 기존 `src/synergy_stats/figures.py` 스타일을 기반으로 6개의 figure 생성 계획을 추가했다. 기존 파이프라인의 cluster overview figure 패턴을 pooled 버전으로 확장하고, step vs nonstep W/H 비교, occupancy 요약, K 선택 diagnostic, sub-centroid similarity heatmap을 pooled 분석 고유 figure로 추가했다.

### English

This initial draft reflects one explicit scope change. The user stated that the former "Phase 4" discussion is unnecessary, so permutation tests, mixed models, residual-specific synergies, and shared reconstruction scoring were removed from this ExecPlan. The plan now covers only the implementation and validation of the analysis-only pooled clustering v1.

Second change: The user requested "existing pipeline figure reference + additional figures," so 6 figure generation specifications were added based on the existing `src/synergy_stats/figures.py` style. The pipeline's cluster overview figure pattern was extended to a pooled version, and step vs nonstep W/H comparison, occupancy summary, K selection diagnostic, and sub-centroid similarity heatmap were added as pooled-analysis-specific figures.

Implementation update: On 2026-03-15 the plan was updated to reflect the completed analysis-only implementation, the CPU-backend validation path used in the local `module` environment, and the observed rerun-MD5 result for the required deliverables.
