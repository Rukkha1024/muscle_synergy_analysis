"""Render global cluster and per-trial NMF figures with a shared layout."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
import pandas as pd


SUPPORTED_FIGURE_FORMATS = {"png", "jpg", "jpeg", "tif", "tiff"}
STRATEGY_COLORS = {"step": "#5C7CFA", "nonstep": "#E64980"}
MIN_STRATEGY_N = 3
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
    if group_id == "pooled_step_nonstep":
        return "Pooled step/nonstep clusters"
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


def _build_strategy_subtitle_part(
    strategy_summary: pd.DataFrame,
    cluster_id: object,
    cluster_total: int,
) -> str:
    """Return strategy portion of subtitle: ``step X/N, nonstep Y/N``."""
    crows = strategy_summary[strategy_summary["cluster_id"] == cluster_id]
    step_row = crows[crows["strategy_label"] == "step"]
    nonstep_row = crows[crows["strategy_label"] == "nonstep"]
    sn = int(step_row["n_rows"].iloc[0]) if not step_row.empty else 0
    nn = int(nonstep_row["n_rows"].iloc[0]) if not nonstep_row.empty else 0
    return f"step {sn}/{cluster_total}, nonstep {nn}/{cluster_total}"


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
    strategy_summary: Optional[pd.DataFrame] = None,
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
                if strategy_summary is not None and not strategy_summary.empty:
                    ct = int(cov_row["n_trials"].iloc[0])
                    strategy_part = _build_strategy_subtitle_part(strategy_summary, cluster_id, ct)
                    subtitle += f"  |  {strategy_part}"

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
    strategy_summary: Optional[pd.DataFrame] = None,
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
        strategy_summary=strategy_summary,
    )


def save_cluster_strategy_composition(
    strategy_summary: pd.DataFrame,
    cfg: dict,
    output_path: Path,
) -> None:
    """Render cluster-by-strategy 100% stacked bar chart (Figure 03)."""
    plt = _pyplot()
    _configure_fonts()

    if strategy_summary.empty:
        return

    cluster_ids = sorted(strategy_summary["cluster_id"].unique())
    n_clusters = len(cluster_ids)

    step_fracs = []
    nonstep_fracs = []
    totals = []
    for cid in cluster_ids:
        crows = strategy_summary[strategy_summary["cluster_id"] == cid]
        step_row = crows[crows["strategy_label"] == "step"]
        nonstep_row = crows[crows["strategy_label"] == "nonstep"]
        sf = float(step_row["fraction_within_cluster"].iloc[0]) if not step_row.empty else 0.0
        nf = float(nonstep_row["fraction_within_cluster"].iloc[0]) if not nonstep_row.empty else 0.0
        step_fracs.append(sf)
        nonstep_fracs.append(nf)
        total = int(crows["cluster_total_rows"].iloc[0]) if not crows.empty else 0
        totals.append(total)

    import numpy as np

    x = np.arange(n_clusters)
    width = 0.6

    fig, ax = plt.subplots(figsize=(max(8, 0.8 * n_clusters), 5))
    ax.bar(x, step_fracs, width, color=STRATEGY_COLORS["step"], label="step")
    ax.bar(x, nonstep_fracs, width, bottom=step_fracs, color=STRATEGY_COLORS["nonstep"], label="nonstep")

    for i, total in enumerate(totals):
        ax.text(i, 1.02, f"n={total}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([str(c) for c in cluster_ids])
    ax.set_xlabel("Cluster ID")
    ax.set_ylabel("Fraction")
    ax.set_ylim(0.0, 1.15)
    ax.set_title("Cluster strategy composition (step / nonstep)", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=_figure_dpi(cfg), format=_normalized_figure_format(cfg), bbox_inches="tight")
    plt.close(fig)


def save_within_cluster_strategy_overlay(
    strategy_w_means: pd.DataFrame,
    strategy_h_means: pd.DataFrame,
    strategy_summary: pd.DataFrame,
    muscle_names: list[str],
    cfg: dict,
    output_path: Path,
) -> None:
    """Render per-cluster step vs nonstep W bar + H overlay (Figure 05)."""
    import numpy as np

    plt = _pyplot()
    _configure_fonts()

    if strategy_w_means.empty or strategy_h_means.empty:
        return

    cluster_ids = sorted(strategy_w_means["cluster_id"].unique())
    n_clusters = len(cluster_ids)
    if n_clusters == 0:
        return

    fig, axes = plt.subplots(n_clusters, 2, figsize=(14, 3.5 * n_clusters), squeeze=False)
    fig.suptitle("Within-cluster strategy overlay (step vs nonstep)", fontsize=14, fontweight="bold", y=0.995)

    for row_idx, cid in enumerate(cluster_ids):
        ax_w, ax_h = axes[row_idx]

        # Build subtitle
        subtitle = ""
        if not strategy_summary.empty:
            crows = strategy_summary[strategy_summary["cluster_id"] == cid]
            step_row = crows[crows["strategy_label"] == "step"]
            nonstep_row = crows[crows["strategy_label"] == "nonstep"]
            sn = int(step_row["n_rows"].iloc[0]) if not step_row.empty else 0
            nn = int(nonstep_row["n_rows"].iloc[0]) if not nonstep_row.empty else 0
            ct = sn + nn
            subtitle = f"\nstep {sn}/{ct}, nonstep {nn}/{ct}"

        # Check minimum n
        crows = strategy_summary[strategy_summary["cluster_id"] == cid] if not strategy_summary.empty else pd.DataFrame()
        step_n = int(crows.loc[crows["strategy_label"] == "step", "n_rows"].iloc[0]) if not crows.empty and not crows.loc[crows["strategy_label"] == "step"].empty else 0
        nonstep_n = int(crows.loc[crows["strategy_label"] == "nonstep", "n_rows"].iloc[0]) if not crows.empty and not crows.loc[crows["strategy_label"] == "nonstep"].empty else 0
        insufficient = step_n < MIN_STRATEGY_N or nonstep_n < MIN_STRATEGY_N

        if insufficient:
            for ax in (ax_w, ax_h):
                ax.text(
                    0.5, 0.5,
                    f"insufficient n (step={step_n}, nonstep={nonstep_n})",
                    ha="center", va="center", fontsize=10, color="gray",
                    transform=ax.transAxes,
                )
                ax.set_title(f"Cluster {cid}{subtitle}", fontsize=11)
            ax_w.set_ylabel("Weight")
            ax_h.set_ylabel("Activation")
            continue

        # W grouped bar
        cluster_w = strategy_w_means[strategy_w_means["cluster_id"] == cid]
        x = np.arange(len(muscle_names))
        bar_width = 0.35
        for strategy, offset in [("step", -bar_width / 2), ("nonstep", bar_width / 2)]:
            sw = cluster_w[cluster_w["strategy_label"] == strategy]
            if sw.empty:
                continue
            sw = sw.copy()
            sw["muscle"] = pd.Categorical(sw["muscle"], categories=muscle_names, ordered=True)
            sw = sw.sort_values("muscle")
            vals = [float(sw.loc[sw["muscle"] == m, "W_mean"].iloc[0]) if not sw.loc[sw["muscle"] == m].empty else 0.0 for m in muscle_names]
            ax_w.bar(x + offset, vals, bar_width, color=STRATEGY_COLORS[strategy], label=strategy)
        ax_w.set_xticks(x)
        ax_w.set_xticklabels(muscle_names, rotation=45, ha="right")
        ax_w.set_ylabel("Weight")
        ax_w.set_title(f"Cluster {cid}: W{subtitle}", fontsize=11)
        ax_w.legend(fontsize=8)

        # H overlay lines
        cluster_h = strategy_h_means[strategy_h_means["cluster_id"] == cid]
        for strategy in ["step", "nonstep"]:
            sh = cluster_h[cluster_h["strategy_label"] == strategy].sort_values("frame_idx")
            if sh.empty:
                continue
            frames = sh["frame_idx"].to_numpy(dtype=float)
            x_pct = 100.0 * frames / frames.max() if len(frames) > 1 and frames.max() > 0 else frames
            ax_h.plot(x_pct, sh["h_mean"].to_numpy(dtype=float), color=STRATEGY_COLORS[strategy], linewidth=2.0, label=strategy)
        ax_h.set_xlim(0.0, 100.0)
        ax_h.set_ylabel("Activation")
        ax_h.set_xlabel("Normalized window (%)")
        ax_h.set_title(f"Cluster {cid}: H{subtitle}", fontsize=11)
        ax_h.legend(fontsize=8)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=_figure_dpi(cfg), format=_normalized_figure_format(cfg), bbox_inches="tight")
    plt.close(fig)


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


def save_cross_group_heatmap(
    pairwise_df: pd.DataFrame,
    threshold: float,
    cfg: dict,
    output_path: Path,
) -> None:
    """Render a step×nonstep cosine similarity heatmap with assignment highlights."""
    from matplotlib.patches import Rectangle

    plt = _pyplot()
    _configure_fonts()

    step_ids = sorted(pairwise_df["step_cluster_id"].unique())
    nonstep_ids = sorted(pairwise_df["nonstep_cluster_id"].unique())
    n_step = len(step_ids)
    n_nonstep = len(nonstep_ids)

    matrix = (
        pairwise_df.pivot(index="step_cluster_id", columns="nonstep_cluster_id", values="cosine_similarity")
        .reindex(index=step_ids, columns=nonstep_ids)
    )

    fig, ax = plt.subplots(figsize=(max(6, 1.2 * n_nonstep), max(4, 1.0 * n_step)))
    im = ax.imshow(matrix.to_numpy(dtype=float), vmin=0.0, vmax=1.0, cmap="Blues", aspect="auto")

    ax.set_xticks(range(n_nonstep))
    ax.set_xticklabels([str(c) for c in nonstep_ids])
    ax.set_yticks(range(n_step))
    ax.set_yticklabels([str(c) for c in step_ids])
    ax.set_xlabel("nonstep cluster id")
    ax.set_ylabel("step cluster id")
    ax.set_title(f"Cross-group W cosine similarity (step × nonstep)\nthreshold={threshold}")

    for row_idx, step_id in enumerate(step_ids):
        for col_idx, nonstep_id in enumerate(nonstep_ids):
            val = float(matrix.iat[row_idx, col_idx])
            cell_row = pairwise_df[
                (pairwise_df["step_cluster_id"] == step_id)
                & (pairwise_df["nonstep_cluster_id"] == nonstep_id)
            ]
            is_assigned = bool(cell_row["selected_in_assignment"].iloc[0]) if not cell_row.empty and "selected_in_assignment" in cell_row.columns else False
            passes = bool(cell_row["passes_threshold"].iloc[0]) if not cell_row.empty and "passes_threshold" in cell_row.columns else False

            label = f"{val:.2f}"
            if is_assigned and passes:
                label += "\n★"
            text_color = "white" if val > 0.6 else "black"
            ax.text(col_idx, row_idx, label, ha="center", va="center", fontsize=9, color=text_color)

            if is_assigned:
                rect = Rectangle(
                    (col_idx - 0.5, row_idx - 0.5), 1, 1,
                    linewidth=2.5, edgecolor="black", facecolor="none",
                )
                ax.add_patch(rect)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=_figure_dpi(cfg), format=_normalized_figure_format(cfg), bbox_inches="tight")
    plt.close(fig)


def save_cross_group_matched_w(
    step_df: pd.DataFrame,
    nonstep_df: pd.DataFrame,
    decision_df: pd.DataFrame,
    muscle_names: list[str],
    cfg: dict,
    output_path: Path,
) -> None:
    """Render matched W bar charts for same_synergy pairs and group_specific clusters."""
    import numpy as np

    plt = _pyplot()
    _configure_fonts()

    step_color = "#5C7CFA"
    nonstep_color = "#E64980"

    matched = decision_df[decision_df["final_label"] == "same_synergy"].copy()
    match_ids = sorted(matched["match_id"].dropna().unique())

    group_specific = decision_df[decision_df["final_label"] == "group_specific_synergy"].copy()

    panels: list[dict] = []
    for mid in match_ids:
        rows = matched[matched["match_id"] == mid]
        step_row = rows[rows["group_id"] == "global_step"]
        nonstep_row = rows[rows["group_id"] == "global_nonstep"]
        if step_row.empty or nonstep_row.empty:
            continue
        s_cid = int(step_row["cluster_id"].iloc[0])
        n_cid = int(nonstep_row["cluster_id"].iloc[0])
        cos_val = float(step_row["assigned_cosine_similarity"].iloc[0])
        panels.append({
            "title": f"{mid} (cos={cos_val:.2f})",
            "type": "matched",
            "step_cluster_id": s_cid,
            "nonstep_cluster_id": n_cid,
        })

    for _, row in group_specific.iterrows():
        gid = row["group_id"]
        cid = int(row["cluster_id"])
        group_label = "step" if gid == "global_step" else "nonstep"
        panels.append({
            "title": f"group_specific: {group_label} cluster {cid}",
            "type": "group_specific",
            "group_id": gid,
            "cluster_id": cid,
        })

    if not panels:
        return

    n_panels = len(panels)
    fig, axes = plt.subplots(n_panels, 1, figsize=(10, 3.0 * n_panels), squeeze=False)

    def _get_w_vector(df: pd.DataFrame, cluster_id: int, muscles: list[str]) -> list[float]:
        vec_cols = [c for c in df.columns if c not in ("group_id", "cluster_id")]
        row = df[df["cluster_id"] == cluster_id]
        if row.empty:
            return [0.0] * len(muscles)
        return [float(row[m].iloc[0]) if m in row.columns else 0.0 for m in muscles]

    x = np.arange(len(muscle_names))
    bar_width = 0.35

    for idx, panel in enumerate(panels):
        ax = axes[idx, 0]
        if panel["type"] == "matched":
            step_vals = _get_w_vector(step_df, panel["step_cluster_id"], muscle_names)
            nonstep_vals = _get_w_vector(nonstep_df, panel["nonstep_cluster_id"], muscle_names)
            ax.bar(x - bar_width / 2, step_vals, bar_width, color=step_color, label="step")
            ax.bar(x + bar_width / 2, nonstep_vals, bar_width, color=nonstep_color, label="nonstep")
            ax.legend(fontsize=8)
        else:
            gid = panel["group_id"]
            cid = panel["cluster_id"]
            source_df = step_df if gid == "global_step" else nonstep_df
            color = step_color if gid == "global_step" else nonstep_color
            vals = _get_w_vector(source_df, cid, muscle_names)
            ax.bar(x, vals, bar_width * 2, color=color)
        ax.set_xticks(x)
        ax.set_xticklabels(muscle_names, rotation=45, ha="right")
        ax.set_ylabel("W weight (L2-norm)")
        ax.set_title(panel["title"], fontsize=11)

    fig.suptitle("Cross-group matched W profiles", fontsize=13, fontweight="bold")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=_figure_dpi(cfg), format=_normalized_figure_format(cfg), bbox_inches="tight")
    plt.close(fig)


def save_cross_group_matched_h(
    rep_h_step: pd.DataFrame,
    rep_h_nonstep: pd.DataFrame,
    minimal_h: pd.DataFrame,
    labels: pd.DataFrame,
    decision_df: pd.DataFrame,
    cfg: dict,
    output_path: Path,
) -> None:
    """Render matched H time-series for same_synergy pairs and group_specific clusters."""
    import numpy as np

    plt = _pyplot()
    _configure_fonts()

    step_color = "#5C7CFA"
    nonstep_color = "#E64980"

    matched = decision_df[decision_df["final_label"] == "same_synergy"].copy()
    match_ids = sorted(matched["match_id"].dropna().unique())

    group_specific = decision_df[decision_df["final_label"] == "group_specific_synergy"].copy()

    panels: list[dict] = []
    for mid in match_ids:
        rows = matched[matched["match_id"] == mid]
        step_row = rows[rows["group_id"] == "global_step"]
        nonstep_row = rows[rows["group_id"] == "global_nonstep"]
        if step_row.empty or nonstep_row.empty:
            continue
        s_cid = int(step_row["cluster_id"].iloc[0])
        n_cid = int(nonstep_row["cluster_id"].iloc[0])
        cos_val = float(step_row["assigned_cosine_similarity"].iloc[0])
        panels.append({
            "title": f"{mid} (cos={cos_val:.2f})",
            "type": "matched",
            "step_cluster_id": s_cid,
            "nonstep_cluster_id": n_cid,
        })

    for _, row in group_specific.iterrows():
        gid = row["group_id"]
        cid = int(row["cluster_id"])
        group_label = "step" if gid == "global_step" else "nonstep"
        panels.append({
            "title": f"group_specific: {group_label} cluster {cid}",
            "type": "group_specific",
            "group_id": gid,
            "cluster_id": cid,
        })

    if not panels:
        return

    # Join labels with minimal_h to get per-trial H curves with cluster assignments
    trial_h = minimal_h.merge(
        labels[["group_id", "trial_id", "component_index", "cluster_id"]],
        on=["group_id", "trial_id", "component_index"],
        how="inner",
    )

    def _compute_trial_stats(
        df: pd.DataFrame, group_id: str, cluster_id: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (x_pct, mean, std) for all trials in a cluster."""
        subset = df[(df["group_id"] == group_id) & (df["cluster_id"] == cluster_id)]
        if subset.empty:
            return np.array([]), np.array([]), np.array([])
        pivot = subset.pivot_table(
            index=["trial_id", "component_index"],
            columns="frame_idx",
            values="h_value",
            aggfunc="first",
        )
        vals = pivot.to_numpy(dtype=float)
        frames = np.array(sorted(pivot.columns), dtype=float)
        x_pct = 100.0 * frames / frames.max() if len(frames) > 1 and frames.max() > 0 else frames
        mean = np.nanmean(vals, axis=0)
        std = np.nanstd(vals, axis=0)
        return x_pct, mean, std

    def _rep_h_curve(rep_df: pd.DataFrame, cluster_id: int) -> tuple[np.ndarray, np.ndarray]:
        subset = rep_df[rep_df["cluster_id"] == cluster_id].sort_values("frame_idx")
        if subset.empty:
            return np.array([]), np.array([])
        frames = subset["frame_idx"].to_numpy(dtype=float)
        x_pct = 100.0 * frames / frames.max() if len(frames) > 1 and frames.max() > 0 else frames
        return x_pct, subset["h_value"].to_numpy(dtype=float)

    n_panels = len(panels)
    fig, axes = plt.subplots(n_panels, 1, figsize=(10, 3.5 * n_panels), squeeze=False)

    for idx, panel in enumerate(panels):
        ax = axes[idx, 0]
        mean_y_collections: list[np.ndarray] = []
        if panel["type"] == "matched":
            # Step
            x_s, mean_s, std_s = _compute_trial_stats(trial_h, "global_step", panel["step_cluster_id"])
            if len(x_s) > 0:
                ax.fill_between(x_s, mean_s - std_s, mean_s + std_s, color=step_color, alpha=0.2)
            x_rep_s, y_rep_s = _rep_h_curve(rep_h_step, panel["step_cluster_id"])
            if len(x_rep_s) > 0:
                ax.plot(x_rep_s, y_rep_s, color=step_color, linewidth=2.5, label="step")
                mean_y_collections.append(y_rep_s)
            # Nonstep
            x_n, mean_n, std_n = _compute_trial_stats(trial_h, "global_nonstep", panel["nonstep_cluster_id"])
            if len(x_n) > 0:
                ax.fill_between(x_n, mean_n - std_n, mean_n + std_n, color=nonstep_color, alpha=0.2)
            x_rep_n, y_rep_n = _rep_h_curve(rep_h_nonstep, panel["nonstep_cluster_id"])
            if len(x_rep_n) > 0:
                ax.plot(x_rep_n, y_rep_n, color=nonstep_color, linewidth=2.5, label="nonstep")
                mean_y_collections.append(y_rep_n)
            ax.legend(fontsize=8, loc="upper right")
        else:
            gid = panel["group_id"]
            cid = panel["cluster_id"]
            color = step_color if gid == "global_step" else nonstep_color
            rep_df = rep_h_step if gid == "global_step" else rep_h_nonstep
            x_t, mean_t, std_t = _compute_trial_stats(trial_h, gid, cid)
            if len(x_t) > 0:
                ax.fill_between(x_t, mean_t - std_t, mean_t + std_t, color=color, alpha=0.2,
                                label=r"mean $\pm$ SD")
            x_rep, y_rep = _rep_h_curve(rep_df, cid)
            if len(x_rep) > 0:
                ax.plot(x_rep, y_rep, color=color, linewidth=2.5, label="mean")
                mean_y_collections.append(y_rep)
            if ax.get_legend_handles_labels()[1]:
                ax.legend(fontsize=8, loc="upper right")

        ax.set_xlim(0.0, 100.0)
        if mean_y_collections:
            all_y = np.concatenate(mean_y_collections)
            ymin, ymax = float(np.nanmin(all_y)), float(np.nanmax(all_y))
            margin = (ymax - ymin) * 0.05 if ymax > ymin else 0.1
            ax.set_ylim(ymin - margin, ymax + margin)
        ax.set_ylabel("Activation")
        ax.set_xlabel("Normalized window (%)")
        ax.set_title(panel["title"], fontsize=11)

    fig.suptitle("Cross-group matched H profiles", fontsize=13, fontweight="bold")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=_figure_dpi(cfg), format=_normalized_figure_format(cfg), bbox_inches="tight")
    plt.close(fig)


