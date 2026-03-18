# Plan: CSV 제거, Parquet 저장 + Parquet 기반 Excel 재생성 체제로 전환

## Context
현재 파이프라인은 CSV/Parquet/Excel을 모두 생성하지만, CSV와 Excel은 내용이 중복되고, Excel 생성 로직이 pipeline export 흐름에 직접 결합되어 있음. CSV 생성 로직을 완전히 제거하고, Parquet를 모든 DataFrame의 단일 저장소(source of truth)로 사용하며, Excel은 사람이 결과를 확인하는 용도로만 Parquet를 읽어 재생성하는 체제로 전환. 즉, raw/derived table은 모두 parquet에 저장하고, `--from-parquet` 옵션으로 Excel workbook만 독립적으로 재생성 가능하게 함.

---

## 변경 1: `src/synergy_stats/artifacts.py` — 모든 DataFrame을 parquet 저장

### 1-1. 상수 추가
```python
PARQUET_FILENAME_MAP = {
    # AGGREGATE_NAME_MAP 대응
    "metadata":          "all_clustering_metadata.parquet",
    "labels":            "all_cluster_labels.parquet",
    "rep_W":             "all_representative_W_posthoc.parquet",
    "rep_H_long":        "all_representative_H_posthoc_long.parquet",
    "minimal_W":         "all_minimal_units_W.parquet",
    "minimal_H_long":    "all_minimal_units_H_long.parquet",
    "trial_windows":     "all_trial_window_metadata.parquet",
    # 추가 frames
    "final_summary":     "final_summary.parquet",
    "source_trial_windows":    "all_concatenated_source_trial_windows.parquet",
    "pooled_strategy_summary": "pooled_cluster_strategy_summary.parquet",
    "pooled_strategy_w_means": "pooled_cluster_strategy_W_means.parquet",
    "pooled_strategy_h_means": "pooled_cluster_strategy_H_means_long.parquet",
    # cross-group
    "cross_group_pairwise":  "cross_group_pairwise.parquet",
    "cross_group_matrix":    "cross_group_matrix.parquet",
    "cross_group_decision":  "cross_group_decision.parquet",
    "cross_group_summary":   "cross_group_summary.parquet",
    # audit tables
    "audit_selection_summary":        "audit_selection_summary.parquet",
    "audit_k_audit":                  "audit_k_audit.parquet",
    "audit_duplicate_trial_summary":  "audit_duplicate_trial_summary.parquet",
    "audit_duplicate_cluster_detail": "audit_duplicate_cluster_detail.parquet",
}
```

### 1-2. `_save_parquet()` 헬퍼 추가
```python
def _save_parquet(frame: pd.DataFrame, path: Path) -> None:
    if frame.empty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_parquet_frame(frame).to_parquet(path, index=False)
```

### 1-3. `_write_mode_exports()`를 parquet 중심 export로 전환
기존 CSV 생성 경로를 제거하고, mode 단위 산출 DataFrame을 모두 `<mode_dir>/parquet/`에 저장.

- `summary_df`, AGGREGATE_NAME_MAP 7개, source_trial_windows, pooled 3개, cross_group 4개
- audit tables: `build_audit_tables(cluster_group_results)` 호출 → 4개 DataFrame parquet 저장

### 1-4. `export_results()`에 root-level parquet 저장 추가
combined frames도 `<run_dir>/parquet/`에 동일하게 저장하여, mode별/통합 결과 모두 parquet만으로 복원 가능하게 함.

### 1-5. `export_from_parquet()` 공개 함수 추가
parquet에서 Excel workbook만 재생성하는 함수. Excel 생성 시 필요한 모든 입력은 parquet에서만 읽고, 별도 CSV나 in-memory export 결과에 의존하지 않음.

```python
def export_from_parquet(run_dir: Path) -> None:
    modes = _discover_parquet_modes(run_dir)
    for mode in modes:
        bundle = _load_parquet_bundle(run_dir / mode / "parquet")
        _write_workbooks_from_bundle(bundle, run_dir / mode)
    root_parquet = run_dir / "parquet"
    if root_parquet.exists():
        bundle = _load_parquet_bundle(root_parquet)
        _write_workbooks_from_bundle(bundle, run_dir)
```

