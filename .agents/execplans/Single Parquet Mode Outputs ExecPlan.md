# Single Parquet Mode Outputs ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows [.agents/PLANS.md](./PLANS.md) and is written so that a novice can understand what changed, why it changed, and how to validate the result.

## English Version

## Purpose / Big Picture

After this change, the EMG pipeline no longer scatters workbook and figure source data across many `parquet/*.parquet` files inside each run directory. The source of truth becomes three alias parquet files in `outputs/`: `final.parquet`, `final_trialwise.parquet`, and `final_concatenated.parquet`. Users inspect only the mode-specific Excel workbooks and figures under `outputs/runs/<run_id>/trialwise` and `outputs/runs/<run_id>/concatenated`. The easiest way to see the behavior is to run `python3 main.py --config configs/global_config.yaml --overwrite` and confirm that the run directory contains mode folders with workbooks and figures, while the run root contains no CSV files, no `parquet/` directory, and no root Excel workbooks.

## Progress

- [x] (2026-03-18 15:15Z) Confirmed that the old implementation wrote run-local parquet bundles and root Excel workbooks that conflicted with the requested output contract.
- [x] (2026-03-18 15:27Z) Added `src/synergy_stats/single_parquet.py` to serialize and restore all workbook and figure source frames through one `artifact_kind`-based parquet table.
- [x] (2026-03-18 15:39Z) Refactored `src/synergy_stats/artifacts.py` so mode exports write only alias parquet files and rebuild mode-specific Excel and figures from those files.
- [x] (2026-03-18 15:47Z) Refactored `src/synergy_stats/figure_rerender.py` and the `05` / `06` scripts to read single parquet aliases instead of `run_dir/parquet/*.parquet`.
- [x] (2026-03-18 15:55Z) Updated contract tests for the new file tree and verified `23 passed` across the focused test suite.
- [ ] Run `python3 main.py --config configs/global_config.yaml --overwrite` against the current repository data and record the observed output tree and any MD5 comparison findings.

## Surprises & Discoveries

- Observation: The existing `outputs/final*.parquet` files did not contain enough information to rebuild Excel and figures.
  Evidence: `outputs/final*.parquet` only held a `minimal_W`-shaped table, while figure regeneration required labels, representative H, trial windows, and optional cross-group frames.

- Observation: Figure rerendering could not simply “switch paths” from `run_dir/parquet` to `outputs/final*.parquet`; it needed a new serialization contract.
  Evidence: The old rerender module looked for files like `all_cluster_labels.parquet` and `all_representative_H_posthoc_long.parquet` under `run_dir/parquet`.

- Observation: Root workbooks were an implementation habit, not a user-facing requirement.
  Evidence: The code created them by merging mode summaries again at the run root, but the user only needed `trialwise` and `concatenated` Excel outputs.

## Decision Log

- Decision: Keep the parquet source of truth in `outputs/final.parquet`, `outputs/final_trialwise.parquet`, and `outputs/final_concatenated.parquet`.
  Rationale: The user explicitly rejected run-local parquet bundles and pointed to the existing alias locations as the desired source layout.
  Date/Author: 2026-03-18 / Codex

- Decision: Remove root Excel workbooks and keep only mode-specific Excel workbooks.
  Rationale: The user said the only necessary Excel outputs are the `trialwise` and `concatenated` versions.
  Date/Author: 2026-03-18 / Codex

- Decision: Encode all exportable workbook and figure source frames into one parquet table using `artifact_kind`.
  Rationale: Excel and figure regeneration must work from a single parquet file per scope, and the previous `minimal_W`-only schema was insufficient.
  Date/Author: 2026-03-18 / Codex

- Decision: Keep old-run backfill out of scope.
  Rationale: The user prioritized the new output contract and `main.py` validation over migration support for old runs.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

