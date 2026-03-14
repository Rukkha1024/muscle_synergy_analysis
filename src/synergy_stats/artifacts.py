"""Export group-level and trial-level EMG synergy artifacts.

This module writes one directory per global clustering group,
merges those group exports into run-level CSVs,
and records the final parquet plus figure paths.
"""

from __future__ import annotations

from pathlib import Path
import logging
from typing import Any

import pandas as pd

from .clustering import build_group_exports, save_group_outputs
from .excel_audit import validate_clustering_audit_workbook, write_clustering_audit_workbook
from .figures import figure_suffix, save_group_cluster_figure, save_trial_nmf_figure


def summarize_group_results(group_rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(group_rows)


def summarize_subject_results(group_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Compatibility alias retained for older imports."""
    return summarize_group_results(group_rows)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.10f")


def _format_filename_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text.replace("/", "-").replace("\\", "-").replace(" ", "_")


def _trial_figure_name(feature_row: Any, figure_ext: str) -> str:
    step_class = str(feature_row.bundle.meta.get("analysis_step_class", "unknown")).strip().lower() or "unknown"
    subject = _format_filename_value(feature_row.subject)
    velocity = _format_filename_value(feature_row.velocity)
    trial_num = _format_filename_value(feature_row.trial_num)
    return f"{subject}_v{velocity}_T{trial_num}_{step_class}_nmf{figure_ext}"


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
    trial_figure_paths: list[Path] = []
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
            cluster_labels=exports.get("labels", pd.DataFrame()),
            trial_metadata=exports.get("trial_windows", pd.DataFrame()),
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
                "selection_method": payload["cluster_result"].get("selection_method", ""),
                "selection_status": payload["cluster_result"].get("selection_status", ""),
                "k_gap_raw": payload["cluster_result"].get("k_gap_raw", ""),
                "k_selected": payload["cluster_result"].get("k_selected", ""),
                "k_min_unique": payload["cluster_result"].get("k_min_unique", ""),
                "duplicate_trials": str(payload["cluster_result"].get("duplicate_trials", [])),
                "algorithm_used": payload["cluster_result"].get("algorithm_used", ""),
                "group_figure_path": str(group_figure_path.relative_to(output_dir)),
            }
        )

    trial_figure_dir = figure_dir / "nmf_trials"
    for feature_row in context["feature_rows"]:
        step_class = str(feature_row.bundle.meta.get("analysis_step_class", "unknown")).strip().lower() or "unknown"
        trial_figure_path = trial_figure_dir / _trial_figure_name(feature_row, figure_ext)
        trial_w = pd.DataFrame(
            [
                {
                    "cluster_id": component_index,
                    "muscle": muscle_names[muscle_index],
                    "W_value": float(value),
                }
                for component_index in range(feature_row.bundle.W_muscle.shape[1])
                for muscle_index, value in enumerate(feature_row.bundle.W_muscle[:, component_index])
            ]
        )
        trial_h = pd.DataFrame(
            [
                {
                    "cluster_id": component_index,
                    "frame_idx": frame_idx,
                    "h_value": float(value),
                }
                for component_index in range(feature_row.bundle.H_time.shape[1])
                for frame_idx, value in enumerate(feature_row.bundle.H_time[:, component_index])
            ]
        )
        save_trial_nmf_figure(
            subject=str(feature_row.subject),
            velocity=feature_row.velocity,
            trial_num=feature_row.trial_num,
            step_class=step_class,
            trial_w=trial_w,
            trial_h=trial_h,
            muscle_names=muscle_names,
            cfg=cfg,
            output_path=trial_figure_path,
        )
        trial_figure_paths.append(trial_figure_path)

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
    workbook_path = write_clustering_audit_workbook(
        output_dir / "clustering_audit.xlsx",
        context["cluster_group_results"],
    )
    workbook_validation = validate_clustering_audit_workbook(workbook_path)
    logging.info("Saved clustering audit workbook to %s", workbook_path)
    logging.info(
        "Clustering audit workbook validation: engine=%s excel_ui_visual_qa=%s fallback_reason=%s",
        workbook_validation["engine"],
        workbook_validation["excel_ui_visual_qa"],
        workbook_validation["fallback_reason"],
    )
    context["artifacts"]["summary_path"] = str(output_dir / "final_summary.csv")
    context["artifacts"]["final_parquet_path"] = str(final_parquet_path)
    context["artifacts"]["clustering_audit_workbook_path"] = str(workbook_path)
    context["artifacts"]["clustering_audit_workbook_validation"] = workbook_validation
    context["artifacts"]["group_figure_paths"] = [str(path) for path in group_figure_paths]
    context["artifacts"]["trial_figure_paths"] = [str(path) for path in trial_figure_paths]
    return context
