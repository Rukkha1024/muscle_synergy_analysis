"""Slice EMG trials using configurable event windows.

The slicer reads the prepared onset/end event columns, preserves
trial-level provenance, and returns aligned trial records for the
downstream NMF and clustering steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class TrialRecord:
    """Container for one `subject-velocity-trial` slice."""

    key: tuple[str, Any, Any]
    frame: pd.DataFrame
    onset_device: int
    offset_device: int
    onset_column: str
    offset_column: str
    metadata: dict[str, Any]


def _windowing_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("windowing", {})


def _resolve_frame_ratio(df_trial: pd.DataFrame, fallback: int = 10) -> int:
    if "MocapFrame" not in df_trial.columns or "original_DeviceFrame" not in df_trial.columns:
        return fallback
    diffs = df_trial[["MocapFrame", "original_DeviceFrame"]].drop_duplicates().sort_values("MocapFrame").diff().dropna()
    if diffs.empty:
        return fallback
    mocap_step = diffs["MocapFrame"].median()
    device_step = diffs["original_DeviceFrame"].median()
    if mocap_step in {0, 0.0} or pd.isna(mocap_step) or pd.isna(device_step):
        return fallback
    return int(round(float(device_step) / float(mocap_step)))


def _trial_metadata(first_row: pd.Series, onset_column: str, offset_column: str, onset_device: int, offset_device: int) -> dict[str, Any]:
    metadata = {
        "analysis_window_onset_column": onset_column,
        "analysis_window_offset_column": offset_column,
        "analysis_window_start": float(first_row[onset_column]),
        "analysis_window_end": float(first_row[offset_column]),
        "analysis_window_start_device": int(onset_device),
        "analysis_window_end_device": int(offset_device),
        "analysis_window_duration_device_frames": int(offset_device - onset_device),
    }
    for column, value in first_row.items():
        if column.startswith("analysis_") and column not in metadata:
            metadata[column] = value
    return metadata


def _event_device_value(row: pd.Series, value_name: str, frame_ratio: int) -> int:
    value = row.get(value_name)
    if pd.isna(value):
        raise ValueError(f"{value_name} is missing.")
    if "MocapFrame" in row.index:
        return int(round(float(value) * frame_ratio))
    return int(round(float(value)))


def _slice_trial(group: pd.DataFrame, frame_ratio: int, onset_column: str, offset_column: str) -> TrialRecord:
    group = group.sort_values("original_DeviceFrame").reset_index(drop=True)
    first_row = group.iloc[0]
    onset_device = _event_device_value(first_row, onset_column, frame_ratio)
    offset_device = _event_device_value(first_row, offset_column, frame_ratio)
    if offset_device < onset_device:
        raise ValueError(
            f"Window end precedes onset for key={first_row[['subject', 'velocity', 'trial_num']].tolist()} "
            f"using {onset_column}->{offset_column}."
        )
    mask = group["original_DeviceFrame"].between(onset_device, offset_device)
    sliced = group.loc[mask].copy()
    if sliced.empty:
        raise ValueError(f"Trial slice is empty for key={first_row[['subject', 'velocity', 'trial_num']].tolist()}")
    sliced["DeviceFrame"] = sliced["original_DeviceFrame"] - onset_device
    if "MocapFrame" in sliced.columns:
        sliced["relative_MocapFrame"] = sliced["MocapFrame"] - int(round(onset_device / frame_ratio))
    if not sliced["original_DeviceFrame"].is_monotonic_increasing:
        raise ValueError("original_DeviceFrame must be monotonic within each trial.")
    trial_key = (str(first_row["subject"]), first_row["velocity"], first_row["trial_num"])
    metadata = _trial_metadata(first_row, onset_column, offset_column, onset_device, offset_device)
    return TrialRecord(
        key=trial_key,
        frame=sliced,
        onset_device=onset_device,
        offset_device=offset_device,
        onset_column=onset_column,
        offset_column=offset_column,
        metadata=metadata,
    )


def _infer_window_columns(df_trial: pd.DataFrame) -> tuple[str, str]:
    onset_candidates = ["analysis_window_start", "platform_onset"]
    offset_candidates = ["analysis_window_end", "step_onset", "platform_offset"]
    onset_column = next((column for column in onset_candidates if column in df_trial.columns and df_trial[column].notna().any()), None)
    offset_column = next((column for column in offset_candidates if column in df_trial.columns and df_trial[column].notna().any()), None)
    if onset_column is None or offset_column is None:
        raise ValueError("Could not infer onset/offset columns from the trial frame.")
    return onset_column, offset_column


def _slice_df_trial_by_on_offset(df_trial: pd.DataFrame) -> pd.DataFrame:
    """Compatibility wrapper for one-trial slicing contract tests."""
    onset_column, offset_column = _infer_window_columns(df_trial)
    frame_ratio = _resolve_frame_ratio(df_trial)
    return _slice_trial(df_trial, frame_ratio=frame_ratio, onset_column=onset_column, offset_column=offset_column).frame


def slice_trials_by_events(df_trial: pd.DataFrame) -> pd.DataFrame:
    """Alias used by contract-style tests for a single trial input."""
    return _slice_df_trial_by_on_offset(df_trial)


def build_trial_records(df: pd.DataFrame, cfg: dict[str, Any]) -> list[TrialRecord]:
    emg_cfg = cfg.get("emg_pipeline", {})
    window_cfg = _windowing_cfg(cfg)
    frame_ratio = int(emg_cfg.get("frame_ratio", window_cfg.get("mocap_to_device_ratio", 10)))
    onset_column = str(window_cfg.get("onset_column", "platform_onset"))
    offset_column = str(window_cfg.get("offset_column", "platform_offset"))
    selected_df = df.copy()
    if "analysis_selected_group" in selected_df.columns:
        selected_df = selected_df.loc[selected_df["analysis_selected_group"].fillna(False)].copy()
        if selected_df.empty:
            raise ValueError("No selected trial groups remain after event filtering.")
    required = ["subject", "velocity", "trial_num", "original_DeviceFrame"]
    missing = [column for column in required if column not in selected_df.columns]
    if missing:
        raise ValueError(f"Missing columns required for trial building: {missing}")
    event_missing = [column for column in [onset_column, offset_column] if column not in selected_df.columns]
    if event_missing:
        raise ValueError(f"Missing event columns required for trial building: {event_missing}")
    trials: list[TrialRecord] = []
    for _, group in selected_df.groupby(["subject", "velocity", "trial_num"], sort=True):
        if group[[onset_column, offset_column]].isnull().any().any():
            raise ValueError(f"{onset_column}/{offset_column} must exist for every trial.")
        trials.append(_slice_trial(group, frame_ratio, onset_column, offset_column))
    return trials