The repository now has a concrete implementation path for the requested output contract: three alias parquet sources in `outputs/`, mode-only workbooks and figures inside each run, and no CSV or run-local parquet bundle contract. Focused tests already prove the new structure in fixture-based scenarios. The remaining work is the full `main.py` validation on current data and the final output/MD5 evidence capture.

## Context and Orientation

The pipeline entrypoint is `main.py`. It runs five thin steps in order, and Step 5 calls `scripts/emg/05_export_artifacts.py`. That script delegates to `src/synergy_stats/artifacts.py`, which is the module that assembles exportable DataFrames, writes parquet outputs, writes Excel workbooks, and records artifact paths in the runtime context. Figure regeneration lives in `src/synergy_stats/figure_rerender.py`. The phrase “single parquet” means one parquet file per analysis scope, not a directory of many parquet files. In this repository, the three scopes are the combined run, the trialwise mode, and the concatenated mode.

## Plan of Work

The implementation replaces the old bundle-parquet contract with a single-table parquet contract. In `src/synergy_stats/single_parquet.py`, all workbook and figure source frames are serialized into one DataFrame with an `artifact_kind` column and written through one parquet file. `src/synergy_stats/artifacts.py` now builds those bundles for each mode, writes the alias parquet files in `outputs/`, and then regenerates the mode-specific workbooks and figures from those files. The root run directory no longer receives a workbook, a `parquet/` directory, or CSV files.

The rerender path is aligned with the same contract. `src/synergy_stats/figure_rerender.py` now loads the alias parquet bundle, restores the required frames, and builds figures in `trialwise/figures` or `concatenated/figures`. `scripts/emg/05_export_artifacts.py` and `scripts/emg/06_render_figures_only.py` use the configured alias parquet files instead of run-local bundle directories.

The tests were updated so they assert the new output tree rather than the removed bundle-parquet layout. `tests/test_synergy_stats/test_end_to_end_contract.py` now expects only alias parquet files in `outputs/`, mode-only workbooks, no root workbook, no run-local `parquet/` directories, and no CSV files. `tests/test_synergy_stats/test_figure_rerender.py` now exercises figure regeneration from single parquet source files.

## Concrete Steps

From the repository root:

    pytest -q tests/test_synergy_stats/test_artifacts.py tests/test_synergy_stats/test_excel_audit.py tests/test_synergy_stats/test_figure_rerender.py tests/test_synergy_stats/test_end_to_end_contract.py tests/test_synergy_stats/test_md5_compare_outputs.py

Expected result:

    23 passed in about 15 seconds

Then validate the real pipeline:

    python3 main.py --config configs/global_config.yaml --overwrite

Expected observations after a successful run:

    outputs/final.parquet exists
    outputs/final_trialwise.parquet exists
    outputs/final_concatenated.parquet exists
    outputs/runs/default_run/trialwise/clustering_audit.xlsx exists
    outputs/runs/default_run/trialwise/results_interpretation.xlsx exists
    outputs/runs/default_run/concatenated/clustering_audit.xlsx exists
    outputs/runs/default_run/concatenated/results_interpretation.xlsx exists
    outputs/runs/default_run/trialwise/figures exists
    outputs/runs/default_run/concatenated/figures exists
    outputs/runs/default_run/parquet does not exist
    outputs/runs/default_run has no CSV files
    outputs/runs/default_run has no root Excel workbook

## Validation and Acceptance

Acceptance is behavioral. A human should be able to run `main.py`, open the run directory, and see only mode-specific workbooks and figures, while all parquet source files live in `outputs/` as the three alias files. The focused pytest suite must pass. The final manual validation must confirm that `main.py` itself creates the expected tree without any helper reconstruction step.

## Idempotence and Recovery

The validation command uses `--overwrite`, so it intentionally removes the existing `outputs/runs/default_run` directory before regenerating outputs. That is safe for this task because the purpose is to validate the current contract from scratch. If the run fails midway, rerun the same command after fixing the issue; the command remains idempotent because it always recreates the run directory from a clean state.

## Artifacts and Notes

