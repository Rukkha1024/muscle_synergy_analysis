# Issue 005: Standalone compare_Cheung Duplicate Assignment Audit

**Status**: Done
**Created**: 2026-03-13

## Background

The user narrowed the source of truth to `analysis/compare_Cheung,2021/`. That paper-like workflow uses ordinary pooled k-means plus gap statistic over trial-level NMF synergy vectors, and it is the path that should determine whether same-trial duplicate cluster assignment is a real practical issue.

Because the production pipeline already forces uniqueness with its own reassignment path, this issue is no longer about auditing production behavior. Instead, the work must live as an independent `analysis/` task that reruns the `compare_Cheung` code path, measures duplicate burden, documents that no within-trial uniqueness enforcement exists in that path, and leaves behind a self-contained report, README, verification script, and reproducible local artifacts.

## Acceptance Criteria

- [x] The audit lives under `analysis/duplicate_assignment_audit/` as a standalone analysis workflow.
- [x] The source of truth is `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`.
- [x] The audit report answers the four user questions using compare_Cheung-only evidence.
- [x] The workflow writes its reproducible artifacts under `analysis/duplicate_assignment_audit/results/`.
- [x] A `README.md` explains how to run and verify the analysis.
- [x] A Python verification script remains alongside the analysis code.
- [x] Validation, explorer, and reviewer passes complete before finalization.

## Tasks

- [x] 1. Narrow the issue scope from “paper-like plus production comparison” to “compare_Cheung-only duplicate audit”.
- [x] 2. Refactor `analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py` to remove production reassignment analysis.
- [x] 3. Generate `analysis/duplicate_assignment_audit/report.md` and local `results/` artifacts from the compare_Cheung path.
- [x] 4. Add `analysis/duplicate_assignment_audit/README.md` and `analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`.
- [x] 5. Remove obsolete top-level audit outputs and production-only validation leftovers created by the earlier broader scope.
- [x] 6. Run analysis, run verification, complete explorer/reviewer passes, and commit with a Korean message of at least five lines.

## Notes

- Main entrypoint: `analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`
- Verification entrypoint: `analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`
- Main report: `analysis/duplicate_assignment_audit/report.md`
- Artifact directory: `analysis/duplicate_assignment_audit/results/`
- Key measured findings:
  - raw duplicate unit rate `28/125 = 0.224`
  - raw excess duplicate ratio `30/503 = 0.060`
  - raw duplicate pair rate `30/852 = 0.035`
  - selected K `global_step=11`, `global_nonstep=6`
  - no forced reassignment stage exists in the compare_Cheung code path
- Validation completed with:
  - `conda run --no-capture-output -n module python -m py_compile analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`
  - `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py --dry-run`
  - `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py`
  - `conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py`
- Residual risk:
  - the audit intentionally uses the checked-in compare_Cheung runtime overrides `10/5/3` rather than the script defaults `1000/500/100` so that the duplicated-assignment results line up with the committed compare_Cheung report.
