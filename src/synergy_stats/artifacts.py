"""Export group-level EMG synergy artifacts.

This module writes one directory per global clustering group,
merges those group exports into run-level CSVs,
and records the final parquet plus figure paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .clustering import build_group_exports, save_group_outputs
from .figures import figure_suffix, save_group_cluster_figure


def summarize_group_results(group_rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(group_rows)


def summarize_subject_results(group_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Compatibility alias retained for older imports."""
    return summarize_group_results(group_rows)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.10f")


def export_results(context: dict[str, Any]) -> dict[str, Any]:
    cfg = context["config"]
    runtime_cfg = cfg["runtime"]
    output_dir = Path(runtime_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    muscle_names = list(cfg["muscles"]["names"])
    target_windows = int(
        cfg.get("synergy_clustering", {})
        .get("representative", {})
        .get("h_output_interpolation", {})
        .get("target_windows", 100)
    )

    all_frames = {
        "metadata": [],
        "labels": [],
        "members": [],
        "rep_W": [],
        "rep_H_long": [],
        "minimal_W": [],
        "minimal_H_long": [],
        "trial_windows": [],
    }
    group_summaries = []
    group_figure_paths: list[Path] = []
    figure_dir = output_dir / "figures"
    figure_ext = figure_suffix(cfg)
    for group_id in ("global_step", "global_nonstep"):
        payload = context["cluster_group_results"][group_id]
        exports = build_group_exports(
            group_id=group_id,
            feature_rows=payload["feature_rows"],
            cluster_result=payload["cluster_result"],
            muscle_names=muscle_names,
            target_windows=target_windows,
        )
        group_dir = output_dir / group_id
        save_group_outputs(group_dir, exports)
        group_figure_path = figure_dir / f"{group_id}_clusters{figure_ext}"
        save_group_cluster_figure(
            group_id=group_id,
            rep_w=exports.get("rep_W", pd.DataFrame()),
            rep_h=exports.get("rep_H_long", pd.DataFrame()),
            muscle_names=muscle_names,
            cfg=cfg,
            output_path=group_figure_path,
        )
        group_figure_paths.append(group_figure_path)
        for key in all_frames:
            frame = exports.get(key, pd.DataFrame())
            if not frame.empty:
                all_frames[key].append(frame)
        group_summaries.append(
            {
                "group_id": group_id,
                "n_trials": len(payload["feature_rows"]),
                "n_components": int(sum(item.bundle.W_muscle.shape[1] for item in payload["feature_rows"])),
                "n_clusters": payload["cluster_result"].get("n_clusters", 0),
                "status": payload["cluster_result"].get("status", "unknown"),
                "duplicate_trials": str(payload["cluster_result"].get("duplicate_trials", [])),
                "algorithm_used": payload["cluster_result"].get("algorithm_used", ""),
                "group_figure_path": str(group_figure_path.relative_to(output_dir)),
            }
        )

    summary_df = summarize_group_results(group_summaries)
    _write_csv(summary_df, output_dir / "final_summary.csv")

    aggregate_name_map = {
        "metadata": "all_clustering_metadata.csv",
        "labels": "all_cluster_labels.csv",
        "members": "all_cluster_members.csv",
        "rep_W": "all_representative_W_posthoc.csv",
        "rep_H_long": "all_representative_H_posthoc_long.csv",
        "minimal_W": "all_minimal_units_W.csv",
        "minimal_H_long": "all_minimal_units_H_long.csv",
        "trial_windows": "all_trial_window_metadata.csv",
    }
    final_parquet_frame = None
    for key, filename in aggregate_name_map.items():
        frame = pd.concat(all_frames[key], ignore_index=True) if all_frames[key] else pd.DataFrame()
        _write_csv(frame, output_dir / filename)
        if key == "minimal_W":
            final_parquet_frame = frame

    if final_parquet_frame is None:
        final_parquet_frame = pd.DataFrame()
    final_parquet_path = Path(runtime_cfg["final_parquet_path"])
    final_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    final_parquet_frame.to_parquet(final_parquet_path, index=False)
    context["artifacts"]["summary_path"] = str(output_dir / "final_summary.csv")
    context["artifacts"]["final_parquet_path"] = str(final_parquet_path)
    context["artifacts"]["group_figure_paths"] = [str(path) for path in group_figure_paths]
    return context
