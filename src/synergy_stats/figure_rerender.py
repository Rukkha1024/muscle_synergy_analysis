"""Rerender EMG figure artifacts from saved run CSV outputs.

This module validates one run directory, reloads the saved
CSV figure sources with Polars, and rebuilds the full
figures tree without rerunning NMF or clustering.
"""

from __future__ import annotations

from io import StringIO
import logging
from pathlib import Path
import shutil
from typing import Any

import polars as pl

from .cross_group_similarity import build_cluster_w_matrix
from .figures import (
    figure_suffix,
    save_cross_group_decision_summary,
    save_cross_group_heatmap,
    save_cross_group_matched_h,
    save_cross_group_matched_w,
    save_group_cluster_figure,
    save_trial_nmf_figure,
)


_CORE_ARTIFACT_FILENAMES = {
    "rep_w": "all_representative_W_posthoc.csv",
    "rep_h_long": "all_representative_H_posthoc_long.csv",
    "minimal_w": "all_minimal_units_W.csv",
    "minimal_h_long": "all_minimal_units_H_long.csv",
    "labels": "all_cluster_labels.csv",
    "trial_windows": "all_trial_window_metadata.csv",
}
_CROSS_GROUP_ARTIFACT_FILENAMES = {
    "cross_group_pairwise": "cross_group_w_pairwise_cosine.csv",
    "cross_group_decision": "cross_group_w_cluster_decision.csv",
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


def _read_csv_utf8_sig(path: Path) -> pl.DataFrame:
    text = path.read_text(encoding="utf-8-sig")
    return pl.read_csv(StringIO(text))


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
    run_dir: Path,
    *,
    include_cross_group: bool = True,
) -> dict[str, Path]:
    artifact_names = dict(_CORE_ARTIFACT_FILENAMES)
    if include_cross_group:
        artifact_names.update(_CROSS_GROUP_ARTIFACT_FILENAMES)

    resolved: dict[str, Path] = {}
    missing: list[str] = []
    for key, filename in artifact_names.items():
        path = run_dir / filename
        if not path.exists():
            missing.append(filename)
            continue
        resolved[key] = path

    if missing:
        missing_text = ", ".join(sorted(missing))
        raise FileNotFoundError(
            f"Missing figure source artifact(s) in {run_dir}: {missing_text}"
        )
    return resolved


def load_figure_artifacts(
    run_dir: Path,
    *,
    include_cross_group: bool = True,
) -> dict[str, object]:
    artifact_paths = required_figure_artifacts(run_dir, include_cross_group=include_cross_group)
    frames = {key: _read_csv_utf8_sig(path) for key, path in artifact_paths.items()}
    return {
        "paths": artifact_paths,
        **frames,
    }


def render_figures_from_run_dir(run_dir: Path, cfg: dict[str, Any]) -> dict[str, list[str]]:
    run_dir = Path(run_dir).resolve()
    include_cross_group = _requires_cross_group_artifacts(cfg)
    artifacts = load_figure_artifacts(run_dir, include_cross_group=include_cross_group)

    muscle_names = list(cfg["muscles"]["names"])
    figure_ext = figure_suffix(cfg)
    figure_dir = run_dir / "figures"
    tmp_dir = run_dir / "figures.__tmp__"
    _cleanup_staging_dirs(run_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    rendered_paths = {
        "group_figure_paths": [],
        "trial_figure_paths": [],
        "cross_group_figure_paths": [],
    }
    try:
        for group_id in ("global_step", "global_nonstep"):
            output_path = tmp_dir / f"{group_id}_clusters{figure_ext}"
            save_group_cluster_figure(
                group_id=group_id,
                rep_w=artifacts["rep_w"].filter(pl.col("group_id") == group_id).to_pandas(),
                rep_h=artifacts["rep_h_long"].filter(pl.col("group_id") == group_id).to_pandas(),
                muscle_names=muscle_names,
                cfg=cfg,
                output_path=output_path,
                cluster_labels=artifacts["labels"].filter(pl.col("group_id") == group_id).to_pandas(),
                trial_metadata=artifacts["trial_windows"].filter(pl.col("group_id") == group_id).to_pandas(),
            )
            rendered_paths["group_figure_paths"].append(str(output_path))

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
        "Rendered %s group figure(s), %s trial figure(s), and %s cross-group figure(s) into %s",
        len(rendered_paths["group_figure_paths"]),
        len(rendered_paths["trial_figure_paths"]),
        len(rendered_paths["cross_group_figure_paths"]),
        figure_dir,
    )
    return materialized_paths
