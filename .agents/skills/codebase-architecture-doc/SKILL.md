---
name: codebase-architecture-doc
description: Enforce and apply the repository architecture rules defined in Codebase_Architecture_Document.md (domain-isolated src/, scripts pipeline vs analysis separation, YAML configs/, outputs conventions, and new-domain scaffolding). Use when deciding where code belongs, what context to provide to Codex, or how to structure new domains, pipeline scripts, analysis folders, configs, and tests.
---

# Codebase Architecture Doc

## Authoritative reference

Read `references/Codebase_Architecture_Document.md` first and treat it as the source of truth.

## Operating rules (checklist)

- Domain isolation: work within one `src/{domain}/` at a time.
- Pipeline vs analysis separation: `scripts/` produces `outputs/final.parquet`; `analysis/` consumes it and stays independent.
- Analysis folder structure: every new `analysis/{topic}/` subfolder must include `README.md`, `analyze_<topic>.py`, and `report.md`; the README must explain why the folder exists and the user's goal.
- Main orchestrator: the project root must include a `main.py` that orchestrates pipeline execution in an explicitly defined order.
- Centralized configuration: keep parameters in `configs/*.yaml` (avoid hard-coded values).
- Raw data is read-only: never modify `data/raw/`.

## Task → where to work

- Modify reusable logic: `src/{domain}/` (and corresponding `tests/test_{domain}/`).
- Add or change pipeline steps: target `scripts/NN_{domain}.py` + the relevant `src/{domain}/` + `configs/{domain}_config.yaml`.
- Change pipeline orchestration / step ordering: `main.py` + the affected `scripts/` steps (+ relevant `src/{domain}/` + configs).
- Add statistical analysis: `analysis/{topic}/` with `README.md`, `analyze_<topic>.py`, and `report.md`, reading only `outputs/final.parquet`.

## New domain scaffolding

When adding a new domain, create these together:

- `src/{new_domain}/`
- `configs/{new_domain}_config.yaml`
- `tests/test_{new_domain}/`

## Prompting / context packaging

When asking Codex to make changes, provide only the minimum relevant context:

- For `src/` work: `src/{domain}/` + `configs/{domain}_config.yaml` (+ tests if relevant).
- For `scripts/` work: the target script + `src/{domain}/` + config.
- For orchestration / run-order changes: include `main.py` + only the specific `scripts/` steps and domain folders/configs involved (avoid providing multiple unrelated domains).
- For `analysis/` work: the analysis folder, its `README.md`, and `outputs/final.parquet` schema (do not include pipeline code).
