"""Serialize all export artifacts into one parquet per analysis scope.

This helper stores workbook and figure source frames in a
single parquet table keyed by `artifact_kind`, and restores
the original frame bundle when rerendering outputs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


AGGREGATE_NAME_MAP = {
    "metadata": "all_clustering_metadata",
    "labels": "all_cluster_labels",
    "rep_W": "all_representative_W_posthoc",
    "rep_H_long": "all_representative_H_posthoc_long",
    "minimal_W": "all_minimal_units_W",
    "minimal_H_long": "all_minimal_units_H_long",
    "trial_windows": "all_trial_window_metadata",
}

SUMMARY_FRAME_KEY = "final_summary"
SOURCE_TRIAL_WINDOWS_FRAME_KEY = "source_trial_windows"
POOLED_CLUSTER_STRATEGY_SUMMARY_KEY = "pooled_strategy_summary"
POOLED_CLUSTER_STRATEGY_W_MEANS_KEY = "pooled_strategy_w_means"
POOLED_CLUSTER_STRATEGY_H_MEANS_KEY = "pooled_strategy_h_means"

ARTIFACT_KIND_COLUMN = "artifact_kind"
SERIALIZED_FRAME_KEYS = [
    SUMMARY_FRAME_KEY,
    *AGGREGATE_NAME_MAP,
    SOURCE_TRIAL_WINDOWS_FRAME_KEY,
    POOLED_CLUSTER_STRATEGY_SUMMARY_KEY,
    POOLED_CLUSTER_STRATEGY_W_MEANS_KEY,
    POOLED_CLUSTER_STRATEGY_H_MEANS_KEY,
    "cross_group_pairwise",
    "cross_group_matrix",
    "cross_group_decision",
    "cross_group_summary",
    "audit_selection_summary",
    "audit_k_audit",
    "audit_duplicate_trial_summary",
    "audit_duplicate_cluster_detail",
]


def empty_bundle() -> dict[str, pd.DataFrame]:
    """Return an empty frame bundle keyed by artifact name."""
    return {frame_key: pd.DataFrame() for frame_key in SERIALIZED_FRAME_KEYS}


def prepare_parquet_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize shared identifier columns before parquet writes."""
    if frame.empty:
        return frame
    prepared = frame.copy()
    for column_name in (
        "aggregation_mode",
        "group_id",
        "subject",
        "trial_num",
        "analysis_unit_id",
        "source_trial_nums_csv",
        ARTIFACT_KIND_COLUMN,
    ):
        if column_name in prepared.columns:
            prepared[column_name] = prepared[column_name].astype(str)
    return prepared


def _ordered_union_columns(frames: list[pd.DataFrame]) -> list[str]:
    columns = [ARTIFACT_KIND_COLUMN]
    for frame in frames:
        for column_name in frame.columns:
            if column_name not in columns:
                columns.append(column_name)
    return columns


def bundle_to_single_frame(bundle: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Collapse a named frame bundle into one parquet-ready table."""
    serialized_frames: list[pd.DataFrame] = []
    for frame_key in SERIALIZED_FRAME_KEYS:
        frame = bundle.get(frame_key, pd.DataFrame())
        if frame is None or frame.empty:
            continue
        prepared = prepare_parquet_frame(frame).copy()
        prepared.insert(0, ARTIFACT_KIND_COLUMN, frame_key)
        serialized_frames.append(prepared)
    if not serialized_frames:
        return pd.DataFrame(columns=[ARTIFACT_KIND_COLUMN])
    union_columns = _ordered_union_columns(serialized_frames)
    normalized = [frame.reindex(columns=union_columns) for frame in serialized_frames]
    return pd.concat(normalized, ignore_index=True, sort=False)


def write_single_parquet_bundle(bundle: dict[str, pd.DataFrame], path: Path) -> Path:
    """Write one artifact bundle as a single parquet file."""
    serialized = bundle_to_single_frame(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    prepare_parquet_frame(serialized).to_parquet(path, index=False)
    return path


def load_single_parquet_bundle(path: Path) -> dict[str, pd.DataFrame]:
    """Restore a named artifact bundle from one parquet file."""
    bundle = empty_bundle()
    if not path.exists():
        return bundle
    serialized = pd.read_parquet(path)
    if serialized.empty:
        return bundle
    if ARTIFACT_KIND_COLUMN not in serialized.columns:
        raise ValueError(f"Single parquet is missing `{ARTIFACT_KIND_COLUMN}`: {path}")
    kind_series = serialized[ARTIFACT_KIND_COLUMN].astype(str)
    for frame_key in SERIALIZED_FRAME_KEYS:
        frame = serialized.loc[kind_series == frame_key].copy()
        if frame.empty:
            continue
        frame = frame.drop(columns=[ARTIFACT_KIND_COLUMN], errors="ignore")
        frame = frame.dropna(axis=1, how="all").reset_index(drop=True)
        bundle[frame_key] = frame
    return bundle


def resolve_single_parquet_path(cfg: dict, mode: str | None = None) -> Path:
    """Return the configured single-parquet source path for one scope."""
    runtime_cfg = cfg["runtime"]
    if mode is None:
        return Path(runtime_cfg["final_parquet_path"]).resolve()
    alias_paths = runtime_cfg.get("final_parquet_alias_paths", {})
    if mode in alias_paths:
        return Path(alias_paths[mode]).resolve()
    return Path(runtime_cfg["final_parquet_path"]).resolve()