Focused test evidence:

    pytest -q tests/test_synergy_stats/test_artifacts.py tests/test_synergy_stats/test_excel_audit.py tests/test_synergy_stats/test_figure_rerender.py tests/test_synergy_stats/test_end_to_end_contract.py tests/test_synergy_stats/test_md5_compare_outputs.py
    .......................                                                  [100%]
    23 passed in 15.20s

## Interfaces and Dependencies

`src/synergy_stats/single_parquet.py` defines the single-parquet contract and must remain the only place that knows how artifact bundles are encoded into one parquet table. `src/synergy_stats/artifacts.py` is responsible for building export bundles, writing alias parquet files, and rebuilding mode-specific workbooks and figures from those files. `src/synergy_stats/figure_rerender.py` depends on the same contract and must never look for `run_dir/parquet/*.parquet` again.

Change note: This plan was added after the user clarified that “one parquet” meant alias parquet sources in `outputs/`, not run-local bundle parquet directories, and that only mode-specific Excel outputs are required.

## 한국어 버전

## Purpose / Big Picture

이 변경 후에는 EMG 파이프라인이 각 run 디렉토리 안에 `parquet/*.parquet` 파일을 여러 개 흩뿌리지 않는다. source of truth는 `outputs/final.parquet`, `outputs/final_trialwise.parquet`, `outputs/final_concatenated.parquet` 세 파일로 고정된다. 사용자는 `outputs/runs/<run_id>/trialwise`와 `outputs/runs/<run_id>/concatenated` 아래의 Excel과 figure만 확인하면 된다. 가장 쉬운 확인 방법은 `python3 main.py --config configs/global_config.yaml --overwrite`를 실행한 뒤, run 루트에는 CSV와 `parquet/` 디렉토리, root Excel이 없고, mode 하위에만 workbook과 figure가 생성되는지 보는 것이다.

## Progress

- [x] (2026-03-18 15:15Z) 기존 구현이 run-local parquet bundle과 root Excel workbook을 생성하고 있어 요구된 output contract와 충돌한다는 점을 확인했다.
- [x] (2026-03-18 15:27Z) `src/synergy_stats/single_parquet.py`를 추가해 workbook/figure source frame 전체를 `artifact_kind` 기반 단일 parquet 테이블로 직렬화하고 복원하도록 만들었다.
- [x] (2026-03-18 15:39Z) `src/synergy_stats/artifacts.py`를 리팩터링해 mode export가 alias parquet만 쓰고, 같은 파일에서 mode Excel과 figure를 다시 만들도록 바꿨다.
- [x] (2026-03-18 15:47Z) `src/synergy_stats/figure_rerender.py`와 `05`, `06` 스크립트를 single parquet alias를 읽도록 바꿨다.
- [x] (2026-03-18 15:55Z) 새 file tree에 맞게 계약 테스트를 바꾸고, 집중 테스트 셋에서 `23 passed`를 확인했다.
- [ ] 현재 저장소 데이터에 대해 `python3 main.py --config configs/global_config.yaml --overwrite`를 실행하고, 실제 output tree와 MD5 비교 결과를 기록한다.

## Surprises & Discoveries

- Observation: 기존 `outputs/final*.parquet`는 Excel과 figure를 다시 만들기에 필요한 정보가 부족했다.
  Evidence: `outputs/final*.parquet`는 사실상 `minimal_W` 형태 데이터만 담고 있었고, figure 재생성에는 labels, representative H, trial windows, optional cross-group frame까지 필요했다.

- Observation: figure rerender는 단순히 경로만 `run_dir/parquet`에서 `outputs/final*.parquet`로 바꾸는 수준으로는 해결되지 않았다.
  Evidence: 기존 rerender 모듈은 `run_dir/parquet` 아래의 `all_cluster_labels.parquet`, `all_representative_H_posthoc_long.parquet` 같은 개별 파일 이름을 전제로 하고 있었다.

