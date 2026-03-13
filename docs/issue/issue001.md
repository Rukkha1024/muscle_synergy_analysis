# Issue 001: Restore professor-style retry-based KMeans selection in compare_professor

**Status**: Done
**Created**: 2026-03-13

## Background

`analysis/compare_professor/compare_step_nonstep_professor_logic.py` currently runs one `KMeans` fit per `K` and falls back to Hungarian repair if no duplicate-free solution is found. The professor reference code retries clustering with different initializations and selects from successful candidate solutions. This work restores that retry-based selection behavior so the comparison script better matches the professor-style clustering logic while keeping the current fallback as a last-resort safety path.

## Acceptance Criteria

- [x] `compare_step_nonstep_professor_logic.py` retries `KMeans` across multiple seeds instead of testing each `K` only once.
- [x] The script selects a duplicate-free candidate from retry results and records the selection metadata in outputs.
- [x] The script still supports a final fallback path when retry-based selection cannot find a valid solution.
- [x] The analysis script runs successfully and repeat runs are validated with MD5 checksums.

## Tasks

- [x] 1. Update the clustering function to collect retry candidates and choose a final solution.
- [x] 2. Add CLI and summary metadata for retry-based selection.
- [x] 3. Refresh the compare-professor documentation to describe the new clustering behavior.
- [x] 4. Re-run the analysis script and compare output checksums across repeated runs.

## Notes

- Implemented professor-style retry search as `retry -> K` loops with `random_state = seed + retry` and `n_init = 1`.
- Selected the final solution by `mode K + lowest inertia` because the professor code's later ICC-based selection step was not ported into this comparison script.
- Verified deterministic reruns before cleanup; the latest retained result is `analysis/compare_professor/artifacts/professor_step_nonstep_compare_retry_rerun`.
- Confirmed that the old fallback-centered reference outputs changed after the retry-based selection logic was restored.
