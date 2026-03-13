# Issue 003: Align professor comparison cluster figures with the pipeline figure style

**Status**: Done
**Created**: 2026-03-13

## Background

`analysis/compare_professor/compare_step_nonstep_professor_logic.py` currently renders its cluster centroid figures with a custom one-column bar chart that does not match the repository's pipeline output style. The user wants the professor comparison figures to use the same visual language as the pipeline so the results are easier to compare directly.

## Acceptance Criteria

- [x] The professor comparison script reuses the pipeline cluster figure style for the centroid PNG outputs.
- [x] The output file names for the professor centroid figures remain unchanged.
- [x] The script is rerun successfully and the changed PNG outputs are validated against the previous reference files.
- [x] Shared figure tests and a review pass complete without unresolved findings.

## Tasks

- [x] 1. Replace the custom centroid plotting path with the shared pipeline renderer.
- [x] 2. Preserve the NMF activation timecourses needed to build pipeline-style `H` panels.
- [x] 3. Re-run the professor comparison output generation and record MD5 differences versus the prior artifacts.
- [x] 4. Run targeted validation and complete explorer/reviewer checks before finalizing.

## Notes

- The target scope is limited to figure generation in `analysis/compare_professor/compare_step_nonstep_professor_logic.py`.
- The rerun kept `professor_trial_summary.csv` and `summary.json` unchanged while only the two centroid PNG files changed.
- Validation completed with `conda run -n module python ...compare_step_nonstep_professor_logic.py --overwrite`, `conda run -n module python -m py_compile ...`, and `conda run -n module python -m pytest tests/test_synergy_stats/test_figures_headless_backend.py`.
- Reviewer sign-off noted no remaining concrete bugs in the figure-style change after the activation scaling fix.
