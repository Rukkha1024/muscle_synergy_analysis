---
name: analysis-report
description: "Create self-contained analysis workflows under analysis/. Each folder bundles a script (.py) and report (report.md). No Excel/CSV output. Produces a report with research question, methodology, results, interpretation structure."
---

# Analysis Report Workflow

## Trigger

- Starting a new analysis topic (research question, exploratory analysis)
- Requests to work under the `analysis/` folder
- Need to bundle statistics + reporting into a single self-contained folder
- Standalone analyses independent of the codebase script. 

## Non-Negotiable Rules

### Folder Structure

```
analysis/<topic>/
  analyze_<topic>.py      # single entry point
  report.md               # research report
```

- Folder name: `snake_case`, descriptive of the analysis topic
- Script: `analyze_<topic>.py` (single entry point)
- Report: `report.md` (always present)

### Output Constraints

- **No Excel/CSV generation** — use stdout statistics and `report.md` for reproducible outputs
- If intermediate data is needed, process in memory; do not export to files

### Reporting Conventions (default)

- User-facing report tables should hide numeric `p` values and `df` by default.
- Use `p < 0.05` as the significance threshold (`alpha=0.05`).
- Report significance with `Sig` only: significant = `< 0.05`, non-significant = `n.s.`.
- If multiple comparison correction is used, compute `Sig` from the corrected p-values (e.g., BH-FDR) and state the correction method in Analysis Methodology.
- If variables use `*_peak`, define it explicitly as absolute peak: `abs_peak = max(|x|)` within the analysis window.
- Analysis Methodology must include a **Coordinate & sign conventions** block using the following 3 tables:
- `Axis & Direction Sign`
- `Signed Metrics Interpretation`
- `Joint/Force/Torque Sign Conventions`
- Required table schema 1: `Axis | Positive (+) | Negative (-) | 대표 변수`
- Required table schema 2: `Metric | (+) meaning | (-) meaning | 판정 기준/참조`
- Required table schema 3: `Variable group | (+)/(-) meaning | 추가 규칙`
- Coordinate/sign tables must define both axis names and `(+)/(-)` meanings for AP/ML/Vertical directions.
- For signed metrics (e.g., `MOS_minDist_signed`, `MOS_AP_v3d`, `MOS_ML_v3d`), report what `(+)/(-)` means in biomechanical terms (inside/outside or bound-relative sign).
- For joint angles, report axis-wise sign semantics (X/Y/Z) and whether left/right sign-unification was applied.
- For force/torque/COP variables, state whether each signal is absolute or onset-zeroed and whether internal/external torque sign conversion was used.
- Directional interpretation text in `Interpretation` must remain consistent with the table-defined sign conventions.

### Code Rules

- Prefer `polars`; use `pandas` when stats APIs require it (pingouin, scipy) **or** for R subprocess CSV I/O
- Use `argparse` to allow input path overrides
- **`--dry-run` flag is mandatory** — loads data and prints summary without running analysis
- Milestone-based `main()` structure: `[M1] Load → [M2] Stats`
- Use `templates/script_boilerplate.py` as the starting point for every new script

### Environment Notes

- **R subprocess (when needed)**: `rpy2` is broken on Windows conda (R not built as shared library). Use `Rscript.exe` via `subprocess.run()` with explicit `R_HOME`/`PATH` env vars. See `analysis/step_vs_nonstep_lmm/analyze_step_vs_nonstep_lmm.py` lines 62-82 for the pattern.

## Templates

- **Script boilerplate**: `templates/script_boilerplate.py` — copy and modify for each new analysis
- **Report template**: `templates/report_template.md` — includes Analysis Methodology section

## Companion Skills

- **Prior-study-based analyses**: When replicating or following a published study's methodology, use `prior-study-replication` skill alongside this one. That skill provides an alternative `report.md` template with mandatory sections for prior study methods/results, methodological adaptation rationale, and systematic comparison. Code rules and folder structure still follow this skill.

## Workflow

1. **Define research question** — Confirm core question, hypotheses, and required data with the user
2. **Create folder** — Create `analysis/<topic>/` directory
3. **Write script** — Copy `templates/script_boilerplate.py` → `analyze_<topic>.py`, then customize
   - Data loading → preprocessing → statistics → stdout output
4. **Dry-run verify** — `conda run --no-capture-output -n module python analysis/<topic>/analyze_<topic>.py --dry-run`
   - Confirm data loads correctly, trial counts match expectations
5. **Full run & verify** — Remove `--dry-run` flag and confirm statistics are produced as expected
6. **Write report** — Use `templates/report_template.md` as starting point for `report.md`
   - Research question → data summary → **analysis methodology (including the 3 Coordinate & sign convention tables)** → results → interpretation → reproduction
7. **Commit** — commit the entire analysis folder

## Validation

- `analyze_<topic>.py --dry-run` succeeds (data loading OK)
- `analyze_<topic>.py` full run completes without errors
- `report.md` exists with required sections: Research Question, Data Summary, **Analysis Methodology**, Results, Interpretation, Reproduction
- Key statistics printed to stdout match report.md content
- No Excel/CSV files generated
- User-facing report tables follow `Sig-only` convention (no numeric `p`/`df` columns unless user explicitly requests)
- `report.md` includes all 3 coordinate/sign tables (`Axis & Direction Sign`, `Signed Metrics Interpretation`, `Joint/Force/Torque Sign Conventions`) with required headers
- `report.md` explicitly documents coordinate/sign conventions (`(+)/(-)` direction meaning) for main variables and signed metrics
- Directional interpretation text is consistent with the declared methodology sign conventions

## Completion Checklist

- [ ] `analysis/<topic>/` folder exists
- [ ] `analyze_<topic>.py --dry-run` succeeds
- [ ] `analyze_<topic>.py` full run completes without errors
- [ ] `report.md` complete (all required sections present, including Analysis Methodology)
- [ ] stdout statistics match report.md content
- [ ] No Excel/CSV files present
- [ ] Committed
