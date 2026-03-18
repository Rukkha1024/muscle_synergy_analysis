# Defend The 90 Percent VAF Cutoff With Expanded Sensitivity Analysis

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows repository guidance in `.agents/PLANS.md` and must be maintained in accordance with that file.

## Purpose / Big Picture

After this work, a reader should be able to rerun one analysis folder and see a much stronger argument for why the EMG synergy pipeline uses `VAF >= 0.90` instead of nearby alternatives. The current analysis already shows that `0.95` is costly, but it does not yet show whether `0.90` is meaningfully better than `0.85` through `0.89`. The goal of this plan is to expand the existing `analysis/vaf_threshold_sensitivity` workflow so it can compare every cutoff from `0.85` through `0.95` in one-percent steps, quantify how much extra complexity each step buys, show when clustering begins to fragment, and test whether `0.90` preserves more interpretable step-versus-nonstep structure than lower or higher cutoffs.

The visible outcome is a regenerated analysis folder with richer JSON outputs, updated report text, and checksum-verified artifacts. A novice should be able to run the script from the repository root, inspect the report, and see a direct answer to the question “why 90 percent?”

## Progress

- [x] 2026-03-19T00:47:35+09:00 Requirements were confirmed with the user: keep work inside `analysis/vaf_threshold_sensitivity`, sweep `85` through `95` in one-point increments, invest extra runtime if needed, and pursue the strongest honest defense of `0.90`.
- [x] 2026-03-19T00:58:00+09:00 Baseline review completed for the current analysis script, report, clustering logic, and NMF rank selection path.
- [x] 2026-03-19T01:37:00+09:00 Extended the analysis script to sweep `85` through `95`, cache all rank candidates once per analysis unit, expose threshold-transition and pooled-validity summaries, and preserve structured artifact/checksum writing.
- [x] 2026-03-19T01:37:00+09:00 Added downstream-validity comparisons centered on pooled member cosine, shared cluster coverage, tiny-cluster burden, and local `89/90/91/92` threshold transitions.
- [x] 2026-03-19T01:50:00+09:00 Updated `analysis/vaf_threshold_sensitivity/report.md` and `README.md` to document the screening-profile broad sweep, the strongest defensible `0.90` argument, and the exact-profile rerun path.
- [x] 2026-03-19T01:56:00+09:00 Dry-run validation passed, `py_compile` passed, and checksum spot-checks for the screening-profile broad sweep matched `checksums.md5`.
- [ ] The exact-profile local rerun around `89/90/91` is still executing separately because the full default clustering profile is substantially slower than the screening sweep.
- [ ] Run required review agents on the final diff, fix any concrete findings, rerun validation, and commit with a Korean commit message of at least five lines.

## Surprises & Discoveries

- Observation: The current analysis supports rejecting `0.95` more strongly than choosing `0.90`.
  Evidence: The saved report shows that pooled clustering first needs uniqueness-driven escalation at `0.90`, while `0.95` pushes `trialwise` from `k_gap_raw=17` to `k_selected=62`.

- Observation: The current NMF code stops at the first rank that reaches the threshold, which means the existing sensitivity study cannot yet explain the efficiency tradeoff between adjacent thresholds.
  Evidence: `src/synergy_stats/nmf.py` iterates rank upward and breaks immediately once `vaf >= vaf_threshold`.

- Observation: The clustering code already computes the raw signals needed for a stronger defense, including gap curves and duplicate-trial burden by `K`.
  Evidence: `src/synergy_stats/clustering.py` returns `gap_by_k`, `duplicate_trial_count_by_k`, `k_gap_raw`, `k_selected`, and `k_min_unique`.

- Observation: The strongest defensible argument for `0.90` is not “minimum burden” but “highest threshold before ceiling-hit begins in both modes.”
  Evidence: In the screening-profile broad sweep, ceiling-hit rate is `0.0000` at `0.90` for both `trialwise` and `concatenated`, then first appears at `0.91` as `0.0080` and `0.0222`.

- Observation: The first report draft risked overstating reproducibility because the tables reflected the reduced-restart screening profile while the reproduction block originally showed only the default command.
  Evidence: Review agent feedback flagged that `report.md` numbers matched `artifacts/default_run/summary.json` from the override run, not a plain default rerun.

## Decision Log

- Decision: Keep the work inside `analysis/vaf_threshold_sensitivity` instead of creating a new sibling analysis folder.
  Rationale: The user explicitly approved that scope, and the existing script already reruns the exact main-pipeline NMF and clustering code paths that matter for the defense.
  Date/Author: 2026-03-19 / Codex

- Decision: Sweep every integer cutoff from `85` through `95`.
  Rationale: The user requested one-point granularity because the current `80/85/90/95` spacing is too coarse to show whether `0.90` is a real elbow or just one arbitrary option.
  Date/Author: 2026-03-19 / Codex

