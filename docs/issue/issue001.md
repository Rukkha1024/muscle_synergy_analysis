# Issue 001: Implement the approved EMG synergy architecture scaffold plan

**Status**: In Progress
**Created**: 2026-03-06

## Background

The repository has an approved ExecPlan at `.agents/execplans/repo_architecture_scaffold_execplan_en.md`,
but the runnable pipeline, domain packages, configs, tests, and verification flow do not exist yet.
This work implements that approved plan inside the repository architecture defined by `configs/`, `src/`,
`scripts/`, `outputs/`, and `analysis/`.

## Acceptance Criteria

- [ ] The repository contains a runnable `main.py` orchestrator plus `src/emg_pipeline/` and `src/synergy_stats/`.
- [ ] The pipeline can run from fixture inputs and write subject outputs, aggregated CSVs, `run_manifest.json`, and `outputs/final.parquet`.
- [ ] Tests cover trial slicing, NMF behavior, clustering duplicate policy, and output artifact presence.
- [ ] A curated MD5 comparison can compare stable outputs against a reference baseline.
- [ ] The living ExecPlan, README, and environment docs reflect the implemented workflow.

## Tasks

- [x] 1. Normalize the top-level directory scaffold (`configs/`, `outputs/`, `archive/`).
- [x] 2. Add the root orchestrator, domain packages, and numbered EMG script wrappers.
- [ ] 3. Add fixture inputs and pytest coverage for the new pipeline.
- [ ] 4. Run fixture execution and curated MD5 verification.
- [ ] 5. Update markdown living documents and finalize with a Korean commit.

## Notes

The approved ExecPlan already serves as the implementation plan, so this issue tracks execution progress rather
than creating a second plan. The repository rule still requires keeping the issue, ExecPlan, and tests aligned.
