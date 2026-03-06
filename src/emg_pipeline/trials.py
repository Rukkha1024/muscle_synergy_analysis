"""Slice EMG trials and derive aligned time axes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class TrialRecord:
    """Container for one `subject-velocity-trial` slice."""

    key: tuple[str, Any, Any]
    frame: pd.DataFrame
    onset_device: int
    offset_device: int


def _event_device_value(row: pd.Series, value_name: str, frame_ratio: int) -> int:
    value = row.get(value_name)
    if pd.isna(value):
        raise ValueError(f"{value_name} is missing.")
    if "MocapFrame" in row.index:
        return int(round(float(value) * frame_ratio))
    return int(round(float(value)))


def _slice_trial(group: pd.DataFrame, frame_ratio: int) -> TrialRecord:
    group = group.sort_values("original_DeviceFrame").reset_index(drop=True)
    first_row = group.iloc[0]
    onset_device = _event_device_value(first_row, "platform_onset", frame_ratio)
    offset_device = _event_device_value(first_row, "platform_offset", frame_ratio)
    if offset_device < onset_device:
        onset_device, offset_device = offset_device, onset_device
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
    return TrialRecord(key=trial_key, frame=sliced, onset_device=onset_device, offset_device=offset_device)


def _slice_df_trial_by_on_offset(df_trial: pd.DataFrame) -> pd.DataFrame:
    """Compatibility wrapper for one-trial slicing contract tests."""
    frame_ratio = 10
    if "relative_MocapFrame" in df_trial.columns:
        frame_ratio = int(round((df_trial["original_DeviceFrame"].iloc[0] - df_trial["DeviceFrame"].iloc[0]) / max(df_trial["MocapFrame"].iloc[0], 1)))
    return _slice_trial(df_trial, frame_ratio=frame_ratio).frame


def slice_trials_by_events(df_trial: pd.DataFrame) -> pd.DataFrame:
    """Alias used by contract-style tests for a single trial input."""
    return _slice_df_trial_by_on_offset(df_trial)


def build_trial_records(df: pd.DataFrame, cfg: dict[str, Any]) -> list[TrialRecord]:
    emg_cfg = cfg.get("emg_pipeline", {})
    window_cfg = cfg.get("windowing", {})
    frame_ratio = int(emg_cfg.get("frame_ratio", window_cfg.get("mocap_to_device_ratio", 10)))
    required = ["subject", "velocity", "trial_num", "original_DeviceFrame"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns required for trial building: {missing}")
    trials: list[TrialRecord] = []
    for _, group in df.groupby(["subject", "velocity", "trial_num"], sort=True):
        if group[["platform_onset", "platform_offset"]].isnull().any().any():
            raise ValueError("platform_onset/platform_offset must exist for every trial.")
        trials.append(_slice_trial(group, frame_ratio))
    return trials
