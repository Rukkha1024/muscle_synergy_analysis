"""Rerender EMG figure artifacts from saved run parquet outputs.

This module validates one run directory, reloads the saved
parquet figure sources with Polars, and rebuilds the full
figures tree without rerunning NMF or clustering.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
from typing import Any

import pandas as pd
import polars as pl

from .cross_group_similarity import build_cluster_w_matrix
from .figures import (
    _build_cluster_coverage,
    figure_suffix,
    save_cluster_strategy_composition,
    save_cross_group_decision_summary,
    save_cross_group_heatmap,
    save_cross_group_matched_h,
    save_cross_group_matched_w,
    save_group_cluster_figure,
    save_trial_composition_figure,
    save_trial_nmf_figure,
    save_within_cluster_strategy_overlay,
)
from .single_parquet import (
    POOLED_CLUSTER_STRATEGY_H_MEANS_KEY,
    POOLED_CLUSTER_STRATEGY_SUMMARY_KEY,
    POOLED_CLUSTER_STRATEGY_W_MEANS_KEY,
    SOURCE_TRIAL_WINDOWS_FRAME_KEY,
    load_single_parquet_bundle,
    resolve_single_parquet_path,
)


_CORE_BUNDLE_KEYS = {
    "rep_w": "rep_W",
    "rep_h_long": "rep_H_long",
    "minimal_w": "minimal_W",
    "minimal_h_long": "minimal_H_long",
    "labels": "labels",
    "trial_windows": "trial_windows",
}
_CROSS_GROUP_BUNDLE_KEYS = {
    "cross_group_pairwise": "cross_group_pairwise",
    "cross_group_decision": "cross_group_decision",
}


def _cross_group_similarity_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    raw_cfg = cfg.get("cross_group_w_similarity", {})
    return {
        "enabled": bool(raw_cfg.get("enabled", True)),
        "threshold": float(raw_cfg.get("threshold", 0.8)),
        "output_figures": bool(raw_cfg.get("output_figures", True)),
    }


def _requires_cross_group_artifacts(cfg: dict[str, Any]) -> bool:
    cross_group_cfg = _cross_group_similarity_cfg(cfg)
    return bool(cross_group_cfg["enabled"] and cross_group_cfg["output_figures"])


def _discover_group_ids(artifacts: dict[str, object]) -> list[str]:
    discovered: list[str] = []
    for key in ("labels", "trial_windows", "rep_w"):
        frame = artifacts.get(key)
        if frame is None or "group_id" not in frame.columns:
            continue
        for group_id in frame.get_column("group_id").drop_nulls().cast(pl.Utf8).unique(maintain_order=True).to_list():
            normalized = str(group_id).strip()
            if normalized and normalized not in discovered:
                discovered.append(normalized)
    return discovered


def _can_render_cross_group(bundle: dict[str, object], cfg: dict[str, Any], group_ids: list[str]) -> bool:
    if not _requires_cross_group_artifacts(cfg):
        return False
    if not {"global_step", "global_nonstep"}.issubset(set(group_ids)):
        return False
    missing = [
        bundle_key
        for bundle_key in _CROSS_GROUP_BUNDLE_KEYS.values()
        if bundle.get(bundle_key) is None or bundle[bundle_key].empty
    ]
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise FileNotFoundError(
            f"Missing figure source artifact(s) in single parquet bundle: {missing_text}"
        )
    return True


def _format_filename_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text.replace("/", "-").replace("\\", "-").replace(" ", "_")


def _trial_figure_name(trial_row: dict[str, Any], figure_ext: str) -> str:
    step_class = str(trial_row.get("analysis_step_class", "unknown")).strip().lower() or "unknown"
    subject = _format_filename_value(trial_row["subject"])
    velocity = _format_filename_value(trial_row["velocity"])
    trial_num = _format_filename_value(trial_row["trial_num"])
    return f"{subject}_v{velocity}_T{trial_num}_{step_class}_nmf{figure_ext}"


def _group_trial_rows(trial_windows: pl.DataFrame) -> list[dict[str, Any]]:
    candidate_columns = [
        column_name
        for column_name in (
            "group_id",
            "subject",
            "velocity",
            "trial_num",
            "trial_id",
            "analysis_step_class",
        )
        if column_name in trial_windows.columns
    ]
    rows = (
        trial_windows.select(candidate_columns)
        .unique(subset=["trial_id"], keep="first")
        .sort(["group_id", "subject", "velocity", "trial_num"])
        .iter_rows(named=True)
    )
    return list(rows)


def _replace_figure_tree(tmp_dir: Path, figure_dir: Path) -> None:
    backup_dir = figure_dir.parent / "figures.__bak__"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    try:
        if figure_dir.exists():
            figure_dir.replace(backup_dir)
        tmp_dir.replace(figure_dir)
    except Exception:
        if figure_dir.exists():
            shutil.rmtree(figure_dir, ignore_errors=True)
        if backup_dir.exists():
            backup_dir.replace(figure_dir)
        raise
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)


def _cleanup_staging_dirs(run_dir: Path) -> None:
    for dirname in ("figures.__tmp__", "figures.__bak__"):
        path = run_dir / dirname
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def _materialized_paths(
    rendered_paths: dict[str, list[str]],
    tmp_dir: Path,
    figure_dir: Path,
) -> dict[str, list[str]]:
    materialized: dict[str, list[str]] = {}
    for key, paths in rendered_paths.items():
        materialized[key] = [
            str(figure_dir / Path(path).relative_to(tmp_dir))
            for path in paths
        ]
    return materialized


def required_figure_artifacts(
    bundle: dict[str, Any],
    *,
    include_cross_group: bool = True,
) -> dict[str, str]:
    bundle_keys = dict(_CORE_BUNDLE_KEYS)
    if include_cross_group:
        bundle_keys.update(_CROSS_GROUP_BUNDLE_KEYS)

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for key, bundle_key in bundle_keys.items():
        frame = bundle.get(bundle_key)
        if frame is None or frame.empty:
            missing.append(bundle_key)
            continue
        resolved[key] = bundle_key

    if missing:
        missing_text = ", ".join(sorted(missing))
        raise FileNotFoundError(
            f"Missing figure source artifact(s) in single parquet bundle: {missing_text}"
        )
    return resolved


def load_figure_artifacts(
    source_parquet_path: Path,
    *,
    include_cross_group: bool = True,
) -> dict[str, object]:
    bundle = load_single_parquet_bundle(source_parquet_path)
    bundle_keys = required_figure_artifacts(bundle, include_cross_group=include_cross_group)
    frames = {
        key: pl.from_pandas(bundle[bundle_key])
        for key, bundle_key in bundle_keys.items()
    }
    return {
        "source_parquet_path": str(source_parquet_path),
        **frames,
    }


def _mode_name_for_run_dir(run_dir: Path) -> str:
    name = run_dir.name.strip().lower()
    if name not in {"trialwise", "concatenated"}:
        raise ValueError(f"Expected a mode output directory, got: {run_dir}")
    return name


def render_figures_from_run_dir(
    run_dir: Path,
    cfg: dict[str, Any],
    *,
    source_parquet_path: Path | None = None,
) -> dict[str, list[str]]:
    run_dir = Path(run_dir).resolve()
    resolved_source_path = (
        Path(source_parquet_path).resolve()
        if source_parquet_path is not None
        else resolve_single_parquet_path(cfg, _mode_name_for_run_dir(run_dir))
    )
    bundle = load_single_parquet_bundle(resolved_source_path)
    artifacts = load_figure_artifacts(resolved_source_path, include_cross_group=False)
    group_ids = _discover_group_ids(artifacts)
    if not group_ids:
        raise ValueError(f"Could not discover any group_id values from saved artifacts in {resolved_source_path}.")
    include_cross_group = _can_render_cross_group(bundle, cfg, group_ids)
    if include_cross_group:
        artifacts = load_figure_artifacts(resolved_source_path, include_cross_group=True)

    muscle_names = list(cfg["muscles"]["names"])
    figure_ext = figure_suffix(cfg)
    figure_dir = run_dir / "figures"
    tmp_dir = run_dir / "figures.__tmp__"
    _cleanup_staging_dirs(run_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    strategy_summary_frame = bundle.get(POOLED_CLUSTER_STRATEGY_SUMMARY_KEY, None)
    strategy_summary = None if strategy_summary_frame is None or strategy_summary_frame.empty else strategy_summary_frame

    rendered_paths = {
        "group_figure_paths": [],
        "trial_figure_paths": [],
        "cross_group_figure_paths": [],
        "pooled_narrative_figure_paths": [],
    }
    try:
        # Figure 01: Trial composition (concatenated mode only)
        source_trial_windows_frame = bundle.get(SOURCE_TRIAL_WINDOWS_FRAME_KEY, None)
        if source_trial_windows_frame is not None and not source_trial_windows_frame.empty:
            pooled_tw = artifacts["trial_windows"].filter(
                pl.col("group_id") == "pooled_step_nonstep"
            ).to_pandas() if "pooled_step_nonstep" in group_ids else pd.DataFrame()
            if not pooled_tw.empty:
                fig01_path = tmp_dir / f"01_trial_composition{figure_ext}"
                save_trial_composition_figure(
                    trial_windows=pooled_tw,
                    source_trial_windows=source_trial_windows_frame,
                    cfg=cfg,
                    output_path=fig01_path,
                )
                rendered_paths["pooled_narrative_figure_paths"].append(str(fig01_path))

        for group_id in group_ids:
            output_path = tmp_dir / f"{group_id}_clusters{figure_ext}"
            group_strategy = (
                strategy_summary
                if strategy_summary is not None and group_id == "pooled_step_nonstep"
                else None
            )
            save_group_cluster_figure(
                group_id=group_id,
                rep_w=artifacts["rep_w"].filter(pl.col("group_id") == group_id).to_pandas(),
                rep_h=artifacts["rep_h_long"].filter(pl.col("group_id") == group_id).to_pandas(),
                muscle_names=muscle_names,
                cfg=cfg,
                output_path=output_path,
                cluster_labels=artifacts["labels"].filter(pl.col("group_id") == group_id).to_pandas(),
                trial_metadata=artifacts["trial_windows"].filter(pl.col("group_id") == group_id).to_pandas(),
                strategy_summary=group_strategy,
            )
            rendered_paths["group_figure_paths"].append(str(output_path))

            # Figure 04 alias: copy pooled figure with numbered name
            if group_id == "pooled_step_nonstep":
                fig04_path = tmp_dir / f"04_pooled_cluster_representatives{figure_ext}"
                shutil.copy2(output_path, fig04_path)
                rendered_paths["pooled_narrative_figure_paths"].append(str(fig04_path))

        # Figure 03: Cluster strategy composition
        if strategy_summary is not None and "pooled_step_nonstep" in group_ids:
            fig03_path = tmp_dir / f"03_cluster_strategy_composition{figure_ext}"
            save_cluster_strategy_composition(
                strategy_summary=strategy_summary,
                cfg=cfg,
                output_path=fig03_path,
            )
            rendered_paths["pooled_narrative_figure_paths"].append(str(fig03_path))

        # Figure 05: Within-cluster strategy overlay
        strategy_w_means = bundle.get(POOLED_CLUSTER_STRATEGY_W_MEANS_KEY, pd.DataFrame())
        strategy_h_means = bundle.get(POOLED_CLUSTER_STRATEGY_H_MEANS_KEY, pd.DataFrame())
        # Recompute h_std from minimal data if missing
        if not strategy_h_means.empty and "h_std" not in strategy_h_means.columns:
            _labels = bundle.get("labels", pd.DataFrame())
            _min_h = bundle.get("minimal_H_long", pd.DataFrame())
            if not _labels.empty and not _min_h.empty:
                _pl = _labels.loc[_labels["group_id"].astype(str) == "pooled_step_nonstep"].copy()
                if not _pl.empty:
                    _pl["strategy_label"] = _pl["analysis_step_class"].astype(str).str.strip().str.lower()
                    _pl = _pl.loc[_pl["strategy_label"].isin(["step", "nonstep"])]
                    _mk = ["group_id", "trial_id", "component_index"]
                    _mg = _min_h.merge(_pl[_mk + ["cluster_id", "strategy_label"]], on=_mk, how="inner")
                    if not _mg.empty:
                        strategy_h_means = (
                            _mg.groupby(["group_id", "cluster_id", "strategy_label", "frame_idx"], dropna=False)["h_value"]
                            .agg(["mean", "std"]).reset_index()
                        )
                        strategy_h_means.columns = [*strategy_h_means.columns[:-2], "h_mean", "h_std"]
                        strategy_h_means["h_std"] = strategy_h_means["h_std"].fillna(0.0)
        if (
            strategy_summary is not None
            and "pooled_step_nonstep" in group_ids
            and not strategy_w_means.empty
            and not strategy_h_means.empty
        ):
            fig05_path = tmp_dir / f"05_within_cluster_strategy_overlay{figure_ext}"
            _pooled_labels = artifacts["labels"].filter(pl.col("group_id") == "pooled_step_nonstep").to_pandas()
            _pooled_tw = artifacts["trial_windows"].filter(pl.col("group_id") == "pooled_step_nonstep").to_pandas()
            if not _pooled_labels.empty and not _pooled_tw.empty:
                _fig05_total_trials, _fig05_total_subjects, _fig05_coverage = _build_cluster_coverage(_pooled_labels, _pooled_tw)
            else:
                _fig05_total_trials, _fig05_total_subjects, _fig05_coverage = None, None, None
            save_within_cluster_strategy_overlay(
                strategy_w_means=strategy_w_means,
                strategy_h_means=strategy_h_means,
                strategy_summary=strategy_summary,
                muscle_names=muscle_names,
                cfg=cfg,
                output_path=fig05_path,
                total_trials=_fig05_total_trials,
                total_subjects=_fig05_total_subjects,
                coverage=_fig05_coverage,
            )
            rendered_paths["pooled_narrative_figure_paths"].append(str(fig05_path))

        trial_figure_dir = tmp_dir / "nmf_trials"
        for trial_row in _group_trial_rows(artifacts["trial_windows"]):
            output_path = trial_figure_dir / _trial_figure_name(trial_row, figure_ext)
            group_id = str(trial_row["group_id"])
            trial_id = str(trial_row["trial_id"])
            trial_w = (
                artifacts["minimal_w"]
                .filter((pl.col("group_id") == group_id) & (pl.col("trial_id") == trial_id))
                .rename({"component_index": "cluster_id"})
                .to_pandas()
            )
            trial_h = (
                artifacts["minimal_h_long"]
                .filter((pl.col("group_id") == group_id) & (pl.col("trial_id") == trial_id))
                .rename({"component_index": "cluster_id"})
                .to_pandas()
            )
            save_trial_nmf_figure(
                subject=str(trial_row["subject"]),
                velocity=trial_row["velocity"],
                trial_num=trial_row["trial_num"],
                step_class=str(trial_row.get("analysis_step_class", "unknown")).strip().lower() or "unknown",
                trial_w=trial_w,
                trial_h=trial_h,
                muscle_names=muscle_names,
                cfg=cfg,
                output_path=output_path,
            )
            rendered_paths["trial_figure_paths"].append(str(output_path))

        if include_cross_group:
            cross_group_cfg = _cross_group_similarity_cfg(cfg)
            pairwise_df = artifacts["cross_group_pairwise"].to_pandas()
            decision_df = artifacts["cross_group_decision"].to_pandas()
            step_df, nonstep_df = build_cluster_w_matrix(artifacts["rep_w"], muscle_names)

            heatmap_path = tmp_dir / f"cross_group_cosine_heatmap{figure_ext}"
            save_cross_group_heatmap(
                pairwise_df=pairwise_df,
                threshold=cross_group_cfg["threshold"],
                cfg=cfg,
                output_path=heatmap_path,
            )
            rendered_paths["cross_group_figure_paths"].append(str(heatmap_path))

            matched_w_path = tmp_dir / f"cross_group_matched_w{figure_ext}"
            save_cross_group_matched_w(
                step_df=step_df,
                nonstep_df=nonstep_df,
                decision_df=decision_df,
                muscle_names=muscle_names,
                cfg=cfg,
                output_path=matched_w_path,
            )
            rendered_paths["cross_group_figure_paths"].append(str(matched_w_path))

            matched_h_path = tmp_dir / f"cross_group_matched_h{figure_ext}"
            save_cross_group_matched_h(
                rep_h_step=artifacts["rep_h_long"].filter(pl.col("group_id") == "global_step").to_pandas(),
                rep_h_nonstep=artifacts["rep_h_long"].filter(pl.col("group_id") == "global_nonstep").to_pandas(),
                minimal_h=artifacts["minimal_h_long"].to_pandas(),
                labels=artifacts["labels"].to_pandas(),
                decision_df=decision_df,
                cfg=cfg,
                output_path=matched_h_path,
            )
            rendered_paths["cross_group_figure_paths"].append(str(matched_h_path))

            decision_summary_path = tmp_dir / f"cross_group_decision_summary{figure_ext}"
            save_cross_group_decision_summary(
                decision_df=decision_df,
                threshold=cross_group_cfg["threshold"],
                cfg=cfg,
                output_path=decision_summary_path,
            )
            rendered_paths["cross_group_figure_paths"].append(str(decision_summary_path))

        materialized_paths = _materialized_paths(rendered_paths, tmp_dir, figure_dir)
        _replace_figure_tree(tmp_dir, figure_dir)
    except Exception:
        _cleanup_staging_dirs(run_dir)
        raise
    logging.info(
        "Rendered %s group figure(s), %s trial figure(s), %s cross-group figure(s), and %s pooled narrative figure(s) into %s",
        len(rendered_paths["group_figure_paths"]),
        len(rendered_paths["trial_figure_paths"]),
        len(rendered_paths["cross_group_figure_paths"]),
        len(rendered_paths["pooled_narrative_figure_paths"]),
        figure_dir,
    )
    return materialized_paths
