"""Export subject and run-level EMG synergy artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .clustering import build_subject_exports, save_subject_outputs


def summarize_subject_results(subject_rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(subject_rows)


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
    }
    subject_summaries = []
    for subject_id, payload in context["subject_results"].items():
        exports = build_subject_exports(
            subject_id=subject_id,
            feature_rows=payload["feature_rows"],
            cluster_result=payload["cluster_result"],
            muscle_names=muscle_names,
            target_windows=target_windows,
        )
        subject_dir = output_dir / f"subject_{subject_id}"
        save_subject_outputs(subject_dir, exports)
        for key in all_frames:
            frame = exports.get(key, pd.DataFrame())
            if not frame.empty:
                all_frames[key].append(frame)
        subject_summaries.append(
            {
                "subject": subject_id,
                "n_trials": len(payload["feature_rows"]),
                "n_clusters": payload["cluster_result"].get("n_clusters", 0),
                "status": payload["cluster_result"].get("status", "unknown"),
                "duplicate_trials": str(payload["cluster_result"].get("duplicate_trials", [])),
                "algorithm_used": payload["cluster_result"].get("algorithm_used", ""),
            }
        )

    summary_df = summarize_subject_results(subject_summaries)
    summary_df.to_csv(output_dir / "final_summary.csv", index=False, encoding="utf-8-sig")

    aggregate_name_map = {
        "metadata": "all_clustering_metadata.csv",
        "labels": "all_cluster_labels.csv",
        "members": "all_cluster_members.csv",
        "rep_W": "all_representative_W_posthoc.csv",
        "rep_H_long": "all_representative_H_posthoc_long.csv",
        "minimal_W": "all_minimal_units_W.csv",
        "minimal_H_long": "all_minimal_units_H_long.csv",
    }
    final_parquet_frame = None
    for key, filename in aggregate_name_map.items():
        frame = pd.concat(all_frames[key], ignore_index=True) if all_frames[key] else pd.DataFrame()
        frame.to_csv(output_dir / filename, index=False, encoding="utf-8-sig")
        if key == "minimal_W":
            final_parquet_frame = frame

    if final_parquet_frame is None:
        final_parquet_frame = pd.DataFrame()
    final_parquet_path = Path(runtime_cfg["final_parquet_path"])
    final_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    final_parquet_frame.to_parquet(final_parquet_path, index=False)
    context["artifacts"]["summary_path"] = str(output_dir / "final_summary.csv")
    context["artifacts"]["final_parquet_path"] = str(final_parquet_path)
    return context