- Decision: Treat “make 90 percent win” as a search objective, not permission to overstate the evidence.
  Rationale: A defense that depends on cherry-picking would be weak under scrutiny; the stronger approach is to add diagnostics that could genuinely separate underfitting, practical balance, and over-fragmentation.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

Implementation now reaches the main analytical goal. The script performs the `85..95` sweep by caching all candidate ranks once per analysis unit and reselecting the minimum threshold-satisfying bundle per cutoff, which made it feasible to add local-neighborhood diagnostics without changing the core threshold rule. The output contract now includes burden summaries, adjacent-threshold transition summaries, pooled-structure validity summaries, and richer `run_metadata`.

The current broad-sweep screening result gives a materially stronger defense of `0.90` than the original four-point comparison. The most defensible statement is that `0.90` is the highest tested cutoff that still avoids ceiling-hit artifacts in both `trialwise` and `concatenated`, while `0.91+` begins to introduce ceiling-hit burden without a clear downstream-structure gain. This does not make `0.90` the lightest cutoff; `0.89` remains more parsimonious. The defense rests on strictness-versus-artifact balance, not on minimum complexity.

Validation status is mixed but usable. `--dry-run` succeeds, `py_compile` succeeds, and checksum spot-checks match the saved screening-profile artifacts. A slower exact-profile rerun for `0.89/0.90/0.91` was launched separately and remained in progress at the time of this update, so the current report is explicitly framed as a screening-profile defense rather than a completed default-profile replication.

## Context and Orientation

The relevant working area is `analysis/vaf_threshold_sensitivity`. The existing script, `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py`, reuses the main EMG pipeline to select trials, run non-negative matrix factorization (NMF), and cluster all extracted synergy weight vectors in a pooled step-plus-nonstep space. “VAF” means “variance accounted for,” which is the fraction of the input EMG energy explained by the reconstructed signal. Higher VAF thresholds force the analysis to keep adding synergy components until reconstruction improves enough. “Gap statistic” is the clustering heuristic used to propose a raw number of clusters `K`. “Zero-duplicate feasibility” is a project rule that rejects a raw `K` when the same trial still contributes multiple components to the same pooled cluster. In this repository, `src/synergy_stats/clustering.py` already searches for the first zero-duplicate solution at or above the gap-selected `K`.

The NMF rank-selection logic lives in `src/synergy_stats/nmf.py`. It tries rank `1`, then `2`, and so on, up to `max_components_to_try` from `configs/synergy_stats_config.yaml`. It stops at the first rank that reaches the requested threshold. The current default configuration sets `vaf_threshold: 0.90` and `max_components_to_try: 8`.

The current report in `analysis/vaf_threshold_sensitivity/report.md` already contains threshold-level summaries, per-subject tables, and a short interpretation. However, it only compares `80`, `85`, `90`, and `95`, and it does not yet quantify three questions that matter for a real defense: how often higher thresholds hit the component ceiling, how much clustering complexity is required to resolve duplicates, and whether the selected cutoff improves downstream step-versus-nonstep interpretability.

## Plan of Work

First, expand the analysis script so threshold handling is no longer locked to four coarse defaults. The script should accept and default to the full `85` through `95` sweep. While preserving the existing summary outputs, add richer per-threshold diagnostics that can be written to JSON without requiring external notebooks. These diagnostics should include at minimum:

1. NMF complexity burden. For each mode and threshold, compute component inflation relative to the lower thresholds, ceiling-hit counts and rates against `max_components_to_try`, and a measure of reconstruction efficiency such as “additional achieved VAF per additional average component.”

2. Clustering burden. Preserve the current selected `K` fields, but also save and summarize the gap curve, duplicate-trial counts by `K`, how far `k_selected` rises above `k_gap_raw`, and whether the chosen threshold enters an escalation or extension regime.

3. Local-neighborhood evidence near `0.90`. Compare adjacent thresholds so the report can talk concretely about `89 -> 90` and `90 -> 91`, not only about far-apart endpoints.

Second, add a downstream-validity comparison that uses the threshold-specific pooled clustering outputs to judge whether the resulting structure remains interpretable. The repository already has a good model for pooled cluster diagnostics in `analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py`. Reuse the same style of evidence where possible: cluster occupancy by step versus nonstep, coverage across subjects, and similarity or balance summaries that can reveal when lower cutoffs merge too much or higher cutoffs fragment the space. The downstream analysis does not need to become a separate pipeline; it only needs to produce enough threshold-by-threshold evidence to answer whether `0.90` is the strongest practical compromise.

Third, update the markdown report in place rather than rewriting it from scratch. Keep the current document structure, terminology, and table style. Insert new sections that explicitly distinguish three claims: why low thresholds may underfit, why `0.90` is a practical balance, and why higher thresholds start to over-fragment or saturate. If the new evidence only partially supports `0.90`, say that directly and explain what is strong versus weak.

## Concrete Steps

