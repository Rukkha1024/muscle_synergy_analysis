# Issue 006: EMG Clustering Audit Workbook Export

**Status**: Done
**Created**: 2026-03-14

## Background

The EMG synergy pipeline already computes the key evidence needed to explain why a clustering solution was accepted, including the gap-statistic result, the raw gap-selected `K`, and the duplicate-trial burden across candidate `K` values. However, those diagnostics are currently packed into CSV JSON fields that are harder to inspect directly in Excel.

The user wants the clustering evidence to be delivered as a single Excel workbook saved in each run output directory. The workbook must show both the selection rationale and the duplicate details in a format that is easy to read in Excel, including a built-in guide that explains how to interpret the tables and a small example.

## Acceptance Criteria

- [x] Each pipeline run writes `clustering_audit.xlsx` under the run output directory.
- [x] The workbook contains `summary`, `duplicates`, and `table_guide` sheets.
- [x] The `summary` sheet always includes a reading guide and a worked example above the tables.
- [x] The workbook exports both duplicate trial summaries and duplicate cluster details.
- [x] Existing stable CSV outputs remain compatible at the code level; no full pipeline rerun was performed in this turn because the user requested tests-only validation.
- [x] The Excel workflow skill is updated to require a reading guide and example in summary sheets for audit-style workbooks.

## Tasks

- [x] 1. Extend clustering diagnostics to preserve workbook-ready duplicate evidence by candidate `K`.
- [x] 2. Add workbook export and validation helpers for the clustering audit workbook.
- [x] 3. Wire workbook generation into the artifact export stage.
- [x] 4. Add or update tests for workbook content and duplicate evidence serialization.
- [x] 5. Update README and Excel skill guidance for the new workbook pattern.
- [x] 6. Run validation, reviewer checks, and commit with a Korean five-line message.

## Notes

- Main implementation files:
  - `src/synergy_stats/clustering.py`
  - `src/synergy_stats/artifacts.py`
  - `src/synergy_stats/excel_audit.py`
- Main tests:
  - `tests/test_synergy_stats/test_clustering_contract.py`
  - `tests/test_synergy_stats/test_excel_audit.py`
- Workbook structure:
  - `summary`
  - `duplicates`
  - `table_guide`
- Environment note:
  - This turn implemented the workbook with an `openpyxl` fallback and recorded that Excel UI visual QA was skipped because desktop Excel automation was unavailable in the active environment.
- Validation completed with:
  - `conda run --no-capture-output -n module python -m py_compile src/synergy_stats/clustering.py src/synergy_stats/artifacts.py src/synergy_stats/excel_audit.py tests/test_synergy_stats/test_clustering_contract.py tests/test_synergy_stats/test_excel_audit.py`
  - `conda run --no-capture-output -n module python -m pytest tests/test_synergy_stats/test_clustering_contract.py tests/test_synergy_stats/test_excel_audit.py -q`
- Residual limitation:
  - The user requested test-only validation, so a full pipeline rerun and curated MD5 comparison were intentionally skipped in this turn.
