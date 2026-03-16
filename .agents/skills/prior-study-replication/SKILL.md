---
name: prior-study-replication
description: "Companion to analysis-report. Provides report.md structure for analyses that replicate or follow a prior study's methodology. Enforces: prior study methods/results/conclusions → methodological adaptation rationale → user data results → systematic comparison with prior findings."
---

# Prior Study Replication Report

## Trigger

- Analysis that replicates, follows, or extends a specific published study's methodology
- Requests like "follow the paper's method", "replicate study X", "apply method from Y to our data"
- Analysis where results should be compared against published findings

## Non-Trigger

- Exploratory analyses with no specific prior study to follow
- Descriptive statistics only (no methodological replication involved)
- Novel analyses where the user defines the method from scratch

## Relationship to Other Skills

- **Always use together with `analysis-report`** — that skill handles folder structure, code rules, environment notes, color conventions, script boilerplate, and the required `README.md` that explains why the analysis subfolder exists plus the user's goal
- This skill **only** defines the `report.md` structure
- Use `analysis-report/templates/script_boilerplate.py` for the Python script
- Use **this skill's** `templates/report_template.md` for the report

## Report Structure (mandatory sections, strict order)

| # | Section | Purpose |
|---|---------|---------|
| 1 | Research Question | Upper context (why this analysis) + core question |
| 2 | **Prior Studies** | Each referenced study's methodology, experimental design, key results (with numbers), and conclusions |
| 3 | **Methodological Adaptation** | Mapping table: prior method → current implementation. Explicit rationale for any deviations |
| 4 | Data Summary | Data sources, N, key variables |
| 5 | Analysis Methodology | Statistical model, analysis window, variable definitions |
| 6 | Results | Statistical tables, effect sizes, figures |
| 7 | **Comparison with Prior Studies** | Side-by-side comparison table with agreement/disagreement verdicts |
| 8 | Interpretation & Conclusion | Findings interpreted in context of prior study comparison |
| 9 | Limitations | Methodological constraints, generalization caveats |
| 10 | Reproduction | Run command, inputs, outputs |
| 11 | Figures | File-description table |

## Section-Specific Rules

### Prior Studies

- One subsection per referenced paper: `### Author et al. (Year) — short title`
- Each subsection MUST include all four items:
  - **Methodology**: Model, variables, analysis approach
  - **Experimental design**: N subjects, equipment, protocol
  - **Key results**: Specific numbers (e.g., "r ≈ 0.54", "AUC = 0.71", "predicted 11% of stepping")
  - **Conclusions**: Authors' main takeaway in 1-2 sentences
- Include reference paper PDFs in the analysis folder when available

### Methodological Adaptation

- MUST contain a comparison table with columns: `Prior Method | Current Implementation | Deviation Rationale`
- Every row where the method was NOT replicated 1:1 MUST have a rationale (e.g., equipment constraints, missing parameters, coordinate system incompatibility)
- End with a summary sentence: "This analysis adopts [aspect X] from [study] but modifies [aspect Y] because [reason]."

### Comparison with Prior Studies

- MUST contain a comparison table with columns: `Comparison Item | Prior Study Result | Current Result | Verdict`
- Verdict values: `Consistent` / `Partially consistent` / `Inconsistent` / `Not tested`
- Any `Inconsistent` or `Not tested` item MUST include a brief explanation

### Results Reporting Convention (default)

- User-facing Results tables should hide numeric `p` values and `df` unless the user explicitly requests them.
- Use `p < 0.05` as the significance threshold (`alpha=0.05`).
- Report significance with `Sig` only: significant = `< 0.05`, non-significant = `n.s.`.
- If multiple comparison correction is used, compute `Sig` from corrected p-values (e.g., BH-FDR) and name the method in Analysis Methodology.
- For metrics named `*_peak`, define the term explicitly as absolute peak: `abs_peak = max(|x|)` within the analysis window.

## Validation

- `README.md` exists per `analysis-report` and explains why the subfolder exists and the user's goal
- report.md contains all 11 mandatory sections in order
- Prior Studies: ≥1 study with all four items (methodology, design, results, conclusions) with specific numbers
- Methodological Adaptation: comparison table present; all deviation rows have rationale
- Comparison with Prior Studies: comparison table present with verdicts; inconsistencies explained
- All numbers in Comparison table match Results section and Prior Studies section
- Results tables follow `Sig-only` convention by default (no numeric `p`/`df` columns unless requested)

## Completion Checklist

- [ ] `README.md` follows the `analysis-report` folder rule and documents the subfolder purpose plus the user's goal
- [ ] `report.md` follows this skill's template (not `analysis-report` template)
- [ ] Prior Studies section has concrete numbers from each referenced paper
- [ ] Methodological Adaptation table explains all deviations
- [ ] Comparison table has verdicts for all items
- [ ] Reference PDFs included in analysis folder (if available)