내부 헬퍼:
- `_discover_parquet_modes(run_dir)`: `parquet/` 폴더가 있는 서브디렉토리 탐색
- `_load_parquet_bundle(parquet_dir)`: PARQUET_FILENAME_MAP 기반 읽기, 없는 파일은 빈 DataFrame
- `_write_workbooks_from_bundle(bundle, output_dir)`:
  - audit 4개 DataFrame → `write_clustering_audit_workbook_from_frames()` 호출
  - summary + aggregate + cross_group + **pooled strategy** → `write_results_interpretation_workbook()` 호출

핵심 원칙:
- parquet가 저장 포맷의 단일 기준이며, Excel은 parquet를 사람 친화적으로 보여주는 파생 산출물
- Excel 재생성 경로는 parquet만 읽어야 하며, CSV 재도입 없이 동일 workbook을 복원할 수 있어야 함

---

## 변경 2: `src/synergy_stats/excel_audit.py` — 리팩토링

`write_clustering_audit_workbook()` → `write_clustering_audit_workbook_from_frames(path, tables)` 추출.
기존 함수는 `build_audit_tables()` 호출 후 새 함수에 위임.

---

## 변경 3: `src/synergy_stats/excel_results.py` — pooled strategy 시트 추가

`RESULT_SHEET_CONFIGS`에 3개 시트 추가:

| source_key | sheet_name | 설명 |
|------------|-----------|------|
| `pooled_strategy_summary` | `pooled_strategy` | Pooled cluster별 step/nonstep 비율 |
| `pooled_strategy_w_means` | `pooled_strategy_W` | Pooled cluster별 strategy별 평균 W |
| `pooled_strategy_h_means` | `pooled_strategy_H` | Pooled cluster별 strategy별 평균 H |

모두 `optional=True`로 설정 (pooled group이 없는 경우 생략).

artifacts.py의 `_write_mode_exports()`와 `export_results()`에서 `write_results_interpretation_workbook()` 호출 시 pooled strategy frames도 dict에 포함하도록 수정. 이때 workbook 생성 입력은 in-memory 결과와 parquet 재로딩 양쪽에서 동일한 frame key 계약을 따르도록 맞춤.

---

## 변경 4: `scripts/emg/05_export_artifacts.py`에 CLI 옵션 추가

```
python scripts/emg/05_export_artifacts.py --from-parquet outputs/runs/<run_id>
```

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.synergy_stats import export_results
from src.synergy_stats.artifacts import export_from_parquet
from src.emg_pipeline.log_utils import log_kv_section


def run(context: dict) -> dict:
    # 기존 코드 유지


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Rebuild Excel workbooks from parquet files."
    )
    parser.add_argument("--from-parquet", required=True,
                        help="Run directory containing parquet/ subdirectories.")
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_dir = Path(args.from_parquet).resolve()
    export_from_parquet(run_dir)
```

---

## 파일 목록

| 파일 | 변경 유형 |
|------|----------|
| `src/synergy_stats/artifacts.py` | 수정 — PARQUET_FILENAME_MAP, _save_parquet, parquet 저장, export_from_parquet 추가 |
| `src/synergy_stats/excel_audit.py` | 수정 — write_clustering_audit_workbook_from_frames 추출 |
| `src/synergy_stats/excel_results.py` | 수정 — RESULT_SHEET_CONFIGS에 pooled strategy 3개 시트 추가 |
| `scripts/emg/05_export_artifacts.py` | 수정 — sys.path insert, __main__ 블록, --from-parquet CLI 추가 |

---

## 검증 방법

1. `python main.py` → `outputs/runs/<run>/parquet/` 디렉토리에 parquet 파일 생성 확인
2. `outputs/runs/<run>/` 내 xlsx 삭제 후 `python scripts/emg/05_export_artifacts.py --from-parquet outputs/runs/<run>` 실행
3. parquet만 남은 상태에서 audit/results workbook이 재생성되는지 확인
4. 재생성된 Excel workbook 내 시트/테이블 구조 검증 (기존 validate 함수)
5. pooled_strategy 시트 3개가 results_interpretation.xlsx에 포함되었는지 확인
