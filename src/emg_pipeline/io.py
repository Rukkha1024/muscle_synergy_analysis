"""Load EMG/event tables and prepare analysis-ready metadata.

The event workflow validates required columns, filters the mixed
comparison set, derives surrogate nonstep window end points, and
returns a table that can be merged directly onto EMG rows.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl


BASE_KEYS = ["subject", "velocity", "trial_num"]
META_REQUIRED_FIELDS = ["나이", "주손 or 주발"]


def _normalize_dominant_side(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    if text in {"R", "RIGHT"}:
        return "R"
    if text in {"L", "LEFT"}:
        return "L"
    return ""


def _safe_read_excel(path: Path, *, sheet_name: str | int | None = None) -> pl.DataFrame:
    try:
        return pl.read_excel(str(path), sheet_name=sheet_name)
    except Exception:
        table = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
        try:
            return pl.from_pandas(table)
        except Exception:
            return pl.from_pandas(table.astype("string"))


def _load_subject_meta_from_meta_sheet(path: Path) -> pl.DataFrame:
    meta_raw = _safe_read_excel(path, sheet_name="meta")
    if "subject" not in meta_raw.columns:
        raise ValueError("meta sheet must contain `subject` column for field labels.")

    meta_raw = meta_raw.rename({"subject": "field"}).with_columns(
        pl.col("field").cast(pl.Utf8, strict=False).str.strip_chars()
    )
    meta_filtered = meta_raw.filter(pl.col("field").is_in(META_REQUIRED_FIELDS))
    present_fields = set(meta_filtered.get_column("field").to_list())
    missing_fields = sorted(set(META_REQUIRED_FIELDS) - present_fields)
    if missing_fields:
        raise ValueError(f"meta sheet missing required field rows: {missing_fields}")

    meta_long = meta_filtered.melt(id_vars=["field"], variable_name="subject", value_name="value")
    meta_wide = meta_long.pivot(index="subject", columns="field", values="value", aggregate_function="first")
    meta_wide = meta_wide.with_columns(pl.col("subject").cast(pl.Utf8, strict=False).str.strip_chars())

    dupe_mask = meta_wide.get_column("subject").is_duplicated()
    if dupe_mask.any():
        duplicates = meta_wide.filter(dupe_mask).get_column("subject").unique().to_list()
        raise ValueError(f"meta sheet has duplicate subjects: {duplicates}")

    return meta_wide.select(["subject"] + META_REQUIRED_FIELDS)


def _load_subject_meta_from_transpose_meta_sheet(path: Path) -> pl.DataFrame:
    meta = _safe_read_excel(path, sheet_name="transpose_meta")
    meta_required = {"subject", *META_REQUIRED_FIELDS}
    meta_missing = sorted(meta_required - set(meta.columns))
    if meta_missing:
        raise ValueError(f"transpose_meta sheet missing required columns: {meta_missing}")

    meta = (
        meta.select(["subject"] + META_REQUIRED_FIELDS)
        .with_columns(
            pl.col("subject").cast(pl.Utf8, strict=False).str.strip_chars(),
            pl.col("나이").cast(pl.Int64, strict=False),
            pl.col("주손 or 주발").cast(pl.Utf8, strict=False).str.strip_chars().str.to_uppercase(),
        )
    )

    dupe_mask = meta.get_column("subject").is_duplicated()
    if dupe_mask.any():
        duplicates = meta.filter(dupe_mask).get_column("subject").unique().to_list()
        raise ValueError(f"transpose_meta has duplicate subjects: {duplicates}")

    return meta


def _load_subject_meta(path: Path) -> pl.DataFrame:
    try:
        meta = _load_subject_meta_from_meta_sheet(path)
        return meta.with_columns(
            pl.col("나이").cast(pl.Int64, strict=False),
            pl.col("주손 or 주발").cast(pl.Utf8, strict=False).str.strip_chars().str.to_uppercase(),
        )
    except Exception as exc:
        logging.warning("Failed to read subject meta from `meta` sheet; falling back to `transpose_meta`: %s", exc)
        return _load_subject_meta_from_transpose_meta_sheet(path)


def _load_platform_with_subject_meta(path: Path) -> pd.DataFrame:
    platform = _safe_read_excel(path, sheet_name="platform")
    if "trial" in platform.columns and "trial_num" not in platform.columns:
        platform = platform.rename({"trial": "trial_num"})
    platform_required = {"subject", "velocity", "trial_num"}
    platform_missing = sorted(platform_required - set(platform.columns))
    if platform_missing:
        raise ValueError(f"platform sheet missing required columns: {platform_missing}")

    platform = platform.with_columns(
        pl.col("subject").cast(pl.Utf8, strict=False).str.strip_chars(),
        pl.col("velocity").cast(pl.Float64, strict=False),
        pl.col("trial_num").cast(pl.Int64, strict=False),
    )
    for column in ["platform_onset", "platform_offset", "step_onset"]:
        if column in platform.columns:
            platform = platform.with_columns(pl.col(column).cast(pl.Float64, strict=False))

    meta = _load_subject_meta(path)

    merged = platform.join(meta, on="subject", how="left")
    missing_meta_subjects = (
        merged.filter(pl.col("나이").is_null() | pl.col("주손 or 주발").is_null())
        .select("subject")
        .unique()
        .to_series()
        .to_list()
    )
    if missing_meta_subjects:
        raise ValueError(f"Missing subject meta for subject(s): {missing_meta_subjects}")

    return merged.to_pandas(use_pyarrow_extension_array=False)


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
    dominant_column = str(selection_cfg.get("dominant_column", "주손 or 주발"))
    age_column = str(selection_cfg.get("age_column", "나이"))
    young_age_threshold = int(selection_cfg.get("young_age_threshold", 30))
    step_class_column = str(surrogate_cfg.get("step_class_column", "step_TF"))
    step_value = _normalize_label(surrogate_cfg.get("step_value", "step"))
    nonstep_value = _normalize_label(surrogate_cfg.get("nonstep_value", "nonstep"))
    actual_step_column = str(surrogate_cfg.get("source_column", "step_onset"))
    output_column = str(surrogate_cfg.get("output_column", "analysis_window_end"))
    state_column = str(stance_cfg.get("state_column", "state"))
    require_mixed = bool(selection_cfg.get("mixed_only", False))
    surrogate_enabled = bool(surrogate_cfg.get("enabled", True))

    required = {onset_column}
    if require_mixed:
        required.update({mixed_column, step_class_column, actual_step_column, dominant_column})
        if "age_group" not in table.columns:
            required.add(age_column)
    elif offset_column != output_column:
        required.add(offset_column)
    if state_column:
        required.add(state_column)
    _require_columns(table, required, "event")

    prepared = table.copy()
    numeric_candidates = {onset_column, offset_column, actual_step_column, "platform_offset"}
    for column in sorted(numeric_candidates):
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
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
    prepared["analysis_state_norm"] = prepared["analysis_state"].map(_normalize_label)
    prepared["analysis_stance_side"] = prepared["analysis_state_norm"].map(_step_stance_side)

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
        prepared.loc[nonstep_mask, "analysis_stance_side"] = prepared.loc[nonstep_mask, "analysis_major_step_side"].map(
            _major_stance_from_step_state
        )
        return prepared

    prepared["analysis_dominant_side"] = prepared[dominant_column].map(_normalize_dominant_side)
    if "age_group" in prepared.columns:
        prepared["analysis_age_group"] = prepared["age_group"].map(_normalize_label)
    else:
        prepared["analysis_age_group"] = prepared[age_column].apply(
            lambda value: "young" if (not pd.isna(value) and float(value) < young_age_threshold) else "old"
        )

    ipsilateral_step = prepared["analysis_is_step"] & (
        ((prepared["analysis_dominant_side"] == "R") & prepared["analysis_state_norm"].eq("step_r"))
        | ((prepared["analysis_dominant_side"] == "L") & prepared["analysis_state_norm"].eq("step_l"))
    )
    prepared["analysis_selected_group"] = (
        prepared["analysis_is_mixed_flag"]
        & prepared["analysis_age_group"].eq("young")
        & (prepared["analysis_is_nonstep"] | ipsilateral_step)
    )
    prepared["analysis_selection_rule"] = "replace_v3d_meta_prefilter"

    if not prepared["analysis_selected_group"].any():
        raise ValueError("No trials remain after replace_V3D meta prefilter selection.")

    selected_step_mask = prepared["analysis_selected_group"] & prepared["analysis_is_step"]
    missing_step_onset_mask = selected_step_mask & prepared[actual_step_column].isna()
    if missing_step_onset_mask.any():
        bad_keys = (
            prepared.loc[missing_step_onset_mask, ["subject", "velocity", "trial_num"]]
            .drop_duplicates()
            .to_dict(orient="records")
        )
        logging.warning("Dropping selected step rows with missing %s: %s", actual_step_column, bad_keys)
        prepared.loc[missing_step_onset_mask, "analysis_selected_group"] = False
        selected_step_mask = prepared["analysis_selected_group"] & prepared["analysis_is_step"]
        if not prepared["analysis_selected_group"].any():
            raise ValueError("No trials remain after replace_V3D meta prefilter selection and step_onset requirement.")

    subject_major = (
        prepared.loc[selected_step_mask]
        .groupby(["subject", "velocity"], sort=False)["analysis_state"]
        .agg(_major_step_state)
        .rename("analysis_major_step_side")
        .reset_index()
    )
    prepared = (
        prepared.drop(columns=["analysis_major_step_side"], errors="ignore")
        .merge(subject_major, on=["subject", "velocity"], how="left")
    )
    prepared["analysis_major_step_side"] = prepared["analysis_major_step_side"].fillna("")
    nonstep_mask = prepared["analysis_is_nonstep"] & prepared["analysis_stance_side"].eq("")
    prepared.loc[nonstep_mask, "analysis_stance_side"] = prepared.loc[nonstep_mask, "analysis_major_step_side"].map(_major_stance_from_step_state)

    selected_nonstep_mask = prepared["analysis_selected_group"] & prepared["analysis_is_nonstep"]

    prepared[output_column] = pd.NA
    prepared.loc[selected_step_mask, output_column] = prepared.loc[selected_step_mask, actual_step_column]
    prepared.loc[selected_step_mask, "analysis_window_source"] = _source_label(actual_step_column)
    prepared.loc[selected_step_mask, "analysis_window_is_surrogate"] = False

    latency_series = pd.Series(pd.NA, index=prepared.index, dtype="Float64")
    latency_series.loc[selected_step_mask] = (
        prepared.loc[selected_step_mask, actual_step_column] - prepared.loc[selected_step_mask, onset_column]
    ).astype(float)
    group_latency_mean = latency_series.groupby([prepared["subject"], prepared["velocity"]]).transform("mean")

    if selected_nonstep_mask.any():
        if surrogate_enabled:
            missing_donor_mask = selected_nonstep_mask & group_latency_mean.isna()
            if missing_donor_mask.any():
                if "platform_offset" not in prepared.columns:
                    raise ValueError("platform_offset is required to window donorless nonstep trials.")
                bad_groups = (
                    prepared.loc[missing_donor_mask, ["subject", "velocity"]]
                    .drop_duplicates()
                    .to_dict(orient="records")
                )
                logging.warning(
                    "No eligible step donor found for selected nonstep group(s); using platform_offset: %s",
                    bad_groups,
                )
                prepared.loc[missing_donor_mask, output_column] = prepared.loc[missing_donor_mask, "platform_offset"]
                prepared.loc[missing_donor_mask, "analysis_window_source"] = _source_label("platform_offset")
                prepared.loc[missing_donor_mask, "analysis_window_is_surrogate"] = False

            surrogate_mask = selected_nonstep_mask & ~missing_donor_mask
            if surrogate_mask.any():
                prepared.loc[surrogate_mask, output_column] = (
                    prepared.loc[surrogate_mask, onset_column].astype(float) + group_latency_mean.loc[surrogate_mask]
                )
                prepared.loc[surrogate_mask, "analysis_window_source"] = "subject_mean_step_onset"
                prepared.loc[surrogate_mask, "analysis_window_is_surrogate"] = True
        else:
            if prepared.loc[selected_nonstep_mask, actual_step_column].isna().any():
                raise ValueError("Nonstep trial requires a surrogate step_onset, but surrogate_step_onset.enabled is false.")
            prepared.loc[selected_nonstep_mask, output_column] = prepared.loc[selected_nonstep_mask, actual_step_column]
            prepared.loc[selected_nonstep_mask, "analysis_window_source"] = _source_label(actual_step_column)
            prepared.loc[selected_nonstep_mask, "analysis_window_is_surrogate"] = False

    group_step_mean = (
        prepared[actual_step_column]
        .where(selected_step_mask)
        .groupby([prepared["subject"], prepared["velocity"]])
        .transform("mean")
    )
    prepared["analysis_subject_mean_step_onset"] = group_step_mean.astype(float)
    prepared["analysis_subject_mean_step_latency"] = group_latency_mean.astype(float)

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
    table = _load_platform_with_subject_meta(path)
    _require_columns(table, set(BASE_KEYS), "event")
    prepared = _prepare_event_metadata(table, cfg)
    window_cfg = _windowing_cfg(cfg)
    onset_column = str(window_cfg.get("onset_column", "platform_onset"))
    offset_column = str(window_cfg.get("offset_column", "platform_offset"))
    _require_columns(prepared, set(BASE_KEYS + [onset_column, offset_column]), "prepared event")
    return prepared


def merge_event_metadata(emg_df: pd.DataFrame, event_df: pd.DataFrame) -> pd.DataFrame:
    merged = emg_df.copy()

    def _normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.copy()
        normalized["subject"] = normalized["subject"].astype(str).str.strip()
        normalized["velocity"] = pd.to_numeric(normalized["velocity"], errors="coerce").astype(float)
        trial_numeric = pd.to_numeric(normalized["trial_num"], errors="coerce")
        if trial_numeric.isna().any():
            raise ValueError("trial_num must be numeric and non-null for event/EMG merging.")
        rounded = trial_numeric.round()
        non_integer_mask = (trial_numeric - rounded).abs() > 1e-9
        if non_integer_mask.any():
            bad_values = trial_numeric.loc[non_integer_mask].drop_duplicates().tolist()
            raise ValueError(f"trial_num must be integer-valued for event/EMG merging. Bad values: {bad_values}")
        normalized["trial_num"] = rounded.astype(int)
        return normalized

    merged = _normalize_keys(merged)
    event_df = _normalize_keys(event_df)

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