- Observation: root workbook은 사용자 요구가 아니라 기존 구현 습관에 가까웠다.
  Evidence: 코드는 mode summary를 한 번 더 합쳐 root workbook을 만들고 있었지만, 사용자는 `trialwise`, `concatenated` Excel만 필요하다고 명시했다.

## Decision Log

- Decision: parquet source of truth는 `outputs/final.parquet`, `outputs/final_trialwise.parquet`, `outputs/final_concatenated.parquet`로 고정한다.
  Rationale: 사용자가 run-local parquet bundle을 원하지 않았고, 기존 alias 위치를 원하는 구조로 직접 지목했다.
  Date/Author: 2026-03-18 / Codex

- Decision: root Excel workbook은 제거하고 mode별 Excel workbook만 유지한다.
  Rationale: 사용자가 필요한 Excel은 `trialwise`와 `concatenated` 버전뿐이라고 명확히 말했다.
  Date/Author: 2026-03-18 / Codex

- Decision: workbook과 figure source frame 전체를 `artifact_kind` 컬럼을 가진 단일 parquet 테이블에 담는다.
  Rationale: scope별 parquet를 한 파일로 줄이면서도 Excel과 figure를 다시 만들 수 있으려면, 기존 `minimal_W` 전용 schema로는 부족했다.
  Date/Author: 2026-03-18 / Codex

- Decision: 오래된 run 구조를 변환하는 backfill은 이번 범위에서 제외한다.
  Rationale: 사용자는 old run migration보다 새 output contract와 `main.py` 검증을 우선했다.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

저장소는 이제 사용자가 요구한 output contract를 구현할 수 있는 구체적인 경로를 갖게 됐다. source parquet는 `outputs/` 아래 3개 alias로 정리되고, run 안에는 mode별 workbook과 figure만 남는다. fixture 기반 집중 테스트는 이미 이 구조를 통과했다. 남은 일은 현재 데이터로 `main.py`를 실제 실행해 최종 output tree와 MD5 증거를 남기는 것이다.

## Context and Orientation

파이프라인 entrypoint는 `main.py`다. 이 파일은 1~5단계의 얇은 스크립트를 순서대로 실행하고, 5단계에서 `scripts/emg/05_export_artifacts.py`를 호출한다. 이 스크립트는 `src/synergy_stats/artifacts.py`에 위임하며, 이 모듈이 export용 DataFrame 조립, parquet 출력, Excel 작성, artifact path 기록을 담당한다. figure 재생성은 `src/synergy_stats/figure_rerender.py`에 있다. 여기서 “single parquet”는 parquet 파일이 한 개뿐인 디렉토리를 뜻하지 않고, scope별 source DataFrame 묶음을 한 parquet 파일 안에 담는 계약을 뜻한다. 이 저장소에서 scope는 combined run, trialwise mode, concatenated mode 세 가지다.

## Plan of Work

구현은 old bundle-parquet 계약을 single-table parquet 계약으로 바꾸는 방식이다. `src/synergy_stats/single_parquet.py`에서 모든 workbook/figure source frame을 `artifact_kind` 컬럼을 가진 하나의 DataFrame으로 직렬화하고, 같은 형식으로 복원한다. `src/synergy_stats/artifacts.py`는 mode별 bundle을 만들고, `outputs/`의 alias parquet를 쓴 뒤, 그 파일에서 다시 mode workbook과 figure를 생성한다. root run 디렉토리에는 더 이상 workbook, `parquet/` 디렉토리, CSV가 생기지 않는다.

rerender 경로도 같은 계약을 사용한다. `src/synergy_stats/figure_rerender.py`는 alias parquet bundle을 읽고 필요한 frame을 복원해 `trialwise/figures` 또는 `concatenated/figures`에 그림을 만든다. `scripts/emg/05_export_artifacts.py`와 `scripts/emg/06_render_figures_only.py`도 run-local bundle 디렉토리가 아니라 configured alias parquet를 사용한다.

