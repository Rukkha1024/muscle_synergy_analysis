# Project Requirements Brief

This brief is completed for the `batch-only CLI simplification` task in `replace_V3D`.

---

## Task Classification (AGENT)

- [ ] **Bug Fix** — Replace incorrect behavior with correct behavior. Do not modify surrounding code.
- [ ] **New Feature** — Add functionality that does not currently exist.
- [x] **Refactor** — Improve code structure without changing behavior.
- [x] **Config / Data Change** — Modify settings or data without changing logic.

Selected: **Refactor + Config/Data Change**

---

## One-Line Summary (AGENT)

Convert the repository to a batch-only execution model by removing single-trial entrypoints and related CLI flags, while preserving batch output behavior.

## Problem Statement (AGENT)

`main.py` currently mixes two execution models: batch export (default) and legacy single-trial routes controlled by removed flags. This increases cognitive load for new users and creates maintenance overhead for paths that are no longer operationally required. The user requested full simplification to a single batch path.

## Ambiguity & Assumptions (AGENT — Think Before Coding)

### Interpretations Considered

- Interpretation A: keep legacy scripts but hide from docs.
- Interpretation B: remove scripts and remove CLI flags from `main.py`.
- **Selected**: Interpretation B.

### Explicit Assumptions

1. Batch mode is the official and only supported runtime flow.
2. Legacy single-trial commands are not required for current operations.
3. Internal docs must be cleaned to avoid dead commands.

### Clarifying Questions (USER)

1. 범위: 4개 스크립트 + `main.py`/`README.md` 정리.
2. 호환 정책: legacy single-trial flags 제거 후 argparse 기본 에러 사용.
3. MOS 전용 보조 batch 엔트리포인트 제거.
4. 내부 문서(`.agents` 포함) 전면 정리.

---

## Success Criteria (USER)

1. `main.py`가 batch-only CLI로 동작한다.
2. 지정된 4개 스크립트가 제거된다.
3. `README/.agents/Archive`에서 제거 대상 실행 경로 참조가 남지 않는다.
4. batch output의 before/after MD5가 일치한다.
5. `.agents/issue.md` 문제 기록 + `$replace-v3d-troubleshooting` 해결 기록 + 한국어 3줄 커밋 완료.

## Verifiable Goals (AGENT — Goal-Driven Execution)

| Original Instruction | Transformed Verifiable Goal |
|---------------------|-----------------------------|
| "batch-only로 단순화" | `main.py --help`에서 legacy single-trial flags가 사라지고 배치 옵션만 남는다. |
| "4개 스크립트 정리" | 파일 4개가 저장소에서 삭제되고 호출 참조도 0건이다. |
| "동작 보존" | `main.py --overwrite --skip_unmatched --max_files 5`의 before/after CSV MD5가 동일하다. |
| "문서 정리" | `rg` 스캔에서 `README/.agents/Archive`의 제거 대상 키워드 매치가 0건이다. |

### Verification Commands

    $ conda run -n cuda python main.py --help
    Expected output: no removed single-trial flags

    $ conda run -n cuda python main.py <removed-single-trial-flag> data/all_data/does_not_matter.c3d
    Expected output: argparse unrecognized arguments

    $ rg -n -S -- "<removed-legacy-entrypoint-or-flag-patterns>" README.md .agents Archive
    Expected output: no matches

---

## Inputs

### Data Sources (USER)

- Format(s): C3D, XLSM
- Location: `data/all_data`, `data/perturb_inform.xlsm`
- Validation sample output: `output/qc/batch_only_before.csv`, `output/qc/batch_only_after.csv`

### External Dependencies (AGENT)

- Required libraries/tools: conda env `cuda`, polars, pandas
- Required services: 없음

## Outputs

### Primary Deliverables (USER)

- `main.py` batch-only CLI
- 4 script removals
- updated `README.md`
- cleaned internal docs under `.agents` and `Archive`

### Secondary Artifacts (AGENT)

- `output/qc/batch_only_before.csv`, `output/qc/batch_only_after.csv`
- `output/qc/batch_only_before.md5`, `output/qc/batch_only_after.md5`
- `output/qc/main_help_before.txt`, `output/qc/main_help_after.txt`

---

## Surgical Change Boundary (AGENT — Surgical Changes)

### Files / Modules to Touch

- `main.py`
- `README.md`
- `.agents/REQUIREMENTS_TEMPLATE.md`
- `.agents/execplans/batch_only_cli_simplification_execplan_ko.md`
- `.agents/execplans/batch_only_cli_simplification_execplan_en.md`
- `.agents/skills/v3d-com-xcom-bos-mos/SKILL.md`
- `.agents/execplans/ankle_z_method2_execplan.md`
- `Archive/JOINT_ANGLE_CONVENTIONS.md`
- `.agents/issue.md`
- `/home/alice/.agents/skills/replace-v3d-troubleshooting/SKILL.md`

### Files Explicitly NOT to Touch

- `src/replace_v3d/**` core computation logic
- `scripts/run_batch_all_timeseries_csv.py`
- `scripts/apply_post_filter_from_meta.py`

### Style Match Rules

- [x] Preserve existing Markdown style where possible.
- [x] Keep changes scoped to this policy migration.
- [x] Do not revert unrelated dirty files.

---

## Constraints

### Technical (AGENT)

- Python execution must use `conda run -n cuda python`.
- Batch behavior must remain unchanged.
- Keep CSV encoding behavior unchanged (`utf-8-sig` default).

### Operational (AGENT)

- Repo may be dirty; unrelated changes must remain untouched.
- Verification should finish with `--max_files 5` time budget.

## Scope

### In Scope (AGENT)

1. Remove single-trial entrypoints and `main.py` single-trial flags.
2. Keep one official batch flow.
3. Clean user/internal docs to remove dead commands.
4. Run before/after MD5 regression checks.

### Out of Scope (USER)

1. Reintroducing single-trial mode.
2. Modifying numerical algorithms.
3. New feature additions beyond CLI/doc simplification.

## Minimal Implementation Contract (AGENT — Simplicity First)

### Will Build

1. Batch-only CLI in `main.py`.
2. Remove legacy script files and dead references.
3. Validation artifacts + 기록/커밋 마감.

### Will NOT Build (by design)

- Backward-compatibility shims for removed flags.
- Alternative single-trial wrappers.

### No Speculative Code Checklist

- [x] No new helper abstractions for future guesswork.
- [x] No hidden compatibility pathways.
- [x] No algorithm-level refactor unrelated to CLI scope.

---

## Prior Art and References (USER)

- Existing entrypoint: `main.py`
- Batch engine: `scripts/run_batch_all_timeseries_csv.py`
- Project rules: `AGENTS.md`, `.agents/PLANS.md`

## User Expertise Level (AGENT)

- Domain expertise: high
- Coding proficiency: high
- Will user modify code after delivery? yes

## Open Questions (AGENT)

1. 없음 (핵심 정책 선택 완료)

---

## Requirements Confirmed

- [x] User confirmed batch-only scope and removal policy.
- [x] CLI compatibility policy locked to argparse default error.
- [x] Internal docs cleanup scope locked (`.agents` 포함).
- [x] Verifiable goals are explicit and command-based.
- [x] Agent may proceed with implementation.
