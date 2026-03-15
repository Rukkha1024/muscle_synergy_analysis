# Review Rubric

## A. Reproducibility Checks
- Script runs successfully with `conda run -n module python`.
- Required outputs are generated (`fig*.png`, stdout summary).
- Model set in code matches report claims.

## B. Quantitative Consistency Checks
- AUC / coefficient / OR / p-value in report match run logs.
- Trial counts and window definitions are consistent.
- No stale values remain from previous analysis versions.

## C. Statistical Interpretation Checks
- Claims match actual effect sizes and significance.
- Avoid overclaiming from non-significant results.
- Distinguish predictive performance from mechanistic causality.

## D. Method/Implementation Alignment
- Variable definitions in report match code formulas.
- Decision rules (windowing, grouping, LOSO, etc.) match implementation.

## E. Severity Assignment
- High: reproducibility failure, numeric mismatch, core method mismatch
- Medium: interpretation risk or methodological ambiguity
- Low: wording/format improvements
