"""Load EMG/event tables and prepare analysis-ready metadata.

The event workflow validates required columns, filters the mixed
comparison set, derives surrogate nonstep window end points, and
returns a table that can be merged directly onto EMG rows.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl


BASE_KEYS = ["subject", "velocity", "trial_num"]


def _windowing_cfg(cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not cfg:
        return {}
    return cfg.get("windowing", {})


def _selection_cfg(cfg: dict[str, Any] | None) -> dict[str, Any]:
    return _windowing_cfg(cfg).get("selection", {})


def _surrogate_cfg(cfg: dict[str, Any] | None) -> dict[str, Any]:
    return _windowing_cfg(cfg).get("surrogate_step_onset", {})


def _stance_cfg(cfg: dict[str, Any] | None) -> dict[str, Any]:
    return _windowing_cfg(cfg).get("stance_metadata", {})


def _is_truthy(value: Any) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in {"1", "1.0", "true", "y", "yes"}


def _normalize_label(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def _step_stance_side(state_value: Any) -> str:
    state = _normalize_label(state_value)
    if state == "step_r":
        return "left"
    if state == "step_l":
        return "right"
    return ""


def _major_step_state(step_states: pd.Series) -> str:
    normalized = [_normalize_label(value) for value in step_states if _normalize_label(value) in {"step_l", "step_r"}]
    if not normalized:
        return ""
    counts = Counter(normalized)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _major_stance_from_step_state(step_state: str) -> str:
    if step_state == "step_r":
        return "left"
    if step_state == "step_l":
        return "right"
    return ""


def _require_columns(table: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(set(table.columns)))
    if missing:
        raise ValueError(f"Missing required {label} columns: {missing}")


def _source_label(label: str) -> str:
    mapping = {
        "platform_offset": "platform_offset",
        "step_onset": "actual_step_onset",
        "subject_velocity_mean_step_onset": "subject_mean_step_onset",
    }
    return mapping.get(label, str(label))


def _prepare_event_metadata(table: pd.DataFrame, cfg: dict[str, Any] | None) -> pd.DataFrame:
    cfg = cfg or {}
    window_cfg = _windowing_cfg(cfg)
    selection_cfg = _selection_cfg(cfg)
    surrogate_cfg = _surrogate_cfg(cfg)
    stance_cfg = _stance_cfg(cfg)
    onset_column = str(window_cfg.get("onset_column", "platform_onset"))
    offset_column = str(window_cfg.get("offset_column", "platform_offset"))
    mixed_column = str(selection_cfg.get("mixed_column", "mixed"))
    step_class_column = str(surrogate_cfg.get("step_class_column", "step_TF"))
    step_value = _normalize_label(surrogate_cfg.get("step_value", "step"))
    nonstep_value = _normalize_label(surrogate_cfg.get("nonstep_value", "nonstep"))
    actual_step_column = str(surrogate_cfg.get("source_column", "step_onset"))
    output_column = str(surrogate_cfg.get("output_column", "analysis_window_end"))
    state_column = str(stance_cfg.get("state_column", "state"))
    require_mixed = bool(selection_cfg.get("mixed_only", False))
    require_step_trials = selection_cfg.get("require_step_trials")
    require_nonstep_trials = selection_cfg.get("require_nonstep_trials")
    require_total_trials = selection_cfg.get("require_total_trials")
    require_single_velocity_per_subject = bool(selection_cfg.get("single_velocity_per_subject", False))
    surrogate_enabled = bool(surrogate_cfg.get("enabled", True))

    required = {onset_column}
    if require_mixed:
        required.update({mixed_column, step_class_column, actual_step_column})
    elif offset_column != output_column:
        required.add(offset_column)
    if state_column:
        required.add(state_column)
    _require_columns(table, required, "event")

    prepared = table.copy()
    prepared["analysis_step_class"] = prepared[step_class_column].map(_normalize_label)
    prepared["analysis_is_step"] = prepared["analysis_step_class"].eq(step_value)
    prepared["analysis_is_nonstep"] = prepared["analysis_step_class"].eq(nonstep_value)
    prepared["analysis_is_mixed_flag"] = prepared[mixed_column].map(_is_truthy) if mixed_column in prepared.columns else False
    prepared["analysis_window_start"] = prepared[onset_column]
    prepared["analysis_window_source"] = _source_label(offset_column)
    prepared["analysis_window_is_surrogate"] = False
    prepared["analysis_window_onset_column"] = onset_column
    prepared["analysis_window_offset_column"] = offset_column

    if state_column in prepared.columns:
        prepared["analysis_state"] = prepared[state_column].fillna("").astype(str)
    else:
        prepared["analysis_state"] = ""
    prepared["analysis_stance_side"] = prepared["analysis_state"].map(_step_stance_side)
    subject_major = (
        prepared.loc[prepared["analysis_is_step"]]
        .groupby("subject", sort=False)["analysis_state"]
        .agg(_major_step_state)
        .rename("analysis_major_step_side")
        .reset_index()
    )
    prepared = prepared.merge(subject_major, on="subject", how="left")
    prepared["analysis_major_step_side"] = prepared["analysis_major_step_side"].fillna("")
    nonstep_mask = prepared["analysis_is_nonstep"] & prepared["analysis_stance_side"].eq("")
    prepared.loc[nonstep_mask, "analysis_stance_side"] = prepared.loc[nonstep_mask, "analysis_major_step_side"].map(_major_stance_from_step_state)

    if not require_mixed:
        if offset_column == output_column:
            if surrogate_enabled and actual_step_column not in prepared.columns:
                raise ValueError(f"{actual_step_column} is required to derive {output_column}.")
            if not surrogate_enabled and output_column not in prepared.columns:
                raise ValueError(f"{output_column} is required when surrogate_step_onset.enabled is false.")
            prepared[output_column] = prepared[actual_step_column] if surrogate_enabled else prepared[output_column]
            prepared["analysis_window_source"] = _source_label(actual_step_column if surrogate_enabled else output_column)
            prepared["analysis_window_is_surrogate"] = False
        else:
            prepared[output_column] = prepared[offset_column]
            prepared["analysis_window_source"] = _source_label(offset_column)
        prepared["analysis_selection_rule"] = "all_trials"
        prepared["analysis_selected_group"] = True
        return prepared

    selection_summary = (
        prepared.groupby(["subject", "velocity"], sort=True)
        .agg(
            analysis_mixed_group_step_trials=("analysis_is_step", "sum"),
            analysis_mixed_group_nonstep_trials=("analysis_is_nonstep", "sum"),
            analysis_mixed_group_total_trials=("trial_num", "size"),
            analysis_group_is_mixed_flag=("analysis_is_mixed_flag", "max"),
            analysis_group_has_complete_step_onset=(actual_step_column, lambda series: bool(series.loc[prepared.loc[series.index, "analysis_is_step"]].notna().all())),
        )
        .reset_index()
    )
    valid_groups = selection_summary["analysis_group_is_mixed_flag"]
    if require_step_trials is not None:
        valid_groups &= selection_summary["analysis_mixed_group_step_trials"].eq(int(require_step_trials))
    else:
        valid_groups &= selection_summary["analysis_mixed_group_step_trials"].gt(0)
    if require_nonstep_trials is not None:
        valid_groups &= selection_summary["analysis_mixed_group_nonstep_trials"].eq(int(require_nonstep_trials))
    else:
        valid_groups &= selection_summary["analysis_mixed_group_nonstep_trials"].gt(0)
    if require_total_trials is not None:
        valid_groups &= selection_summary["analysis_mixed_group_total_trials"].eq(int(require_total_trials))
    valid_groups &= selection_summary["analysis_group_has_complete_step_onset"]
    selection_summary["analysis_selected_group"] = valid_groups
    selection_summary["analysis_selection_rule"] = "mixed_velocity_exact_counts"

    prepared = prepared.merge(selection_summary, on=["subject", "velocity"], how="left")
    if not prepared["analysis_selected_group"].fillna(False).any():
        raise ValueError("No valid mixed-velocity groups remain after event filtering.")
    prepared["analysis_selected_group"] = prepared["analysis_selected_group"].fillna(False)
    prepared["analysis_selection_rule"] = prepared["analysis_selection_rule"].fillna("mixed_velocity_exact_counts")
    if require_single_velocity_per_subject:
        subject_velocity_counts = (
            prepared.loc[prepared["analysis_selected_group"]]
            .groupby("subject", sort=True)["velocity"]
            .nunique()
        )
        ambiguous_subjects = subject_velocity_counts.loc[subject_velocity_counts.gt(1)].index.tolist()
        if ambiguous_subjects:
            raise ValueError(
                "Multiple mixed velocities remain for subject(s): "
                + ", ".join(str(subject) for subject in ambiguous_subjects)
            )

    prepared[output_column] = pd.NA
    selected_mask = prepared["analysis_selected_group"]
    prepared.loc[selected_mask, output_column] = prepared.loc[selected_mask, actual_step_column]
    prepared.loc[selected_mask, "analysis_window_source"] = _source_label(actual_step_column)
    prepared.loc[selected_mask, "analysis_window_is_surrogate"] = False
    selected_groups = prepared.loc[selected_mask].groupby("subject", sort=True)
    for subject, group in selected_groups:
        step_mask = group["analysis_is_step"]
        if not step_mask.any():
            raise ValueError(f"No step trials available for surrogate derivation: subject={subject}")
        step_mean = float(group.loc[step_mask, actual_step_column].mean())
        if pd.isna(step_mean):
            raise ValueError(f"No valid step_onset donor for subject={subject}")
        step_latency_mean = float((group.loc[step_mask, actual_step_column] - group.loc[step_mask, onset_column]).mean())
        # Latency mean is exported as metadata, but it is not required for the
        # README-aligned surrogate rule (absolute mean step_onset).
        if pd.isna(step_latency_mean):
            step_latency_mean = float("nan")
        nonstep_mask_group = group["analysis_is_nonstep"]
        if nonstep_mask_group.any():
            if surrogate_enabled:
                # README contract: nonstep trials use the subject's mean step_onset
                # (absolute event time) as the surrogate window end.
                prepared.loc[group.index[nonstep_mask_group], output_column] = step_mean
                prepared.loc[group.index[nonstep_mask_group], "analysis_window_source"] = "subject_mean_step_onset"
                prepared.loc[group.index[nonstep_mask_group], "analysis_window_is_surrogate"] = True
            elif group.loc[nonstep_mask_group, actual_step_column].isna().any():
                raise ValueError(
                    "Nonstep trial requires a surrogate step_onset, but surrogate_step_onset.enabled is false: "
                    f"subject={subject}"
                )
        prepared.loc[group.index, "analysis_subject_mean_step_onset"] = step_mean
        prepared.loc[group.index, "analysis_subject_mean_step_latency"] = step_latency_mean

    return prepared


def load_emg_table(parquet_path: str) -> pd.DataFrame:
    path = Path(parquet_path)
    if not path.exists():
        raise FileNotFoundError(f"EMG parquet not found: {path}")
    table = pl.read_parquet(path)
    required = {"subject", "velocity", "trial_num"}
    missing = sorted(required.difference(set(table.columns)))
    if missing:
        raise ValueError(f"Missing required EMG columns: {missing}")
    return table.to_pandas(use_pyarrow_extension_array=False)


def load_event_metadata(xlsm_path: str, cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    path = Path(xlsm_path)
    if not path.exists():
        raise FileNotFoundError(f"Event workbook not found: {path}")
    table = pd.read_excel(path, engine="openpyxl")
    if "trial" in table.columns and "trial_num" not in table.columns:
        table = table.rename(columns={"trial": "trial_num"})
    _require_columns(table, set(BASE_KEYS), "event")
    prepared = _prepare_event_metadata(table, cfg)
    window_cfg = _windowing_cfg(cfg)
    onset_column = str(window_cfg.get("onset_column", "platform_onset"))
    offset_column = str(window_cfg.get("offset_column", "platform_offset"))
    _require_columns(prepared, set(BASE_KEYS + [onset_column, offset_column]), "prepared event")
    return prepared


def merge_event_metadata(emg_df: pd.DataFrame, event_df: pd.DataFrame) -> pd.DataFrame:
    merged = emg_df.copy()
    if event_df.duplicated(BASE_KEYS).any():
        duplicate_keys = event_df.loc[event_df.duplicated(BASE_KEYS, keep=False), BASE_KEYS].drop_duplicates()
        raise ValueError(f"Duplicate event rows found for keys: {duplicate_keys.to_dict(orient='records')}")
    override_columns = [column for column in event_df.columns if column not in BASE_KEYS]
    merged = merged.drop(columns=[column for column in override_columns if column in merged.columns], errors="ignore")
    merged = merged.merge(event_df, on=BASE_KEYS, how="left", validate="m:1", indicator=True)
    unmatched = merged.loc[merged["_merge"] != "both", BASE_KEYS].drop_duplicates().to_dict(orient="records")
    if unmatched:
        raise ValueError(f"Missing event metadata for EMG trial keys: {unmatched}")
    return merged.drop(columns="_merge")