테스트는 제거된 bundle-parquet 레이아웃이 아니라 새 output tree를 검증하도록 바꿨다. `tests/test_synergy_stats/test_end_to_end_contract.py`는 이제 `outputs/` 아래 alias parquet만 기대하고, mode별 workbook만 기대하며, root workbook과 run-local `parquet/` 디렉토리, CSV가 없음을 확인한다. `tests/test_synergy_stats/test_figure_rerender.py`는 single parquet source에서 figure를 다시 그리는 경로를 직접 검증한다.

## Concrete Steps

저장소 루트에서 실행한다.

    pytest -q tests/test_synergy_stats/test_artifacts.py tests/test_synergy_stats/test_excel_audit.py tests/test_synergy_stats/test_figure_rerender.py tests/test_synergy_stats/test_end_to_end_contract.py tests/test_synergy_stats/test_md5_compare_outputs.py

기대 결과:

    23 passed 전후

그다음 실제 파이프라인을 검증한다.

    python3 main.py --config configs/global_config.yaml --overwrite

성공 시 기대 관찰:

    outputs/final.parquet 존재
    outputs/final_trialwise.parquet 존재
    outputs/final_concatenated.parquet 존재
    outputs/runs/default_run/trialwise/clustering_audit.xlsx 존재
    outputs/runs/default_run/trialwise/results_interpretation.xlsx 존재
    outputs/runs/default_run/concatenated/clustering_audit.xlsx 존재
    outputs/runs/default_run/concatenated/results_interpretation.xlsx 존재
    outputs/runs/default_run/trialwise/figures 존재
    outputs/runs/default_run/concatenated/figures 존재
    outputs/runs/default_run/parquet 없음
    outputs/runs/default_run 아래 CSV 없음
    outputs/runs/default_run root Excel 없음

## Validation and Acceptance

수용 기준은 행동으로 확인 가능해야 한다. 사람이 `main.py`를 실행하고 run 디렉토리를 열었을 때, source parquet는 `outputs/` 아래 3개 alias 파일뿐이고, 사용자가 보는 결과물은 mode별 workbook과 figure뿐이어야 한다. 집중 pytest 세트는 통과해야 한다. 마지막 manual validation은 helper 재생성 없이 `main.py` 자체가 이 구조를 만들어내는지를 보여줘야 한다.

## Idempotence and Recovery

검증 명령은 `--overwrite`를 사용하므로 기존 `outputs/runs/default_run` 디렉토리를 지우고 다시 만든다. 이번 작업의 목적이 scratch부터 새 contract를 검증하는 것이므로 이 동작은 안전하다. 중간에 실패하면 수정 후 같은 명령을 다시 실행하면 된다. 항상 clean run 디렉토리에서 다시 시작하므로 명령은 반복 가능하다.

## Artifacts and Notes

집중 테스트 증거:

    pytest -q tests/test_synergy_stats/test_artifacts.py tests/test_synergy_stats/test_excel_audit.py tests/test_synergy_stats/test_figure_rerender.py tests/test_synergy_stats/test_end_to_end_contract.py tests/test_synergy_stats/test_md5_compare_outputs.py
    .......................                                                  [100%]
    23 passed in 15.20s

## Interfaces and Dependencies

`src/synergy_stats/single_parquet.py`는 single-parquet contract를 정의하는 유일한 장소여야 한다. `src/synergy_stats/artifacts.py`는 export bundle 작성, alias parquet 쓰기, 같은 파일에서 mode workbook과 figure 다시 만들기를 담당한다. `src/synergy_stats/figure_rerender.py`는 같은 contract에 의존하며, 다시는 `run_dir/parquet/*.parquet`를 찾으면 안 된다.

Change note: 이 계획 문서는 사용자가 “하나의 parquet”가 run-local bundle parquet 디렉토리가 아니라 `outputs/` 아래 alias parquet source를 뜻한다고 명확히 했고, root Excel은 필요 없다고 정리한 뒤 추가되었다.
