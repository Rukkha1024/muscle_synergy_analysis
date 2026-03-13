# Issue 005: Audit Duplicate Cluster Assignment Within Trial Units

**Status**: Done
**Created**: 2026-03-13

## Background

The repository now contains two relevant clustering paths for muscle synergy interpretation. The production path under `scripts/emg/` and `src/synergy_stats/` uses trial-level NMF features plus a duplicate-prevention reassignment step, while `analysis/compare_Cheung,2021/` contains a paper-like plain k-means plus gap-statistic path without that safeguard.

The user wants a reproducible audit that measures how often same-trial duplicate cluster assignment actually occurs, where the production reassignment intervenes, how much assignment cost it adds, and whether the issue is large enough to affect downstream biological interpretation. The audit must be isolated from production logic, grounded only in repository code/config/output, and leave behind reusable scripts, tabular outputs, plots, and a written summary.

## Acceptance Criteria

- [x] A standalone audit entrypoint exists outside the production pipeline and does not modify production logic.
- [x] The audit maps the actual NMF, normalization, clustering, gap-statistic, matching, and reassignment paths with exact file and function names.
- [x] The audit computes duplicate metrics for paper-like unconstrained clustering and for production pre/post forced reassignment states.
- [x] The audit measures reassignment cost changes, transition patterns, and any remaining duplicate exceptions.
- [x] The audit writes the requested results under `results/duplicate_assignment_audit/` and includes a top-level `summary.md`.
- [x] The audit adds a regression check that exercises the uniqueness-enforcement path in `src/synergy_stats/clustering.py`.
- [x] Validation, explorer, and reviewer passes complete before finalization.

## Tasks

- [x] 1. Create bilingual ExecPlans that lock the audit scope, data sources, metrics, and validation steps.
- [x] 2. Implement an isolated audit script that reconstructs both the paper-like and production clustering states from repo code.
- [x] 3. Generate summary tables, duplicate-pair exports, K-sensitivity outputs, and plots under `results/duplicate_assignment_audit/`.
- [x] 4. Add a focused regression test for the production uniqueness-enforcement behavior.
- [x] 5. Run the audit and validation commands, then record key findings and caveats.
- [x] 6. Complete explorer/reviewer passes and commit with a Korean message of at least five lines.

## Notes

- The audit entrypoint is `analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`.
- Generated outputs live under `results/duplicate_assignment_audit/` and include `summary.md`, `overall_metrics.csv`, `per_unit_metrics.csv`, `duplicate_pairs.csv`, `per_cluster_stats.csv`, `k_sensitivity.csv`, `reassignment_stats.csv`, and plots.
- Validation completed with:
  `conda run --no-capture-output -n module python -m py_compile analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py tests/test_synergy_stats/test_duplicate_assignment_audit.py`
  `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`
  `conda run --no-capture-output -n module pytest tests/test_synergy_stats/test_duplicate_assignment_audit.py`
- Key measured findings:
  paper-like duplicate unit rate `28/125 = 0.224`
  production pre-force duplicate unit rate `35/125 = 0.280`
  production post-force duplicate unit rate `0/125 = 0.000`
  reassigned synergies `44/486 = 0.091`
- Explorer and reviewer passes reported no concrete implementation findings. Residual risks are the intentional `compare_Cheung` runtime override alignment (`10/5/3` rather than the code defaults `1000/500/100`) and the audit script's dependence on private helper functions.
