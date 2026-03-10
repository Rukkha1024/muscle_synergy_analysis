"""Render representative figures for global step and nonstep clusters."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd


SUPPORTED_FIGURE_FORMATS = {"png", "jpg", "jpeg", "tif", "tiff"}


def _figure_cfg(cfg: dict) -> dict:
    return cfg.get("figures", {})


def _normalized_figure_format(cfg: dict) -> str:
    raw = str(_figure_cfg(cfg).get("format", "png")).strip().lower().lstrip(".")
    normalized = "jpeg" if raw == "jpg" else raw
    if normalized not in SUPPORTED_FIGURE_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FIGURE_FORMATS))
        raise ValueError(f"Unsupported figure format for export: {raw}. Supported formats: {supported}")
    return normalized


def figure_suffix(cfg: dict) -> str:
    return f".{_normalized_figure_format(cfg)}"


def _figure_dpi(cfg: dict) -> int:
    return int(_figure_cfg(cfg).get("dpi", 150))


def _group_title(group_id: str) -> str:
    if group_id == "global_step":
        return "Global step clusters"
    if group_id == "global_nonstep":
        return "Global nonstep clusters"
    return group_id.replace("_", " ").title()


def save_group_cluster_figure(
    group_id: str,
    rep_w: pd.DataFrame,
    rep_h: pd.DataFrame,
    muscle_names: list[str],
    cfg: dict,
    output_path: Path,
) -> None:
    cluster_ids = sorted(rep_w["cluster_id"].dropna().unique().tolist()) if not rep_w.empty else []
    n_clusters = max(len(cluster_ids), 1)
    fig, axes = plt.subplots(n_clusters, 2, figsize=(14, 3.5 * n_clusters), squeeze=False)
    fig.suptitle(_group_title(group_id), fontsize=14, y=0.995)
    for row_index, cluster_id in enumerate(cluster_ids or [0]):
        ax_w, ax_h = axes[row_index]
        cluster_w = rep_w.loc[rep_w["cluster_id"] == cluster_id].copy()
        cluster_h = rep_h.loc[rep_h["cluster_id"] == cluster_id].copy()
        if cluster_w.empty or cluster_h.empty:
            ax_w.text(0.5, 0.5, "No representative cluster", ha="center", va="center")
            ax_h.text(0.5, 0.5, "No representative cluster", ha="center", va="center")
        else:
            cluster_w["muscle"] = pd.Categorical(cluster_w["muscle"], categories=muscle_names, ordered=True)
            cluster_w = cluster_w.sort_values("muscle")
            ax_w.bar(cluster_w["muscle"].astype(str), cluster_w["W_value"], color="#5C7CFA")
            ax_w.set_ylim(0.0, max(1.0, float(cluster_w["W_value"].max()) * 1.15))
            ax_w.set_title(f"Cluster {cluster_id}: W")
            ax_w.tick_params(axis="x", rotation=45)

            cluster_h = cluster_h.sort_values("frame_idx")
            x_values = cluster_h["frame_idx"].to_numpy(dtype=float)
            if len(x_values) > 1:
                x_values = 100.0 * x_values / float(x_values.max())
            ax_h.plot(x_values, cluster_h["h_value"], color="#2F9E44", linewidth=2.0)
            ax_h.set_xlim(0.0, 100.0)
            ax_h.set_title(f"Cluster {cluster_id}: H (100-window)")
            ax_h.set_xlabel("Normalized window (%)")
        ax_w.set_ylabel("Weight")
        ax_h.set_ylabel("Activation")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=_figure_dpi(cfg), format=_normalized_figure_format(cfg), bbox_inches="tight")
    plt.close(fig)


def save_subject_cluster_figure(
    subject_id: str,
    rep_w: pd.DataFrame,
    rep_h: pd.DataFrame,
    muscle_names: list[str],
    cfg: dict,
    output_path: Path,
) -> None:
    """Compatibility wrapper for legacy import paths."""

    save_group_cluster_figure(subject_id, rep_w, rep_h, muscle_names, cfg, output_path)
