"""Cluster selected synergy components into global step/nonstep groups."""

from __future__ import annotations

import math

from src.synergy_stats import cluster_feature_group
from src.synergy_stats.clustering import describe_clustering_runtime
from src.emg_pipeline.log_utils import format_float, log_kv_section


def _meta_flag(meta: dict, key: str) -> bool:
    value = meta.get(key, False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if value is None:
        return False
    try:
        if value != value:
            return False
    except Exception:
        pass
    return bool(value)


def run(context: dict) -> dict:
    cfg = context["config"]
    runtime = describe_clustering_runtime(cfg["synergy_clustering"])
    log_kv_section(
        "Clustering Runtime",
        [
            ("Algorithm", runtime["algorithm"]),
            ("Torch device", runtime["torch_device"] or "n/a"),
            ("Torch dtype", runtime["torch_dtype"] or "n/a"),
            ("Restart batch size", runtime["torch_restart_batch_size"]),
            ("Gap ref batch size", runtime["gap_reference_batch_size"]),
        ],
    )
    # Grouping is intentionally fixed to global step vs nonstep.
    if "grouping" in cfg.get("synergy_clustering", {}):
        raise ValueError(
            "`synergy_clustering.grouping` is no longer supported. "
            "Remove it from the YAML config; global grouping is fixed to step vs nonstep."
        )

    grouped_rows = {
        "global_step": [],
        "global_nonstep": [],
    }
    invalid_trials = []
    for item in context["feature_rows"]:
        if not _meta_flag(item.bundle.meta, "analysis_selected_group"):
            continue
        is_step = _meta_flag(item.bundle.meta, "analysis_is_step")
        is_nonstep = _meta_flag(item.bundle.meta, "analysis_is_nonstep")
        if is_step == is_nonstep:
            invalid_trials.append(f"{item.subject}_v{item.velocity}_T{item.trial_num}")
            continue
        target_group = "global_step" if is_step else "global_nonstep"
        grouped_rows[target_group].append(item)
    if invalid_trials:
        raise ValueError(
            "Selected trials must belong to exactly one global group: "
            + ", ".join(invalid_trials)
        )
    empty_groups = [group_id for group_id, feature_rows in grouped_rows.items() if not feature_rows]
    if empty_groups:
        raise ValueError(f"Global clustering requires non-empty groups for: {empty_groups}")

    cluster_group_results = {}
    for group_id, feature_rows in grouped_rows.items():
        cluster_result = cluster_feature_group(feature_rows, cfg["synergy_clustering"], group_id=group_id)
        if cluster_result.get("status") != "success":
            reason = cluster_result.get("reason", "Unknown clustering failure.")
            raise RuntimeError(f"Clustering failed for {group_id}: {reason}")
        inertia = cluster_result.get("inertia")
        inertia_display = (
            format_float(inertia, digits=6)
            if inertia is not None and not (isinstance(inertia, float) and math.isnan(inertia))
            else "n/a"
        )
        log_kv_section(
            f"Cluster Result: {group_id}",
            [
                ("K gap raw", cluster_result.get("k_gap_raw", "n/a")),
                ("K selected", cluster_result.get("k_selected", "n/a")),
                ("Selection status", cluster_result.get("selection_status", "n/a")),
                ("Duplicate trials", len(cluster_result.get("duplicate_trials", []))),
                ("Inertia", inertia_display),
                ("Algorithm used", cluster_result.get("algorithm_used", "n/a")),
            ],
        )
        cluster_group_results[group_id] = {
            "group_id": group_id,
            "feature_rows": feature_rows,
            "cluster_result": cluster_result,
        }
    context["cluster_group_results"] = cluster_group_results
    return context