All commands below run from the repository root: `/home/alice/workspace/26-03-synergy-analysis`.

1. Validate the current input path and baseline analysis loading.

       conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --dry-run

   Expected outcome: the script prints the selected trial count, the subject list, the threshold list, and ends with `Dry run complete.`

2. Extend `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py` to:
   - change the default threshold list to `0.85` through `0.95`,
   - capture richer per-threshold metrics from `feature_rows` and `cluster_result`,
   - optionally generate threshold-diagnostic figures if they materially help the report,
   - continue writing `summary.json`, per-threshold `summary.json`, and `checksums.md5`.

3. If needed, add a small helper in the same analysis folder for downstream pooled-structure summaries. Keep the change additive and self-contained.

4. Update `analysis/vaf_threshold_sensitivity/report.md` with the new findings while preserving the existing heading hierarchy and nearby style.

5. Run the broad sweep screening profile that the updated report now cites.

       conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
         --cluster-repeats 100 \
         --gap-ref-n 100 \
         --gap-ref-restarts 20 \
         --uniqueness-candidate-restarts 100

   Expected outcome: the script prints one block per threshold, shows both `trialwise` and `concatenated` summaries, and writes screening-profile artifacts under `analysis/vaf_threshold_sensitivity/artifacts/default_run`.

6. Optionally run the slower exact-profile local confirmation around the practical neighborhood of `0.90`.

       conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --thresholds 0.89 0.90 0.91 --out-dir analysis/vaf_threshold_sensitivity/artifacts/exact_89_91

   Expected outcome: the script writes a smaller exact-profile artifact set for the `89/90/91` neighborhood.
7. Record and verify checksums.

       md5sum analysis/vaf_threshold_sensitivity/artifacts/default_run/summary.json
       md5sum analysis/vaf_threshold_sensitivity/artifacts/default_run/by_threshold/vaf_90/summary.json
       sed -n '1,120p' analysis/vaf_threshold_sensitivity/artifacts/default_run/checksums.md5

8. Review the diff and run the required review agents before committing.

## Validation and Acceptance

The analysis is acceptable only if all of the following are true.

The script can still complete `--dry-run` successfully and can still execute the documented screening-profile rerun from the repository root with the `cuda` conda environment. The regenerated artifacts include the full `85` through `95` sweep. The report contains explicit evidence for the neighborhood around `0.90`, not just endpoint comparisons. The final interpretation clearly states whether `0.90` is defended by a balance of reconstruction, clustering burden, and interpretability. The generated checksums must match the freshly written screening-profile artifacts. If the expanded diagnostics expose a stronger rival cutoff, that fact must be reported rather than hidden.

## Idempotence and Recovery

The analysis script should remain safe to rerun multiple times. Regenerating the same artifact paths is expected and should overwrite stale outputs with current ones. If a full run fails midway, fix the underlying script issue and rerun the same command; there is no destructive migration step. Do not touch unrelated dirty files in the worktree. If the script produces extra scratch files that are not part of the final artifact contract, delete them before finishing.

## Artifacts and Notes

Important final artifacts should remain inside `analysis/vaf_threshold_sensitivity/artifacts/default_run` for the broad screening profile, with optional exact-profile neighborhood checks written to a separate out-dir such as `analysis/vaf_threshold_sensitivity/artifacts/exact_89_91`. If figures are added, keep them under a predictable subdirectory such as `figures/` and include them in the checksum file only when they are part of the intended deliverable set.

The final report should make it easy to answer three novice-facing questions:

1. What gets better when the cutoff rises from the high eighties to `0.90`?
2. What gets worse when the cutoff rises above `0.90`?
3. Why is `0.90` the most defensible practical setting in this pipeline?

## Interfaces and Dependencies

This work must continue to use the repository’s source-of-truth pipeline code rather than reimplementing NMF or clustering inside the analysis folder. Specifically:

- Use `src.emg_pipeline.build_trial_records`, `load_emg_table`, `load_event_metadata`, `load_pipeline_config`, and `merge_event_metadata` for input preparation.
- Use the same low-level NMF rank fitting and VAF computation primitives as `src.synergy_stats.nmf`, but allow this analysis script to cache all candidate ranks once per unit and then reselect the minimum threshold-satisfying bundle across multiple cutoffs.
- Use the same concatenated super-trial preparation logic as `src.synergy_stats.concatenated`, while allowing this analysis script to split averaged activation profiles back into threshold-specific feature rows for each source trial.
- Use `src.synergy_stats.clustering.cluster_feature_group` for pooled clustering and `K` selection.
- Read default rank and clustering bounds from `configs/synergy_stats_config.yaml`.

Any new helper function added to the analysis script should remain local to `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py` unless more than one existing module genuinely needs it.

Revision note: created on 2026-03-19 to support a focused defense of the `VAF >= 0.90` cutoff with finer-grained sensitivity and downstream-structure diagnostics.