def save_cross_group_decision_summary(
    decision_df: pd.DataFrame,
    threshold: float,
    cfg: dict,
    output_path: Path,
) -> None:
    """Render a horizontal stacked bar chart summarizing cluster decisions."""
    plt = _pyplot()
    _configure_fonts()

    same_color = "#2F9E44"
    specific_color = "#868E96"

    groups = ["step", "nonstep"]
    same_counts = []
    specific_counts = []
    for g in groups:
        gid = f"global_{g}"
        subset = decision_df[decision_df["group_id"] == gid]
        same_counts.append(int((subset["final_label"] == "same_synergy").sum()))
        specific_counts.append(int((subset["final_label"] == "group_specific_synergy").sum()))

    fig, ax = plt.subplots(figsize=(8, 3))
    y_pos = range(len(groups))
    ax.barh(y_pos, same_counts, color=same_color, label="same_synergy")
    ax.barh(y_pos, specific_counts, left=same_counts, color=specific_color, label="group_specific_synergy")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(groups)
    ax.set_xlabel("Number of clusters")
    ax.set_title(f"Cross-group cluster decision summary (threshold={threshold})")
    ax.legend(loc="lower right", fontsize=9)

    for i, (s, g) in enumerate(zip(same_counts, specific_counts)):
        total = s + g
        if s > 0:
            ax.text(s / 2, i, str(s), ha="center", va="center", fontsize=10, fontweight="bold", color="white")
        if g > 0:
            ax.text(s + g / 2, i, str(g), ha="center", va="center", fontsize=10, fontweight="bold", color="white")

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
