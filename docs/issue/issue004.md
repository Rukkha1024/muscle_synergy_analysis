# Issue 004: Align `compare_Cheung,2021` with the PDF for plain k-means and NMF

**Status**: Done
**Created**: 2026-03-13

## Background

`analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py` currently mixes paper-inspired logic with project-specific adaptations. The biggest gap is clustering: the script enforces a within-trial duplicate-free reassignment path, adds prototype gating, and only reaches the paper's heavy gap-statistic runtime through a special flag. Its NMF selection rule is close to the PDF, but the current `R²` definition and runtime defaults are still not aligned enough with the paper for the user's goal.

The user wants this analysis revised so that, while the repository keeps its 16-channel perturbation EMG input and baseline trial/window truth, the NMF and k-means stages follow the PDF more closely. That means plain k-means over `K = 2..20`, paper-style gap-statistic repeat counts, and a paper-aligned `R²` interpretation for rank selection. The README and generated report text must be updated so the method description stays consistent with the code.

## Acceptance Criteria

- [x] `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py` no longer contains or calls a duplicate-free reassignment path for clustering.
- [x] The clustering search evaluates plain k-means over `K = 2..20` per group, capped only by the mathematical sample limit.
- [x] The default clustering runtime uses the paper-aligned repeat counts for observed and reference-data gap-statistic searches.
- [x] The NMF stage keeps 16 channels but uses the paper-style rank search, restart rule, `R² >= 0.80` minimum-rank rule, and a centered-variance `R²` definition.
- [x] `analysis/compare_Cheung,2021/README.md` and the generated `analysis/compare_Cheung,2021/report.md` explain the revised method without stale duplicate-free or `--paper-full` wording.
- [x] The revised analysis completes in dry-run and full-run modes, and repeated full runs produce reproducible output checksums.
- [x] Explorer and reviewer passes finish without unresolved concrete findings.

## Tasks

- [x] 1. Create the revision ExecPlan and lock the implementation scope to the approved PDF-alignment changes.
- [x] 2. Replace duplicate-free clustering, prototype gating, and paper-full runtime branching with plain k-means plus paper-default gap-statistic counts.
- [x] 3. Update the NMF `R²` calculation so it matches the approved centered-variance interpretation while keeping the 16-channel adaptation.
- [x] 4. Regenerate or rewrite the method descriptions in the README and report so they match the new implementation.
- [x] 5. Run dry-run and full-run validation, record MD5 outputs, and document expected differences from the pre-revision analysis outputs.
- [x] 6. Complete explorer/reviewer checks and commit with a Korean message of at least five lines.

## Notes

- The revision added `analysis/compare_Cheung,2021/exceplan_compare_cheung_pdf_alignment_revision.md` so the new PDF-alignment change is tracked separately from the earlier completed ExecPlan.
- The analysis script now defaults to paper-aligned clustering counts (`kmeans_restarts=1000`, `gap_ref_n=500`, `gap_ref_restarts=100`) while still allowing CLI overrides for tractable local validation.
- Validation completed with:
  `python3 -m py_compile analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`
  `conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py --dry-run`
  `conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py --kmeans-restarts 10 --gap-ref-n 5 --gap-ref-restarts 3`
- The reduced-count validation run completed twice with the same reported clustering summary: `step optimal_k=11`, `nonstep optimal_k=6`, matched step-to-nonstep centroid pairs `=6`.
- `analysis/compare_Cheung,2021/checksums_validation_final_run1.md5` and `analysis/compare_Cheung,2021/checksums_validation_final_run2.md5` are identical, and `md5sum -c analysis/compare_Cheung,2021/checksums.md5` passes for the current checked-in artifacts.
- Explorer pass confirmed that the active `main()` flow no longer contains the old prototype or `--paper-full` branching, and the final reviewer pass reported no concrete findings in the scoped diff.
- `analysis/compare_Cheung,2021/checksums_before_pdf_alignment.md5` captures the pre-revision artifacts. The current `analysis/compare_Cheung,2021/checksums.md5` differs as expected because the NMF `R²` definition, clustering path, figures, and report all changed.
