"""Render global cluster and per-trial NMF figures with a shared layout."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
import pandas as pd


SUPPORTED_FIGURE_FORMATS = {"png", "jpg", "jpeg", "tif", "tiff"}
KOREAN_FONT_CANDIDATES = (
    "NanumGothic",
    "NanumBarunGothic",
    "Malgun Gothic",
    "AppleGothic",
    "Noto Sans CJK KR",
    "Noto Sans KR",
)

_PYPLOT = None
_FONTS_CONFIGURED = False


def _pyplot():
    global _PYPLOT
    if _PYPLOT is not None:
        return _PYPLOT
    try:
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
    import matplotlib.pyplot as plt

    _PYPLOT = plt
    return plt


def _configure_fonts() -> None:
    global _FONTS_CONFIGURED
    if _FONTS_CONFIGURED:
        return
    from matplotlib import font_manager

    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    preferred_font = next((name for name in KOREAN_FONT_CANDIDATES if name in available_fonts), None)
    if preferred_font is not None:
        matplotlib.rcParams["font.family"] = [preferred_font]
    matplotlib.rcParams["axes.unicode_minus"] = False
    _FONTS_CONFIGURED = True


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


def _display_value(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _normalized_component_axis(values: pd.Series) -> tuple[pd.Series, list[float]]:
    ordered = values.sort_values("frame_idx")
    x_values = ordered["frame_idx"].to_numpy(dtype=float)
    if len(x_values) > 1 and float(x_values.max()) > 0.0:
        x_values = 100.0 * x_values / float(x_values.max())
    return ordered["h_value"], x_values.tolist()


def _build_cluster_coverage(
    cluster_labels: pd.DataFrame,
    trial_metadata: pd.DataFrame,
) -> tuple[int, int, pd.DataFrame]:
    """Return (total_trials, total_subjects, per-cluster coverage DataFrame)."""
    total_trials = int(trial_metadata["trial_id"].nunique())
    total_subjects = int(trial_metadata["subject"].nunique())
    coverage = (
        cluster_labels.groupby("cluster_id")
        .agg(n_trials=("trial_id", "nunique"), n_subjects=("subject", "nunique"))
        .reset_index()
    )
    coverage["trial_pct"] = (coverage["n_trials"] / total_trials * 100).round(1)
    return total_trials, total_subjects, coverage


def _render_component_grid(
    title: str,
    rep_w: pd.DataFrame,
    rep_h: pd.DataFrame,
    muscle_names: list[str],
    cfg: dict,
    output_path: Path,
    *,
    row_label: str,
    coverage: Optional[pd.DataFrame] = None,
    total_trials: Optional[int] = None,
    total_subjects: Optional[int] = None,
) -> None:
    plt = _pyplot()
    _configure_fonts()
    cluster_ids = sorted(rep_w["cluster_id"].dropna().unique().tolist()) if not rep_w.empty else []
    n_clusters = max(len(cluster_ids), 1)

    fig, axes = plt.subplots(n_clusters, 2, figsize=(14, 3.5 * n_clusters), squeeze=False)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.995)
    for row_index, cluster_id in enumerate(cluster_ids or [0]):
        ax_w, ax_h = axes[row_index]

        subtitle = ""
        if coverage is not None and total_trials is not None and total_subjects is not None:
            cov_row = coverage.loc[coverage["cluster_id"] == cluster_id]
            if not cov_row.empty:
                nt = int(cov_row["n_trials"].iloc[0])
                ns = int(cov_row["n_subjects"].iloc[0])
                tp = float(cov_row["trial_pct"].iloc[0])
                subtitle = f"\n{nt}/{total_trials} trials ({tp}%)  |  {ns}/{total_subjects} subjects"

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
            ax_w.set_title(f"{row_label} {cluster_id}: W{subtitle}", fontsize=11)
            ax_w.tick_params(axis="x", rotation=45)

            h_values, x_values = _normalized_component_axis(cluster_h)
            ax_h.plot(x_values, h_values.to_numpy(dtype=float), color="#2F9E44", linewidth=2.0)
            ax_h.set_xlim(0.0, 100.0)
            ax_h.set_title(f"{row_label} {cluster_id}: H (100-window){subtitle}", fontsize=11)
            ax_h.set_xlabel("Normalized window (%)")
        ax_w.set_ylabel("Weight")
        ax_h.set_ylabel("Activation")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=_figure_dpi(cfg), format=_normalized_figure_format(cfg), bbox_inches="tight")
    plt.close(fig)


def save_group_cluster_figure(
    group_id: str,
    rep_w: pd.DataFrame,
    rep_h: pd.DataFrame,
    muscle_names: list[str],
    cfg: dict,
    output_path: Path,
    cluster_labels: Optional[pd.DataFrame] = None,
    trial_metadata: Optional[pd.DataFrame] = None,
) -> None:
    has_coverage = cluster_labels is not None and trial_metadata is not None
    if has_coverage:
        total_trials, total_subjects, coverage = _build_cluster_coverage(
            cluster_labels, trial_metadata,
        )
        title = f"{_group_title(group_id)}  (n={total_trials} trials, {total_subjects} subjects)"
    else:
        coverage = pd.DataFrame()
        title = _group_title(group_id)

    _render_component_grid(
        title=title,
        rep_w=rep_w,
        rep_h=rep_h,
        muscle_names=muscle_names,
        cfg=cfg,
        output_path=output_path,
        row_label="Cluster",
        coverage=coverage if has_coverage else None,
        total_trials=total_trials if has_coverage else None,
        total_subjects=total_subjects if has_coverage else None,
    )


def save_trial_nmf_figure(
    subject: str,
    velocity: object,
    trial_num: object,
    step_class: str,
    trial_w: pd.DataFrame,
    trial_h: pd.DataFrame,
    muscle_names: list[str],
    cfg: dict,
    output_path: Path,
) -> None:
    """Render one trial's NMF components with the cluster figure layout."""

    title = f"{subject} v{_display_value(velocity)} T{_display_value(trial_num)} ({step_class})"
    _render_component_grid(
        title=title,
        rep_w=trial_w,
        rep_h=trial_h,
        muscle_names=muscle_names,
        cfg=cfg,
        output_path=output_path,
        row_label="Component",
    )


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
