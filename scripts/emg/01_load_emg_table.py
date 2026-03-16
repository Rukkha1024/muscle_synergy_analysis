"""Load the EMG parquet and event workbook into pipeline context."""

from __future__ import annotations

import pandas as pd

from src.emg_pipeline import load_emg_table, load_event_metadata, merge_event_metadata
from src.emg_pipeline.log_utils import compact_list, format_float, log_kv_section


_BASE_KEYS = ["subject", "velocity", "trial_num"]


def _format_subjects(subjects: list[str]) -> str:
    if not subjects:
        return "0"
    return f"{len(subjects)} ({compact_list(subjects)})"


def _format_velocities(velocities: list[float]) -> str:
    if not velocities:
        return "n/a"
    return compact_list([f"{value:g}" for value in velocities], limit=8)


def run(context: dict) -> dict:
    cfg = context["config"]
    emg_df = load_emg_table(cfg["input"]["emg_parquet_path"])
    event_df = load_event_metadata(cfg["input"]["event_xlsm_path"], cfg)
    merged = merge_event_metadata(emg_df, event_df)
    context["emg_df"] = merged
    muscle_columns = [name for name in cfg["muscles"]["names"] if name in merged.columns]
    muscle_frame = merged[muscle_columns].apply(pd.to_numeric, errors="coerce") if muscle_columns else pd.DataFrame()
    trial_frame = merged.drop_duplicates(subset=_BASE_KEYS).copy()
    selected_trials = trial_frame.loc[trial_frame["analysis_selected_group"].fillna(False)].copy()
    selected_subjects = sorted(selected_trials["subject"].dropna().astype(str).unique().tolist())
    selected_velocities = sorted(selected_trials["velocity"].dropna().astype(float).unique().tolist())
    missing_count = int(muscle_frame.isna().sum().sum()) if not muscle_frame.empty else 0
    total_muscle_values = int(muscle_frame.shape[0] * muscle_frame.shape[1]) if not muscle_frame.empty else 0
    missing_ratio = (missing_count / total_muscle_values) if total_muscle_values else 0.0
    selected_step_count = int(
        selected_trials["analysis_is_step"].fillna(False).sum()
    ) if "analysis_is_step" in selected_trials.columns else 0
    selected_nonstep_count = int(
        selected_trials["analysis_is_nonstep"].fillna(False).sum()
    ) if "analysis_is_nonstep" in selected_trials.columns else 0
    surrogate_count = int(
        selected_trials["analysis_window_is_surrogate"].fillna(False).sum()
    ) if "analysis_window_is_surrogate" in selected_trials.columns else 0
    actual_window_count = max(len(selected_trials) - surrogate_count, 0)
    log_kv_section(
        "EMG Data",
        [
            ("Rows", len(merged)),
            ("Columns", len(merged.columns)),
            ("Subjects", _format_subjects(selected_subjects)),
            ("Velocities", _format_velocities(selected_velocities)),
            ("Muscle channels", len(muscle_columns)),
            ("Muscle missing", f"{missing_count} ({missing_ratio:.2%})"),
            ("Muscle min", format_float(muscle_frame.min().min() if not muscle_frame.empty else None, digits=4)),
            ("Muscle max", format_float(muscle_frame.max().max() if not muscle_frame.empty else None, digits=4)),
        ],
    )
    log_kv_section(
        "Event Metadata",
        [
            ("Event rows", len(trial_frame)),
            ("Selected trials", len(selected_trials)),
            ("Selected step", selected_step_count),
            ("Selected nonstep", selected_nonstep_count),
            ("Surrogate window end", surrogate_count),
            ("Actual window end", actual_window_count),
        ],
    )
    return context
