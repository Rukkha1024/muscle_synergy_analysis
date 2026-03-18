"""Export mode-specific and combined EMG synergy artifacts.

This module writes full artifact bundles under each
analysis mode directory, then builds root-level combined
CSV, parquet, and workbook outputs with mode provenance.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
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
from .methods import primary_analysis_mode


AGGREGATE_NAME_MAP = {
    "metadata": "all_clustering_metadata.csv",
    "labels": "all_cluster_labels.csv",
    "rep_W": "all_representative_W_posthoc.csv",
    "rep_H_long": "all_representative_H_posthoc_long.csv",
    "minimal_W": "all_minimal_units_W.csv",
    "minimal_H_long": "all_minimal_units_H_long.csv",
    "trial_windows": "all_trial_window_metadata.csv",
}

CONCATENATED_SOURCE_TRIAL_WINDOWS_FILENAME = "all_concatenated_source_trial_windows.csv"
POOLED_CLUSTER_STRATEGY_SUMMARY_FILENAME = "pooled_cluster_strategy_summary.csv"


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


def _ensure_mode_context(context: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, dict[str, Any]]]]:
    analysis_modes = list(context.get("analysis_modes") or [])
    analysis_mode_cluster_group_results = context.get("analysis_mode_cluster_group_results")
    if analysis_modes and analysis_mode_cluster_group_results:
        return analysis_modes, analysis_mode_cluster_group_results

    feature_rows = context.get("feature_rows", [])
    cluster_group_results = context.get("cluster_group_results", {})
    mode = primary_analysis_mode(analysis_modes or ["trialwise"])
    context["analysis_modes"] = [mode]
    context["analysis_mode_feature_rows"] = {mode: feature_rows}
    context["analysis_mode_cluster_group_results"] = {mode: cluster_group_results}
    return context["analysis_modes"], context["analysis_mode_cluster_group_results"]


def _concat_frames_union(frames: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [frame for frame in frames if frame is not None and not frame.empty]
    if not non_empty:
        return pd.DataFrame()
    return pd.concat(non_empty, ignore_index=True, sort=False)


def _with_mode_column(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame()
    if frame.empty:
        if "aggregation_mode" not in frame.columns:
            frame = frame.copy()
            frame["aggregation_mode"] = pd.Series(dtype="object")
        return frame
    updated = frame.copy()
    updated["aggregation_mode"] = mode
    return updated


def _prepare_parquet_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    prepared = frame.copy()
    for column_name in ("aggregation_mode", "group_id", "subject", "trial_num", "analysis_unit_id", "source_trial_nums_csv"):
        if column_name in prepared.columns:
            prepared[column_name] = prepared[column_name].astype(str)
    return prepared


def _present_group_ids(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "group_id" not in frame.columns:
        return []
    group_ids = (
        frame["group_id"]
        .dropna()
        .astype(str)
        .map(str.strip)
    )
    return [group_id for group_id in group_ids.drop_duplicates().tolist() if group_id]


def _can_build_cross_group_artifacts(aggregate_frames: dict[str, pd.DataFrame]) -> bool:
    present_groups = set(_present_group_ids(aggregate_frames.get("rep_W", pd.DataFrame())))
    return {"global_step", "global_nonstep"}.issubset(present_groups)


def _build_pooled_cluster_strategy_summary(labels_frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"group_id", "cluster_id", "analysis_step_class"}
    if labels_frame.empty or not required_columns.issubset(set(labels_frame.columns)):
        return pd.DataFrame()

    pooled_labels = labels_frame.loc[labels_frame["group_id"].astype(str) == "pooled_step_nonstep"].copy()
    if pooled_labels.empty:
        return pd.DataFrame()

    pooled_labels["strategy_label"] = (
        pooled_labels["analysis_step_class"]
        .astype(str)
        .str.strip()
        .str.lower()
    )
    pooled_labels = pooled_labels.loc[pooled_labels["strategy_label"].isin(["step", "nonstep"])].copy()
    if pooled_labels.empty:
        return pd.DataFrame()

    summary = (
        pooled_labels.groupby(["group_id", "cluster_id", "strategy_label"], dropna=False)
        .size()
        .rename("n_rows")
        .reset_index()
    )
    cluster_totals = (
        pooled_labels.groupby(["group_id", "cluster_id"], dropna=False)
        .size()
        .rename("cluster_total_rows")
        .reset_index()
    )
    strategy_index = pd.MultiIndex.from_product(
        [
            sorted(pooled_labels["group_id"].drop_duplicates().tolist()),
            sorted(pooled_labels["cluster_id"].drop_duplicates().tolist()),
            ["step", "nonstep"],
        ],
        names=["group_id", "cluster_id", "strategy_label"],
    )
    summary = (
        summary.set_index(["group_id", "cluster_id", "strategy_label"])
        .reindex(strategy_index, fill_value=0)
        .reset_index()
    )
    summary = summary.merge(cluster_totals, on=["group_id", "cluster_id"], how="left")
    summary["fraction_within_cluster"] = (
        summary["n_rows"] / summary["cluster_total_rows"].where(summary["cluster_total_rows"].ne(0), pd.NA)
    )
    summary["fraction_within_cluster"] = summary["fraction_within_cluster"].fillna(0.0)
    return summary[
        [
            "group_id",
            "cluster_id",
            "strategy_label",
            "n_rows",
            "cluster_total_rows",
            "fraction_within_cluster",
        ]
    ]


def _build_cross_group_artifacts(
    aggregate_frames: dict[str, pd.DataFrame],
    muscle_names: list[str],
    cfg: dict[str, Any],
    output_dir: Path,
) -> dict[str, pd.DataFrame]:
    cross_group_cfg = _cross_group_similarity_cfg(cfg)
    if not cross_group_cfg["enabled"]:
        return {}
    if not _can_build_cross_group_artifacts(aggregate_frames):
        return {}
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
        _write_csv(pairwise_output_df, output_dir / "cross_group_w_pairwise_cosine.csv")
    if cross_group_cfg["output_cluster_decision_csv"]:
        _write_csv(decision_df, output_dir / "cross_group_w_cluster_decision.csv")
    return cross_group_artifacts


def _write_mode_exports(
    *,
    mode: str,
    cluster_group_results: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
    root_output_dir: Path,
    mode_output_dir: Path,
    final_alias_path: Path,
) -> dict[str, Any]:
    runtime_cfg = cfg["runtime"]
    muscle_names = list(cfg["muscles"]["names"])
    target_windows = int(
        cfg.get("synergy_clustering", {})
        .get("representative", {})
        .get("h_output_interpolation", {})
        .get("target_windows", 100)
    )
    mode_output_dir.mkdir(parents=True, exist_ok=True)
    figure_ext = figure_suffix(cfg)

    all_frames = {key: [] for key in AGGREGATE_NAME_MAP}
    source_trial_window_frames: list[pd.DataFrame] = []
    group_summaries = []
    for group_id, payload in cluster_group_results.items():
        exports = build_group_exports(
            group_id=group_id,
            feature_rows=payload["feature_rows"],
            cluster_result=payload["cluster_result"],
            muscle_names=muscle_names,
            target_windows=target_windows,
        )
        for key in all_frames:
            frame = exports.get(key, pd.DataFrame())
            if not frame.empty:
                all_frames[key].append(_with_mode_column(frame, mode))
        source_trial_window_frame = exports.get("source_trial_windows", pd.DataFrame())
        if not source_trial_window_frame.empty:
            source_trial_window_frames.append(_with_mode_column(source_trial_window_frame, mode))
        group_summaries.append(
            {
                "aggregation_mode": mode,
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
                "group_figure_path": str(
                    (mode_output_dir / "figures" / f"{group_id}_clusters{figure_ext}").relative_to(root_output_dir)
                ),
            }
        )

    summary_df = summarize_group_results(group_summaries)
    _write_csv(summary_df, mode_output_dir / "final_summary.csv")

    aggregate_frames: dict[str, pd.DataFrame] = {}
    final_parquet_frame = pd.DataFrame()
    source_trial_windows_frame = pd.DataFrame()
    for key, filename in AGGREGATE_NAME_MAP.items():
        frame = _concat_frames_union(all_frames[key])
        aggregate_frames[key] = frame
        _write_csv(frame, mode_output_dir / filename)
        if key == "minimal_W":
            final_parquet_frame = frame
    source_trial_windows_frame = _concat_frames_union(source_trial_window_frames)
    if not source_trial_windows_frame.empty:
        _write_csv(
            source_trial_windows_frame,
            mode_output_dir / CONCATENATED_SOURCE_TRIAL_WINDOWS_FILENAME,
        )
    pooled_strategy_summary_frame = _build_pooled_cluster_strategy_summary(aggregate_frames["labels"])
    if not pooled_strategy_summary_frame.empty:
        pooled_strategy_summary_frame = _with_mode_column(pooled_strategy_summary_frame, mode)
        _write_csv(
            pooled_strategy_summary_frame,
            mode_output_dir / POOLED_CLUSTER_STRATEGY_SUMMARY_FILENAME,
        )

    mode_final_parquet_path = mode_output_dir / "final.parquet"
    mode_final_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_parquet_frame(final_parquet_frame).to_parquet(mode_final_parquet_path, index=False)
    final_alias_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_parquet_frame(final_parquet_frame).to_parquet(final_alias_path, index=False)

    cross_group_cfg = _cross_group_similarity_cfg(cfg)
    cross_group_artifacts = _build_cross_group_artifacts(
        aggregate_frames,
        muscle_names,
        cfg,
        mode_output_dir,
    )
    workbook_path = write_clustering_audit_workbook(
        mode_output_dir / "clustering_audit.xlsx",
        cluster_group_results,
    )
    workbook_validation = validate_clustering_audit_workbook(workbook_path)
    interpretation_workbook_path = write_results_interpretation_workbook(
        mode_output_dir / "results_interpretation.xlsx",
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
    rendered_figures = render_figures_from_run_dir(mode_output_dir, cfg)
    logging.info("Saved %s mode artifacts to %s", mode, mode_output_dir)

    return {
        "mode": mode,
        "output_dir": mode_output_dir,
        "summary": summary_df,
        "aggregate_frames": aggregate_frames,
        "cross_group_artifacts": cross_group_artifacts,
        "final_parquet_frame": final_parquet_frame,
        "final_parquet_path": mode_final_parquet_path,
        "final_alias_path": final_alias_path,
        "source_trial_windows_frame": source_trial_windows_frame,
        "pooled_strategy_summary_frame": pooled_strategy_summary_frame,
        "clustering_audit_workbook_path": workbook_path,
        "clustering_audit_workbook_validation": workbook_validation,
        "results_interpretation_workbook_path": interpretation_workbook_path,
        "results_interpretation_workbook_validation": interpretation_workbook_validation,
        "rendered_figures": rendered_figures,
    }


def _combined_audit_payloads(
    analysis_mode_cluster_group_results: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for mode, group_results in analysis_mode_cluster_group_results.items():
        for group_id, payload in group_results.items():
            combined[f"{mode}::{group_id}"] = {
                **payload,
                "group_id": group_id,
                "aggregation_mode": mode,
            }
    return combined


def _write_analysis_methods_manifest(
    *,
    cfg: dict[str, Any],
    analysis_modes: list[str],
    mode_exports: dict[str, dict[str, Any]],
    combined_final_parquet_path: Path,
) -> Path:
    manifest_path = Path(
        cfg["runtime"].get("analysis_methods_manifest_path")
        or (Path(cfg["runtime"]["output_dir"]) / "analysis_methods_manifest.json")
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "selected_mode": cfg.get("synergy_analysis", {}).get("mode", "both"),
        "analysis_modes": analysis_modes,
        "combined_final_parquet_path": str(combined_final_parquet_path),
        "final_parquet_path": cfg["runtime"]["final_parquet_path"],
        "final_parquet_alias_paths": cfg["runtime"].get("final_parquet_alias_paths", {}),
        "modes": {
            mode: {
                "output_dir": str(exports["output_dir"]),
                "final_parquet_path": str(exports["final_parquet_path"]),
                "final_alias_path": str(exports["final_alias_path"]),
                "concatenated_source_trial_windows_path": (
                    str(exports["output_dir"] / CONCATENATED_SOURCE_TRIAL_WINDOWS_FILENAME)
                    if not exports.get("source_trial_windows_frame", pd.DataFrame()).empty
                    else ""
                ),
                "clustering_audit_workbook_path": str(exports["clustering_audit_workbook_path"]),
                "results_interpretation_workbook_path": str(exports["results_interpretation_workbook_path"]),
            }
            for mode, exports in mode_exports.items()
        },
    }
    with manifest_path.open("w", encoding="utf-8-sig") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return manifest_path


def export_results(context: dict[str, Any]) -> dict[str, Any]:
    cfg = context["config"]
    runtime_cfg = cfg["runtime"]
    root_output_dir = Path(runtime_cfg["output_dir"])
    root_output_dir.mkdir(parents=True, exist_ok=True)

    analysis_modes, analysis_mode_cluster_group_results = _ensure_mode_context(context)
    alias_cfg = runtime_cfg.get("final_parquet_alias_paths", {})
    mode_alias_paths = {
        "trialwise": Path(alias_cfg.get("trialwise", runtime_cfg.get("final_parquet_path", root_output_dir / "final.parquet"))),
        "concatenated": Path(alias_cfg.get("concatenated", root_output_dir / "final_concatenated.parquet")),
    }
    mode_exports = {}
    for mode in analysis_modes:
        mode_exports[mode] = _write_mode_exports(
            mode=mode,
            cluster_group_results=analysis_mode_cluster_group_results[mode],
            cfg=cfg,
            root_output_dir=root_output_dir,
            mode_output_dir=root_output_dir / mode,
            final_alias_path=mode_alias_paths.get(mode, root_output_dir / f"final_{mode}.parquet"),
        )
    cross_group_cfg = _cross_group_similarity_cfg(cfg)

    combined_summary = _concat_frames_union([exports["summary"] for exports in mode_exports.values()])
    _write_csv(combined_summary, root_output_dir / "final_summary.csv")

    combined_frames: dict[str, pd.DataFrame] = {}
    combined_final_parquet_frame = pd.DataFrame()
    for key, filename in AGGREGATE_NAME_MAP.items():
        frame = _concat_frames_union([exports["aggregate_frames"][key] for exports in mode_exports.values()])
        combined_frames[key] = frame
        _write_csv(frame, root_output_dir / filename)
        if key == "minimal_W":
            combined_final_parquet_frame = frame
    combined_source_trial_windows_frame = _concat_frames_union(
        [exports.get("source_trial_windows_frame", pd.DataFrame()) for exports in mode_exports.values()]
    )
    if not combined_source_trial_windows_frame.empty:
        _write_csv(
            combined_source_trial_windows_frame,
            root_output_dir / CONCATENATED_SOURCE_TRIAL_WINDOWS_FILENAME,
        )
    combined_pooled_strategy_summary = _concat_frames_union(
        [exports.get("pooled_strategy_summary_frame", pd.DataFrame()) for exports in mode_exports.values()]
    )
    if not combined_pooled_strategy_summary.empty:
        _write_csv(
            combined_pooled_strategy_summary,
            root_output_dir / POOLED_CLUSTER_STRATEGY_SUMMARY_FILENAME,
        )

    combined_final_parquet_path = Path(
        runtime_cfg.get("combined_final_parquet_path")
        or (root_output_dir / "final.parquet")
    )
    combined_final_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_parquet_frame(combined_final_parquet_frame).to_parquet(combined_final_parquet_path, index=False)
    final_parquet_alias_path = Path(
        runtime_cfg.get("final_parquet_path")
        or (root_output_dir / "final.parquet")
    )
    final_parquet_alias_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_parquet_frame(combined_final_parquet_frame).to_parquet(final_parquet_alias_path, index=False)

    root_cross_group_artifacts: dict[str, pd.DataFrame] = {}
    if len(analysis_modes) == 1 and cross_group_cfg["enabled"]:
        root_cross_group_artifacts = mode_exports[analysis_modes[0]]["cross_group_artifacts"]
        if cross_group_cfg["output_pairwise_csv"] and "cross_group_pairwise" in root_cross_group_artifacts:
            pairwise_path = root_output_dir / "cross_group_w_pairwise_cosine.csv"
            _write_csv(root_cross_group_artifacts["cross_group_pairwise"], pairwise_path)
            context["artifacts"]["cross_group_pairwise_path"] = str(pairwise_path)
        if cross_group_cfg["output_cluster_decision_csv"] and "cross_group_decision" in root_cross_group_artifacts:
            decision_path = root_output_dir / "cross_group_w_cluster_decision.csv"
            _write_csv(root_cross_group_artifacts["cross_group_decision"], decision_path)
            context["artifacts"]["cross_group_cluster_decision_path"] = str(decision_path)

    combined_audit_payloads = _combined_audit_payloads(analysis_mode_cluster_group_results)
    workbook_path = write_clustering_audit_workbook(
        root_output_dir / "clustering_audit.xlsx",
        combined_audit_payloads,
    )
    workbook_validation = validate_clustering_audit_workbook(workbook_path)
    interpretation_workbook_path = write_results_interpretation_workbook(
        root_output_dir / "results_interpretation.xlsx",
        combined_summary,
        {
            **combined_frames,
            **(
                root_cross_group_artifacts
                if len(analysis_modes) == 1 and cross_group_cfg["output_excel_sheets"]
                else {}
            ),
        },
    )
    interpretation_workbook_validation = validate_results_interpretation_workbook(interpretation_workbook_path)
    analysis_methods_manifest_path = _write_analysis_methods_manifest(
        cfg=cfg,
        analysis_modes=analysis_modes,
        mode_exports=mode_exports,
        combined_final_parquet_path=combined_final_parquet_path,
    )

    context["artifacts"]["summary_path"] = str(root_output_dir / "final_summary.csv")
    context["artifacts"]["combined_final_parquet_path"] = str(combined_final_parquet_path)
    context["artifacts"]["final_parquet_path"] = str(final_parquet_alias_path)
    if not combined_source_trial_windows_frame.empty:
        context["artifacts"]["concatenated_source_trial_windows_path"] = str(
            root_output_dir / CONCATENATED_SOURCE_TRIAL_WINDOWS_FILENAME
        )
    if not combined_pooled_strategy_summary.empty:
        context["artifacts"]["pooled_cluster_strategy_summary_path"] = str(
            root_output_dir / POOLED_CLUSTER_STRATEGY_SUMMARY_FILENAME
        )
    context["artifacts"]["final_parquet_alias_paths"] = {
        mode: str(mode_alias_paths.get(mode, root_output_dir / f"final_{mode}.parquet"))
        for mode in analysis_modes
    }
    context["artifacts"]["mode_output_dirs"] = {
        mode: str(exports["output_dir"]) for mode, exports in mode_exports.items()
    }
    context["artifacts"]["analysis_methods_manifest_path"] = str(analysis_methods_manifest_path)
    context["artifacts"]["clustering_audit_workbook_path"] = str(workbook_path)
    context["artifacts"]["clustering_audit_workbook_validation"] = workbook_validation
    context["artifacts"]["results_interpretation_workbook_path"] = str(interpretation_workbook_path)
    context["artifacts"]["results_interpretation_workbook_validation"] = interpretation_workbook_validation
    context["artifacts"]["group_figure_paths"] = [
        path
        for exports in mode_exports.values()
        for path in exports["rendered_figures"]["group_figure_paths"]
    ]
    context["artifacts"]["trial_figure_paths"] = [
        path
        for exports in mode_exports.values()
        for path in exports["rendered_figures"]["trial_figure_paths"]
    ]
    context["artifacts"]["cross_group_figure_paths"] = [
        path
        for exports in mode_exports.values()
        for path in exports["rendered_figures"]["cross_group_figure_paths"]
    ]
    return context
