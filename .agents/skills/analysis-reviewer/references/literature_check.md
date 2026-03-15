# Literature Alignment Protocol

## Trigger
Run this protocol when:
- report mentions a paper/study
- a PDF is present in the analysis folder
- user asks for paper-method verification

## Procedure
1. Extract claimed method elements from report/code:
   - definitions
   - formulas
   - decision boundaries
   - statistical model framing
2. Extract corresponding elements from the paper.
3. Compare item-by-item and assign:
   - Exact: practically equivalent
   - Partial: conceptually aligned with implementation differences
   - Mismatch: core method/logic does not match
4. Report each item with:
   - verdict
   - basis (code line + paper section/page)
   - impact on conclusions
   - corrective action

## Output Rule
If full text is unavailable, explicitly mark inference limits.
