"""Cluster selected synergy components into global step/nonstep groups."""

from __future__ import annotations

import logging

from src.synergy_stats import cluster_feature_group


def run(context: dict) -> dict:
    cfg = context["config"]
    grouping_mode = str(cfg["synergy_clustering"].get("grouping", {}).get("mode", "global_step_nonstep")).strip().lower()
    if grouping_mode != "global_step_nonstep":
        raise ValueError(f"Unsupported grouping mode: {grouping_mode}")

    selected_rows = [
        item
        for item in context["feature_rows"]
        if bool(item.bundle.meta.get("analysis_selected_group", False))
    ]
    grouped_rows = {
        "global_step": [
            item
            for item in selected_rows
            if bool(item.bundle.meta.get("analysis_is_step", False))
        ],
        "global_nonstep": [
            item
            for item in selected_rows
            if bool(item.bundle.meta.get("analysis_is_nonstep", False))
        ],
    }
    empty_groups = [group_id for group_id, feature_rows in grouped_rows.items() if not feature_rows]
    if empty_groups:
        raise ValueError(f"Global clustering requires non-empty groups for: {empty_groups}")

    cluster_group_results = {}
    for group_id, feature_rows in grouped_rows.items():
        cluster_result = cluster_feature_group(feature_rows, cfg["synergy_clustering"], group_id=group_id)
        if cluster_result.get("status") != "success":
            reason = cluster_result.get("reason", "Unknown clustering failure.")
            raise RuntimeError(f"Clustering failed for {group_id}: {reason}")
        cluster_group_results[group_id] = {
            "group_id": group_id,
            "feature_rows": feature_rows,
            "cluster_result": cluster_result,
        }
    context["cluster_group_results"] = cluster_group_results
    logging.info("Clustered synergies for %s global groups.", len(cluster_group_results))
    return context
