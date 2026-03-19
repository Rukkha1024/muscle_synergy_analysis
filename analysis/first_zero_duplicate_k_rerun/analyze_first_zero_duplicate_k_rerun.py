"""Rerun pooled K selection without gap statistic.

Loads one final parquet bundle, rebuilds pooled W vectors,
scans K upward with the production duplicate rule,
and reports the first zero-duplicate solution in `analysis/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

try:
    matplotlib.use("Agg", force=True)
except Exception:
    pass
from matplotlib import pyplot as plt
import numpy as np
import polars as pl

from src.emg_pipeline.config import load_pipeline_config
from src.synergy_stats.artifacts import export_results
from src.synergy_stats.artifacts import _write_mode_figures_from_source
from src.synergy_stats.clustering import (
    SubjectFeatureResult,
    _search_zero_duplicate_candidate_at_k,
    _stack_weight_vectors,
    _subject_hmax,
)
from src.synergy_stats.single_parquet import load_single_parquet_bundle, write_single_parquet_bundle


DEFAULT_SOURCE_PARQUET = REPO_ROOT / "outputs" / "final_concatenated.parquet"
DEFAULT_CONFIG = REPO_ROOT / "configs" / "global_config.yaml"
DEFAULT_OUT_DIR = SCRIPT_DIR / "artifacts" / "default_run"
DEFAULT_GROUP_ID = "pooled_step_nonstep"
DEFAULT_FIGURE_FORMAT = "png"
DEFAULT_FIGURE_DPI = 150


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for dry-run and full reruns."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-parquet",
        type=Path,
        default=DEFAULT_SOURCE_PARQUET,
        help="Single final parquet bundle written by the main pipeline.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Global pipeline config used to mirror workbook/figure export settings.",
    )
    parser.add_argument(
        "--group-id",
        default=DEFAULT_GROUP_ID,
        help="Cluster group to reconstruct from the bundle.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Analysis artifact directory.",
    )
    parser.add_argument(
        "--algorithm",
        default=None,
        help="Override clustering backend. Defaults to the source bundle metadata.",
    )
    parser.add_argument(
        "--max-clusters",
        type=int,
        default=None,
        help="Upper K bound for the no-gap scan. Defaults to the source bundle metadata range.",
    )
    parser.add_argument(
        "--uniqueness-candidate-restarts",
        type=int,
        default=None,
        help="Override the number of searched candidates per K.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=None,
        help="Override the maximum iterations per k-means fit.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=None,
        help="Override the clustering random seed.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing analysis artifact directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load the bundle and print the planned K scan without writing artifacts.",
    )
    return parser.parse_args()


def _print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def _ensure_clean_dir(path: Path, *, overwrite: bool) -> None:
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"Output directory exists: {path} (use --overwrite)")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_builtin(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [_to_builtin(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        scalar = float(value)
        return scalar if math.isfinite(scalar) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig") as handle:
        json.dump(_to_builtin(payload), handle, ensure_ascii=False, indent=2)


def _file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksums(paths: list[Path], output_path: Path) -> None:
    lines = [f"{_file_md5(path)}  {path.resolve()}" for path in sorted(paths)]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _path_relative_to(base_dir: Path, raw_path: str) -> str:
    path = Path(raw_path)
    try:
        return str(path.resolve().relative_to(base_dir.resolve()))
    except Exception:
        return str(path)


def _scalar_to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        if value != value:
            return default
    except Exception:
        pass
    try:
        return int(float(value))
    except Exception:
        return default


def _scalar_to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if value != value:
            return default
    except Exception:
        pass
    return str(value)


def _same_scalar_expression(column_name: str, value: Any) -> Any:
    if isinstance(value, str):
        return pl.col(column_name).cast(pl.Utf8) == value
    try:
        if value != value:
            return pl.col(column_name).is_null()
    except Exception:
        pass
    if isinstance(value, (int, float, np.integer, np.floating)):
        return pl.col(column_name).cast(pl.Float64) == float(value)
    return pl.col(column_name).cast(pl.Utf8) == str(value)


def _load_source_bundle(source_parquet: Path) -> dict[str, Any]:
    if not source_parquet.exists():
        raise FileNotFoundError(f"Source parquet does not exist: {source_parquet}")
    bundle = load_single_parquet_bundle(source_parquet)
    required_frames = ("minimal_W", "minimal_H_long", "metadata", "final_summary")
    missing_frames = [frame_key for frame_key in required_frames if bundle.get(frame_key) is None or bundle[frame_key].empty]
    if missing_frames:
        raise ValueError(f"Source parquet is missing required frames: {missing_frames}")
    return bundle


def _group_metadata_row(bundle: dict[str, Any], group_id: str) -> dict[str, Any]:
    metadata_pl = pl.from_pandas(bundle["metadata"])
    filtered = metadata_pl.filter(pl.col("group_id").cast(pl.Utf8) == group_id)
    if filtered.is_empty():
        raise ValueError(f"Group `{group_id}` was not found in bundle metadata.")
    return filtered.to_dicts()[0]


def _parse_metric_json(raw_value: Any) -> dict[str, Any]:
    text = _scalar_to_str(raw_value)
    if not text:
        return {}
    return json.loads(text)


def _muscle_order(minimal_w_pl: pl.DataFrame) -> list[str]:
    return (
        minimal_w_pl
        .select("muscle")
        .unique(maintain_order=True)
        .get_column("muscle")
        .cast(pl.Utf8)
        .to_list()
    )


def _mode_from_bundle(bundle: dict[str, Any], group_id: str) -> str:
    summary_pl = pl.from_pandas(bundle["final_summary"])
    filtered = summary_pl.filter(pl.col("group_id").cast(pl.Utf8) == group_id)
    if filtered.is_empty():
        raise ValueError(f"Group `{group_id}` was not found in the final_summary frame.")
    mode = filtered.get_column("aggregation_mode").cast(pl.Utf8).to_list()[0]
    return str(mode).strip().lower() or "concatenated"


def _rebuild_feature_rows(
    minimal_w_frame: Any,
    minimal_h_frame: Any,
    group_id: str,
) -> tuple[list[SubjectFeatureResult], list[str]]:
    minimal_w_pl = pl.from_pandas(minimal_w_frame).filter(pl.col("group_id").cast(pl.Utf8) == group_id)
    minimal_h_pl = pl.from_pandas(minimal_h_frame).filter(pl.col("group_id").cast(pl.Utf8) == group_id)
    if minimal_w_pl.is_empty():
        raise ValueError(f"Group `{group_id}` was not found in the minimal_W frame.")
    if minimal_h_pl.is_empty():
        raise ValueError(f"Group `{group_id}` was not found in the minimal_H_long frame.")

    muscle_names = _muscle_order(minimal_w_pl)
    key_columns = [
        "subject",
        "velocity",
        "trial_num",
        "trial_id",
        "analysis_unit_id",
    ]
    trial_rows = minimal_w_pl.select(key_columns).unique(maintain_order=True)
    feature_rows: list[SubjectFeatureResult] = []
    for trial_key in trial_rows.iter_rows(named=True):
        analysis_unit_id = trial_key.get("analysis_unit_id")
        if analysis_unit_id not in (None, ""):
            trial_pl = minimal_w_pl.filter(
                pl.col("analysis_unit_id").cast(pl.Utf8) == str(analysis_unit_id)
            )
            trial_h_pl = minimal_h_pl.filter(
                pl.col("analysis_unit_id").cast(pl.Utf8) == str(analysis_unit_id)
            )
        else:
            trial_pl = minimal_w_pl.filter(
                _same_scalar_expression("subject", trial_key["subject"])
                & _same_scalar_expression("velocity", trial_key["velocity"])
                & _same_scalar_expression("trial_num", trial_key["trial_num"])
            )
            trial_h_pl = minimal_h_pl.filter(
                _same_scalar_expression("subject", trial_key["subject"])
                & _same_scalar_expression("velocity", trial_key["velocity"])
                & _same_scalar_expression("trial_num", trial_key["trial_num"])
            )
        trial_pdf = trial_pl.to_pandas()
        trial_h_pdf = trial_h_pl.to_pandas()
        component_ids = sorted({int(float(value)) for value in trial_pdf["component_index"].tolist()})
        pivot = trial_pdf.pivot(index="muscle", columns="component_index", values="W_value")
        pivot = pivot.reindex(index=muscle_names, columns=component_ids)
        if pivot.isnull().values.any():
            raise ValueError(f"Null W values found while reconstructing trial `{trial_key['trial_id']}`.")
        h_pivot = trial_h_pdf.pivot(index="frame_idx", columns="component_index", values="h_value")
        h_pivot = h_pivot.sort_index().reindex(columns=component_ids)
        if h_pivot.isnull().values.any():
            raise ValueError(f"Null H values found while reconstructing trial `{trial_key['trial_id']}`.")
        meta = {
            column_name: trial_pdf.iloc[0][column_name]
            for column_name in trial_pdf.columns
            if column_name not in {"muscle", "W_value"}
        }
        feature_rows.append(
            SubjectFeatureResult(
                subject=str(trial_key["subject"]),
                velocity=trial_key["velocity"],
                trial_num=trial_key["trial_num"],
                bundle=SimpleNamespace(
                    W_muscle=pivot.to_numpy(dtype=np.float32),
                    H_time=h_pivot.to_numpy(dtype=np.float32),
                    meta=meta,
                ),
            )
        )
    return feature_rows, muscle_names


def _build_scan_cfg(metadata_row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    algorithm_used = _scalar_to_str(metadata_row.get("algorithm_used"), "sklearn_kmeans").strip().lower()
    cfg = {
        "algorithm": args.algorithm or algorithm_used or "sklearn_kmeans",
        "torch_device": _scalar_to_str(metadata_row.get("torch_device"), "auto") or "auto",
        "torch_dtype": _scalar_to_str(metadata_row.get("torch_dtype"), "float32") or "float32",
        "uniqueness_candidate_restarts": args.uniqueness_candidate_restarts
        or _scalar_to_int(metadata_row.get("uniqueness_candidate_restarts"), 100)
        or 100,
        "max_iter": args.max_iter or _scalar_to_int(metadata_row.get("max_iter"), 300) or 300,
        "random_state": args.random_state or _scalar_to_int(metadata_row.get("random_state"), 42) or 42,
        "torch_restart_batch_size": 128,
    }
    return cfg


def _default_k_max(metadata_row: dict[str, Any], vector_count: int) -> int:
    duplicate_counts = _parse_metric_json(metadata_row.get("duplicate_trial_count_by_k_json"))
    candidate_keys = [int(key) for key in duplicate_counts]
    fallback_candidates = [
        _scalar_to_int(metadata_row.get("k_selected")),
        _scalar_to_int(metadata_row.get("k_gap_raw")),
        _scalar_to_int(metadata_row.get("k_min_unique")),
        max(candidate_keys) if candidate_keys else None,
    ]
    resolved = max(value for value in fallback_candidates if value is not None)
    return min(int(resolved), int(vector_count))


def scan_first_zero_duplicate_k(
    feature_rows: list[SubjectFeatureResult],
    *,
    group_id: str,
    cfg: dict[str, Any],
    k_max: int,
) -> dict[str, Any]:
    data, sample_map = _stack_weight_vectors(feature_rows, group_id)
    if data.size == 0:
        raise ValueError("No pooled vectors were reconstructed from the source bundle.")
    k_min = max(2, _subject_hmax(feature_rows))
    resolved_k_max = min(int(k_max), int(data.shape[0]))
    if resolved_k_max < k_min:
        raise ValueError(f"Invalid K range: k_min={k_min}, k_max={resolved_k_max}")

    scan_rows: list[dict[str, Any]] = []
    selected_row: dict[str, Any] | None = None
    selected_candidate: dict[str, Any] | None = None
    selected_sample_map: list[dict[str, Any]] | None = None
    for n_clusters in range(k_min, resolved_k_max + 1):
        candidate = _search_zero_duplicate_candidate_at_k(
            data,
            sample_map,
            n_clusters,
            cfg,
            observed_result=None,
        )
        zero_duplicate = candidate["best_zero_duplicate_result"] is not None
        row = {
            "k": int(n_clusters),
            "duplicate_trial_count": int(candidate["min_duplicate_trial_count"]),
            "searched_restarts": int(candidate["searched_restarts"]),
            "zero_duplicate_found": bool(zero_duplicate),
            "objective": (
                float(candidate["feasible_objective"])
                if zero_duplicate and candidate["feasible_objective"] == candidate["feasible_objective"]
                else None
            ),
            "representative_duplicate_trials": [
                [str(subject), _to_builtin(velocity), _to_builtin(trial_num)]
                for subject, velocity, trial_num in candidate.get("representative_duplicate_trials", [])
            ],
            "representative_duplicate_evidence": candidate.get("representative_duplicate_evidence", []),
        }
        scan_rows.append(row)
        if zero_duplicate and selected_row is None:
            selected_row = row
            selected_candidate = candidate["best_zero_duplicate_result"]
            selected_sample_map = sample_map
            break

    return {
        "group_id": group_id,
        "vector_count": int(data.shape[0]),
        "trial_count": int(len(feature_rows)),
        "k_min": int(k_min),
        "k_max": int(resolved_k_max),
        "selected_k": int(selected_row["k"]) if selected_row is not None else None,
        "selected_row": selected_row,
        "selected_candidate": selected_candidate,
        "sample_map": selected_sample_map,
        "scan_rows": scan_rows,
    }


def _combine_duplicate_counts(
    pipeline_duplicate_counts: dict[str, Any],
    scan_rows: list[dict[str, Any]],
) -> dict[int, int]:
    merged = {int(key): int(value) for key, value in pipeline_duplicate_counts.items()}
    for row in scan_rows:
        merged[int(row["k"])] = int(row["duplicate_trial_count"])
    return dict(sorted(merged.items()))


def _cluster_result_from_scan(
    *,
    metadata_row: dict[str, Any],
    scan_result: dict[str, Any],
    pipeline_duplicate_counts: dict[str, Any],
) -> dict[str, Any]:
    selected_candidate = scan_result.get("selected_candidate")
    if selected_candidate is None or scan_result.get("selected_k") is None:
        raise ValueError("No zero-duplicate candidate was selected for export.")
    duplicate_count_by_k = _combine_duplicate_counts(pipeline_duplicate_counts, scan_result["scan_rows"])
    feasible_objective_by_k = {
        int(row["k"]): (float(row["objective"]) if row.get("objective") is not None else np.nan)
        for row in scan_result["scan_rows"]
    }
    return {
        "status": "success",
        "group_id": scan_result["group_id"],
        "n_trials": scan_result["trial_count"],
        "n_components": scan_result["vector_count"],
        "n_clusters": int(scan_result["selected_k"]),
        "labels": np.asarray(selected_candidate["labels"], dtype=np.int32),
        "inertia": float(selected_candidate["objective"]),
        "duplicate_trials": [],
        "algorithm_used": selected_candidate.get("algorithm_used", ""),
        "torch_device": selected_candidate.get("torch_device", ""),
        "torch_dtype": selected_candidate.get("torch_dtype", ""),
        "sample_map": list(scan_result["sample_map"] or []),
        "selection_method": "first_zero_duplicate",
        "selection_status": "success_first_zero_duplicate",
        "duplicate_resolution": _scalar_to_str(metadata_row.get("duplicate_resolution"), "none") or "none",
        "require_zero_duplicate_solution": True,
        "k_lb": int(scan_result["k_min"]),
        "k_gap_raw": _scalar_to_int(metadata_row.get("k_gap_raw"), scan_result["selected_k"]),
        "k_selected": int(scan_result["selected_k"]),
        "k_min_unique": int(scan_result["selected_k"]),
        "gap_ref_n": _scalar_to_int(metadata_row.get("gap_ref_n"), 0) or 0,
        "gap_ref_restarts": _scalar_to_int(metadata_row.get("gap_ref_restarts"), 0) or 0,
        "repeats": _scalar_to_int(metadata_row.get("repeats"), 0) or 0,
        "uniqueness_candidate_restarts": _scalar_to_int(metadata_row.get("uniqueness_candidate_restarts"), 0) or 0,
        "gap_by_k": _parse_metric_json(metadata_row.get("gap_by_k_json")),
        "gap_sd_by_k": _parse_metric_json(metadata_row.get("gap_sd_by_k_json")),
        "observed_objective_by_k": _parse_metric_json(metadata_row.get("observed_objective_by_k_json")),
        "feasible_objective_by_k": feasible_objective_by_k,
        "duplicate_trial_count_by_k": duplicate_count_by_k,
        "duplicate_trial_evidence_by_k": {
            int(row["k"]): row.get("representative_duplicate_evidence", [])
            for row in scan_result["scan_rows"]
        },
    }


def _export_cfg(
    *,
    base_cfg_path: Path,
    out_dir: Path,
    mode: str,
    muscle_names: list[str],
) -> dict[str, Any]:
    cfg = deepcopy(load_pipeline_config(base_cfg_path))
    cfg.setdefault("muscles", {})["names"] = list(muscle_names)
    cfg.setdefault("synergy_analysis", {})["mode"] = mode
    cfg.setdefault("figures", {}).setdefault("format", DEFAULT_FIGURE_FORMAT)
    cfg.setdefault("figures", {}).setdefault("dpi", DEFAULT_FIGURE_DPI)
    runtime_cfg = cfg.setdefault("runtime", {})
    runtime_cfg["output_dir"] = str(out_dir)
    runtime_cfg["run_id"] = out_dir.name
    runtime_cfg["manifest_path"] = str(out_dir / "run_manifest.json")
    runtime_cfg["log_path"] = str(out_dir / "logs" / "run.log")
    runtime_cfg["analysis_methods_manifest_path"] = str(out_dir / "analysis_methods_manifest.json")
    runtime_cfg["final_parquet_path"] = str(out_dir / "final.parquet")
    runtime_cfg["combined_final_parquet_path"] = str(out_dir / "final.parquet")
    runtime_cfg["final_parquet_alias_paths"] = {
        mode: str(out_dir / f"final_{mode}.parquet"),
    }
    return cfg


def _export_pipeline_like_outputs(
    *,
    out_dir: Path,
    mode: str,
    cfg: dict[str, Any],
    feature_rows: list[SubjectFeatureResult],
    cluster_result: dict[str, Any],
    group_id: str,
) -> dict[str, Any]:
    context = {
        "config": cfg,
        "analysis_modes": [mode],
        "analysis_mode_feature_rows": {mode: feature_rows},
        "analysis_mode_cluster_group_results": {
            mode: {
                group_id: {
                    "group_id": group_id,
                    "aggregation_mode": mode,
                    "feature_rows": feature_rows,
                    "cluster_result": cluster_result,
                }
            }
        },
        "cluster_group_results": {
            group_id: {
                "group_id": group_id,
                "aggregation_mode": mode,
                "feature_rows": feature_rows,
                "cluster_result": cluster_result,
            }
        },
        "artifacts": {"steps": []},
    }
    return export_results(context)


def _inject_source_trial_windows_and_rerender(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    cfg: dict[str, Any],
    mode: str,
) -> None:
    source_trial_windows = bundle.get("source_trial_windows")
    if source_trial_windows is None or source_trial_windows.empty:
        return
    parquet_targets = [out_dir / "final.parquet"]
    alias_path = out_dir / f"final_{mode}.parquet"
    if alias_path.exists():
        parquet_targets.append(alias_path)
    for parquet_path in parquet_targets:
        rewritten = load_single_parquet_bundle(parquet_path)
        rewritten["source_trial_windows"] = source_trial_windows.copy()
        write_single_parquet_bundle(rewritten, parquet_path)
    _write_mode_figures_from_source(
        mode_output_dir=out_dir / mode,
        cfg=cfg,
        mode=mode,
        source_path=alias_path if alias_path.exists() else out_dir / "final.parquet",
    )


def _normalize_analysis_methods_manifest(out_dir: Path) -> None:
    manifest_path = out_dir / "analysis_methods_manifest.json"
    if not manifest_path.exists():
        return
    with manifest_path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if isinstance(payload.get("combined_final_parquet_path"), str):
        payload["combined_final_parquet_path"] = _path_relative_to(out_dir, payload["combined_final_parquet_path"])
    if isinstance(payload.get("final_parquet_path"), str):
        payload["final_parquet_path"] = _path_relative_to(out_dir, payload["final_parquet_path"])
    alias_paths = payload.get("final_parquet_alias_paths")
    if isinstance(alias_paths, dict):
        payload["final_parquet_alias_paths"] = {
            str(key): _path_relative_to(out_dir, str(value))
            for key, value in alias_paths.items()
        }
    modes = payload.get("modes")
    if isinstance(modes, dict):
        normalized_modes: dict[str, Any] = {}
        for mode_name, mode_payload in modes.items():
            if not isinstance(mode_payload, dict):
                normalized_modes[str(mode_name)] = mode_payload
                continue
            normalized_mode = dict(mode_payload)
            for field_name in (
                "output_dir",
                "final_alias_path",
                "clustering_audit_workbook_path",
                "results_interpretation_workbook_path",
            ):
                raw_value = normalized_mode.get(field_name)
                if isinstance(raw_value, str):
                    normalized_mode[field_name] = _path_relative_to(out_dir, raw_value)
            normalized_modes[str(mode_name)] = normalized_mode
        payload["modes"] = normalized_modes
    _write_json(manifest_path, payload)


def _plot_duplicate_burden(
    scan_rows: list[dict[str, Any]],
    pipeline_duplicate_counts: dict[str, Any],
    pipeline_k_gap_raw: int | None,
    pipeline_k_selected: int | None,
    rerun_selected_k: int | None,
    output_path: Path,
) -> Path:
    rerun_k = [int(row["k"]) for row in scan_rows]
    rerun_duplicates = [int(row["duplicate_trial_count"]) for row in scan_rows]
    pipeline_items = sorted((int(key), int(value)) for key, value in pipeline_duplicate_counts.items())

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.plot(rerun_k, rerun_duplicates, marker="o", linewidth=2.2, color="#1f77b4", label="analysis rerun")
    if pipeline_items:
        ax.plot(
            [item[0] for item in pipeline_items],
            [item[1] for item in pipeline_items],
            marker="s",
            linewidth=1.6,
            linestyle="--",
            color="#ff7f0e",
            label="pipeline metadata",
        )
    if pipeline_k_gap_raw is not None:
        ax.axvline(pipeline_k_gap_raw, color="#c0392b", linestyle=":", linewidth=1.2, label="pipeline k_gap_raw")
    if pipeline_k_selected is not None:
        ax.axvline(pipeline_k_selected, color="#7f8c8d", linestyle="-.", linewidth=1.2, label="pipeline k_selected")
    if rerun_selected_k is not None:
        ax.axvline(rerun_selected_k, color="#16a085", linestyle="-", linewidth=1.4, label="rerun first zero-duplicate")
    ax.set_title("Duplicate trial burden by K")
    ax.set_xlabel("K")
    ax.set_ylabel("Duplicate trials")
    ax.set_xticks(sorted(set(rerun_k + [item[0] for item in pipeline_items])))
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.25, axis="y")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def main() -> None:
    args = parse_args()

    print("=" * 72)
    print("First Zero-Duplicate K Rerun")
    print("=" * 72)
    print(f"Date: 2026-03-19")
    print(f"Source parquet: {args.source_parquet}")
    print(f"Group: {args.group_id}")
    print(f"Export config: {args.config}")

    _print_section("[M1] Load Source Bundle")
    bundle = _load_source_bundle(args.source_parquet)
    available_frames = sorted(frame_key for frame_key, frame in bundle.items() if frame is not None and not frame.empty)
    print("Restored frames:", ", ".join(available_frames))
    mode = _mode_from_bundle(bundle, args.group_id)
    print(f"Resolved mode: {mode}")

    metadata_row = _group_metadata_row(bundle, args.group_id)
    pipeline_duplicate_counts = _parse_metric_json(metadata_row.get("duplicate_trial_count_by_k_json"))
    pipeline_k_gap_raw = _scalar_to_int(metadata_row.get("k_gap_raw"))
    pipeline_k_selected = _scalar_to_int(metadata_row.get("k_selected"))
    pipeline_k_min_unique = _scalar_to_int(metadata_row.get("k_min_unique"))
    print(
        "Pipeline metadata:",
        f"k_gap_raw={pipeline_k_gap_raw},",
        f"k_selected={pipeline_k_selected},",
        f"k_min_unique={pipeline_k_min_unique}",
    )

    _print_section("[M2] Rebuild Pooled Feature Rows")
    feature_rows, muscle_names = _rebuild_feature_rows(bundle["minimal_W"], bundle["minimal_H_long"], args.group_id)
    print(f"Trials reconstructed: {len(feature_rows)}")
    print(f"Muscles per vector: {len(muscle_names)}")
    print(f"Subject Hmax: {_subject_hmax(feature_rows)}")

    scan_cfg = _build_scan_cfg(metadata_row, args)
    inferred_k_max = _default_k_max(metadata_row, sum(int(item.bundle.W_muscle.shape[1]) for item in feature_rows))
    resolved_k_max = args.max_clusters or inferred_k_max
    print(
        "No-gap rerun config:",
        f"algorithm={scan_cfg['algorithm']},",
        f"uniqueness_candidate_restarts={scan_cfg['uniqueness_candidate_restarts']},",
        f"max_iter={scan_cfg['max_iter']},",
        f"random_state={scan_cfg['random_state']},",
        f"k_max={resolved_k_max}",
    )
    print("Gap statistic used: False")

    if args.dry_run:
        print("\nDry run complete. No artifacts were written.")
        return

    _print_section("[M3] Scan First Zero-Duplicate K")
    scan_result = scan_first_zero_duplicate_k(
        feature_rows,
        group_id=args.group_id,
        cfg=scan_cfg,
        k_max=resolved_k_max,
    )
    for row in scan_result["scan_rows"]:
        print(
            f"K={row['k']}: duplicate_trials={row['duplicate_trial_count']}, "
            f"zero_duplicate={row['zero_duplicate_found']}, searched_restarts={row['searched_restarts']}"
        )
    if scan_result["selected_k"] is None:
        print("No zero-duplicate solution was found in the scanned range.")
        summary_payload = {
            "source_parquet": str(args.source_parquet.resolve()),
            "group_id": args.group_id,
            "analysis_date": "2026-03-19",
            "resolved_mode": mode,
            "vector_count": scan_result["vector_count"],
            "trial_count": scan_result["trial_count"],
            "muscle_count": len(muscle_names),
            "k_min": scan_result["k_min"],
            "k_max": scan_result["k_max"],
            "selection_method": "first_zero_duplicate",
            "gap_statistic_used": False,
            "k_selected_first_zero_duplicate": None,
            "pipeline_k_gap_raw": pipeline_k_gap_raw,
            "pipeline_k_selected": pipeline_k_selected,
            "pipeline_k_min_unique": pipeline_k_min_unique,
            "duplicate_trial_count_by_k": {str(row["k"]): int(row["duplicate_trial_count"]) for row in scan_result["scan_rows"]},
            "pipeline_duplicate_trial_count_by_k": {str(key): int(value) for key, value in pipeline_duplicate_counts.items()},
            "scan_cfg": scan_cfg,
        }
        k_scan_payload = {
            "selection_method": "first_zero_duplicate",
            "gap_statistic_used": False,
            "scan_rows": scan_result["scan_rows"],
        }
        _ensure_clean_dir(args.out_dir, overwrite=args.overwrite)
        summary_path = args.out_dir / "summary.json"
        k_scan_path = args.out_dir / "k_scan.json"
        _write_json(summary_path, summary_payload)
        _write_json(k_scan_path, k_scan_payload)
        checksum_path = args.out_dir / "checksums.md5"
        _write_checksums([summary_path, k_scan_path], checksum_path)
        raise SystemExit(1)
    else:
        print(f"First zero-duplicate K: {scan_result['selected_k']}")

    _print_section("[M4] Export Pipeline-Like Outputs")
    _ensure_clean_dir(args.out_dir, overwrite=args.overwrite)
    cluster_result = _cluster_result_from_scan(
        metadata_row=metadata_row,
        scan_result=scan_result,
        pipeline_duplicate_counts=pipeline_duplicate_counts,
    )
    export_cfg = _export_cfg(
        base_cfg_path=args.config,
        out_dir=args.out_dir,
        mode=mode,
        muscle_names=muscle_names,
    )
    export_context = _export_pipeline_like_outputs(
        out_dir=args.out_dir,
        mode=mode,
        cfg=export_cfg,
        feature_rows=feature_rows,
        cluster_result=cluster_result,
        group_id=args.group_id,
    )
    _inject_source_trial_windows_and_rerender(
        bundle=bundle,
        out_dir=args.out_dir,
        cfg=export_cfg,
        mode=mode,
    )
    _normalize_analysis_methods_manifest(args.out_dir)
    figure_path = _plot_duplicate_burden(
        scan_result["scan_rows"],
        pipeline_duplicate_counts,
        pipeline_k_gap_raw,
        pipeline_k_selected,
        scan_result["selected_k"],
        args.out_dir / "k_duplicate_burden.png",
    )
    k_scan_payload = {
        "selection_method": "first_zero_duplicate",
        "gap_statistic_used": False,
        "scan_rows": scan_result["scan_rows"],
    }
    summary_payload = {
        "source_parquet": str(args.source_parquet.resolve()),
        "group_id": args.group_id,
        "analysis_date": "2026-03-19",
        "resolved_mode": mode,
        "vector_count": scan_result["vector_count"],
        "trial_count": scan_result["trial_count"],
        "muscle_count": len(muscle_names),
        "k_min": scan_result["k_min"],
        "k_max": scan_result["k_max"],
        "selection_method": "first_zero_duplicate",
        "gap_statistic_used": False,
        "k_selected_first_zero_duplicate": scan_result["selected_k"],
        "pipeline_k_gap_raw": pipeline_k_gap_raw,
        "pipeline_k_selected": pipeline_k_selected,
        "pipeline_k_min_unique": pipeline_k_min_unique,
        "duplicate_trial_count_by_k": {str(row["k"]): int(row["duplicate_trial_count"]) for row in scan_result["scan_rows"]},
        "pipeline_duplicate_trial_count_by_k": {str(key): int(value) for key, value in pipeline_duplicate_counts.items()},
        "scan_cfg": scan_cfg,
        "figure_path": figure_path.name,
        "pipeline_like_output_dir": ".",
        "final_parquet_path": _path_relative_to(args.out_dir, export_context["artifacts"]["final_parquet_path"]),
        "final_parquet_alias_paths": export_context["artifacts"]["final_parquet_alias_paths"],
        "mode_output_dirs": export_context["artifacts"]["mode_output_dirs"],
        "clustering_audit_workbook_path": _path_relative_to(
            args.out_dir,
            export_context["artifacts"]["clustering_audit_workbook_path"],
        ),
        "results_interpretation_workbook_path": _path_relative_to(
            args.out_dir,
            export_context["artifacts"]["results_interpretation_workbook_path"],
        ),
        "group_figure_paths": [
            _path_relative_to(args.out_dir, path)
            for path in export_context["artifacts"]["group_figure_paths"]
        ],
        "trial_figure_paths": [
            _path_relative_to(args.out_dir, path)
            for path in export_context["artifacts"]["trial_figure_paths"]
        ],
    }
    summary_payload["final_parquet_alias_paths"] = {
        key: _path_relative_to(args.out_dir, value)
        for key, value in summary_payload["final_parquet_alias_paths"].items()
    }
    summary_payload["mode_output_dirs"] = {
        key: _path_relative_to(args.out_dir, value)
        for key, value in summary_payload["mode_output_dirs"].items()
    }
    summary_path = args.out_dir / "summary.json"
    k_scan_path = args.out_dir / "k_scan.json"
    _write_json(summary_path, summary_payload)
    _write_json(k_scan_path, k_scan_payload)
    checksum_path = args.out_dir / "checksums.md5"
    generated_paths = [path for path in args.out_dir.rglob("*") if path.is_file() and path.name != "checksums.md5"]
    _write_checksums(generated_paths, checksum_path)
    print(f"Wrote summary: {summary_path}")
    print(f"Wrote scan log: {k_scan_path}")
    print(f"Wrote figure: {figure_path}")
    print(f"Wrote final parquet: {export_context['artifacts']['final_parquet_path']}")
    print(f"Wrote mode workbook dir: {export_context['artifacts']['mode_output_dirs'][mode]}")
    print(f"Wrote checksums: {checksum_path}")


if __name__ == "__main__":
    main()
