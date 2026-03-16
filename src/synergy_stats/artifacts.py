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

from .clustering import build_group_exports
from .cross_group_similarity import (
    annotate_pairwise_assignment,
    build_cluster_decision,
    build_cluster_w_matrix,
    build_cross_group_summary,
    build_pairwise_matrix,
    compute_pairwise_cosine,
    solve_assignment,
)
from .excel_audit import validate_clustering_audit_workbook, write_clustering_audit_workbook
from .excel_results import (
    validate_results_interpretation_workbook,
    write_results_interpretation_workbook,
)
from .figure_rerender import render_figures_from_run_dir
from .figures import figure_suffix


def summarize_group_results(group_rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(group_rows)


def summarize_subject_results(group_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Compatibility alias retained for older imports."""
    return summarize_group_results(group_rows)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.10f")


def _cross_group_similarity_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    raw_cfg = cfg.get("cross_group_w_similarity", {})
    return {
        "enabled": bool(raw_cfg.get("enabled", True)),
        "metric": str(raw_cfg.get("metric", "cosine")).strip().lower() or "cosine",
        "threshold": float(raw_cfg.get("threshold", 0.8)),
        "assignment": str(raw_cfg.get("assignment", "linear_sum_assignment")).strip().lower()
        or "linear_sum_assignment",
        "output_pairwise_csv": bool(raw_cfg.get("output_pairwise_csv", True)),
        "output_cluster_decision_csv": bool(raw_cfg.get("output_cluster_decision_csv", True)),
        "output_excel_sheets": bool(raw_cfg.get("output_excel_sheets", True)),
        "output_figures": bool(raw_cfg.get("output_figures", True)),
    }


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
        "rep_W": [],
        "rep_H_long": [],
        "minimal_W": [],
        "minimal_H_long": [],
        "trial_windows": [],
    }
    group_summaries = []
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
        group_figure_path = figure_dir / f"{group_id}_clusters{figure_ext}"
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
    summary_df = summarize_group_results(group_summaries)
    _write_csv(summary_df, output_dir / "final_summary.csv")

    aggregate_name_map = {
        "metadata": "all_clustering_metadata.csv",
        "labels": "all_cluster_labels.csv",
        "rep_W": "all_representative_W_posthoc.csv",
        "rep_H_long": "all_representative_H_posthoc_long.csv",
        "minimal_W": "all_minimal_units_W.csv",
        "minimal_H_long": "all_minimal_units_H_long.csv",
        "trial_windows": "all_trial_window_metadata.csv",
    }
    final_parquet_frame = None
    aggregate_frames: dict[str, pd.DataFrame] = {}
    for key, filename in aggregate_name_map.items():
        frame = pd.concat(all_frames[key], ignore_index=True) if all_frames[key] else pd.DataFrame()
        aggregate_frames[key] = frame
        _write_csv(frame, output_dir / filename)
        if key == "minimal_W":
            final_parquet_frame = frame

    if final_parquet_frame is None:
        final_parquet_frame = pd.DataFrame()
    final_parquet_path = Path(runtime_cfg["final_parquet_path"])
    final_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    final_parquet_frame.to_parquet(final_parquet_path, index=False)

    cross_group_cfg = _cross_group_similarity_cfg(cfg)
    cross_group_artifacts: dict[str, pd.DataFrame] = {}
    if cross_group_cfg["enabled"]:
        if cross_group_cfg["metric"] != "cosine":
            raise ValueError(f"Unsupported cross_group_w_similarity.metric: {cross_group_cfg['metric']}")
        if cross_group_cfg["assignment"] != "linear_sum_assignment":
            raise ValueError(
                f"Unsupported cross_group_w_similarity.assignment: {cross_group_cfg['assignment']}"
            )
        step_df, nonstep_df = build_cluster_w_matrix(aggregate_frames["rep_W"], muscle_names)
        pairwise_df = compute_pairwise_cosine(step_df, nonstep_df)
        assigned_df = solve_assignment(pairwise_df)
        pairwise_output_df = annotate_pairwise_assignment(
            pairwise_df,
            assigned_df,
            cross_group_cfg["threshold"],
        )
        decision_df = build_cluster_decision(
            step_df,
            nonstep_df,
            pairwise_df,
            assigned_df,
            cross_group_cfg["threshold"],
        )
        cross_group_artifacts = {
            "cross_group_pairwise": pairwise_output_df,
            "cross_group_matrix": build_pairwise_matrix(pairwise_df),
            "cross_group_decision": decision_df,
            "cross_group_summary": build_cross_group_summary(
                step_df,
                nonstep_df,
                decision_df,
                cross_group_cfg["threshold"],
            ),
        }
        if cross_group_cfg["output_pairwise_csv"]:
            pairwise_path = output_dir / "cross_group_w_pairwise_cosine.csv"
            _write_csv(pairwise_output_df, pairwise_path)
            context["artifacts"]["cross_group_pairwise_path"] = str(pairwise_path)
        if cross_group_cfg["output_cluster_decision_csv"]:
            decision_path = output_dir / "cross_group_w_cluster_decision.csv"
            _write_csv(decision_df, decision_path)
            context["artifacts"]["cross_group_cluster_decision_path"] = str(decision_path)

    workbook_path = write_clustering_audit_workbook(
        output_dir / "clustering_audit.xlsx",
        context["cluster_group_results"],
    )
    workbook_validation = validate_clustering_audit_workbook(workbook_path)
    interpretation_workbook_path = write_results_interpretation_workbook(
        output_dir / "results_interpretation.xlsx",
        summary_df,
        {
            **aggregate_frames,
            **(
                cross_group_artifacts
                if cross_group_cfg["enabled"] and cross_group_cfg["output_excel_sheets"]
                else {}
            ),
        },
    )
    interpretation_workbook_validation = validate_results_interpretation_workbook(interpretation_workbook_path)
    logging.info("Saved clustering audit workbook to %s", workbook_path)
    logging.info(
        "Clustering audit workbook validation: engine=%s excel_ui_visual_qa=%s fallback_reason=%s",
        workbook_validation["engine"],
        workbook_validation["excel_ui_visual_qa"],
        workbook_validation["fallback_reason"],
    )
    logging.info("Saved interpretation workbook to %s", interpretation_workbook_path)
    logging.info(
        "Interpretation workbook validation: engine=%s excel_ui_visual_qa=%s fallback_reason=%s",
        interpretation_workbook_validation["engine"],
        interpretation_workbook_validation["excel_ui_visual_qa"],
        interpretation_workbook_validation["fallback_reason"],
    )
    context["artifacts"]["summary_path"] = str(output_dir / "final_summary.csv")
    context["artifacts"]["final_parquet_path"] = str(final_parquet_path)
    context["artifacts"]["clustering_audit_workbook_path"] = str(workbook_path)
    context["artifacts"]["clustering_audit_workbook_validation"] = workbook_validation
    context["artifacts"]["results_interpretation_workbook_path"] = str(interpretation_workbook_path)
    context["artifacts"]["results_interpretation_workbook_validation"] = interpretation_workbook_validation
    rendered_figures = render_figures_from_run_dir(output_dir, cfg)
    context["artifacts"]["group_figure_paths"] = rendered_figures["group_figure_paths"]
    context["artifacts"]["trial_figure_paths"] = rendered_figures["trial_figure_paths"]
    if rendered_figures["cross_group_figure_paths"]:
        context["artifacts"]["cross_group_figure_paths"] = rendered_figures["cross_group_figure_paths"]
    return context
