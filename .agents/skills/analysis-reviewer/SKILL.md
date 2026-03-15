---
name: analysis-reviewer
description: Review and repair existing analysis workflows under analysis/* by validating reproducibility, quantitative consistency, statistical interpretation, and paper-method alignment; auto-fix High issues only; default to console-first reporting.
---

# Analysis Reviewer

## Trigger

Use this skill when the user asks to:
- review an existing analysis folder under `analysis/`
- verify whether script outputs match `report.md`
- identify problematic methods or over-claims
- fix incorrect analysis logic or mismatched quantitative reporting

## Non-Trigger

Do not use this skill when:
- creating a brand-new analysis topic from scratch (use `analysis-report`)
- editing prose only without technical validation
- tasks are outside `analysis/*`

## Scope

This skill only targets analysis folders with:
- `analyze_*.py`
- `report.md`

Default scope is one folder unless the user explicitly asks for multiple folders.

## Defaults (Decision-Locked)

- Review scope: `analysis/*` standard analysis folders only
- Fix mode: Hybrid
- Auto-fix: High severity only
- Reporting mode: Console-first
- `report.md` edits: only when explicitly requested
- Literature checks: automatic if paper/PDF/citation is mentioned

## Severity Rubric

- High:
  - script fails to run or cannot reproduce core outputs
  - quantitative mismatch between script stdout and report tables/claims
  - wrong analysis window/model definition versus stated method
  - core method mismatch with cited literature (definition/formula/decision logic)

- Medium:
  - interpretation overstatement or weak statistical phrasing
  - incomplete caveats or non-critical method ambiguity

- Low:
  - wording clarity, formatting, naming consistency improvements

## Mandatory Workflow

1. Discover target and verify expected files exist.
2. Run static checks on `analyze_*.py` and `report.md` (definitions, model list, window rules, metric names).
3. Execute analysis script and capture actual quantitative outputs.
4. Cross-check stdout numbers versus `report.md` values.
5. If literature is referenced, run method-alignment check.
6. Produce findings in High -> Medium -> Low order with file/line evidence.
7. Auto-fix High issues only.
8. Re-run analysis and verify corrected quantitative outputs.
9. Report final console summary with actual numbers and applied fixes.

## Auto-Fix Policy

Auto-fix only High issues. Examples:
- execution-breaking code defects
- incorrect metric extraction
- incorrect model set/window logic
- report numeric mismatches when report editing is explicitly requested

Do not auto-fix Medium/Low by default.

## Console Output Contract

Always output in this order:
1. Findings (High -> Medium -> Low)
2. Applied Fixes (High only)
3. Actual Quant Results (measured values, not expected values)
4. Open Questions / Assumptions
5. Optional Next Actions

Each finding must include:
- severity
- file path + line
- evidence
- impact
- action

## Environment / Repo Rules

- Always run Python as: `conda run -n cuda python ...`
- Prefer `polars` then `pandas`
- Keep analysis outputs as stdout + `report.md` (no Excel/CSV unless user explicitly asks)
- Do not modify unrelated files
- Do not rewrite `report.md` unless explicitly requested

## References

- Review rubric: `references/review_rubric.md`
- Literature alignment protocol: `references/literature_check.md`
- Output format contract: `references/console_output_contract.md`
