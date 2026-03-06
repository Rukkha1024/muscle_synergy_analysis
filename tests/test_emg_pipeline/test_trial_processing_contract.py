"""Trial slicing and window-resolution contract tests."""

from __future__ import annotations

from copy import deepcopy

import pandas as pd
import pytest

from src.emg_pipeline import build_trial_records, load_event_metadata, load_pipeline_config, merge_event_metadata


def test_trial_slicing_and_alignment_contract(fixture_bundle: dict[str, object]) -> None:
    """Mixed-only trial slices should use actual or surrogate step_onset end points."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    emg_df = pd.read_parquet(fixture_bundle["parquet"])
    event_df = load_event_metadata(str(fixture_bundle["xlsm"]), cfg)
    merged = merge_event_metadata(emg_df.copy(), event_df.copy())
    records = build_trial_records(merged, cfg)

    assert len(records) == 8
    assert {record.key[1] for record in records} == {1}

    step_record = next(record for record in records if record.key == ("S01", 1, 1))
    assert int(step_record.frame["DeviceFrame"].min()) == 0
    assert int(step_record.frame["DeviceFrame"].max()) == 80
    assert step_record.metadata["analysis_window_source"] == "actual_step_onset"
    assert bool(step_record.metadata["analysis_window_is_surrogate"]) is False

    nonstep_record = next(record for record in records if record.key == ("S01", 1, 3))
    assert int(nonstep_record.frame["DeviceFrame"].min()) == 0
    assert int(nonstep_record.frame["DeviceFrame"].max()) == 90
    assert nonstep_record.metadata["analysis_window_source"] == "subject_mean_step_onset"
    assert bool(nonstep_record.metadata["analysis_window_is_surrogate"]) is True


def test_merge_event_metadata_fails_when_emg_trial_has_no_event_match(
    fixture_bundle: dict[str, object],
) -> None:
    """Workbook key mismatches should fail instead of silently dropping trials."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    emg_df = pd.read_parquet(fixture_bundle["parquet"])
    event_df = load_event_metadata(str(fixture_bundle["xlsm"]), cfg)
    missing_trial_event_df = event_df.loc[~((event_df["subject"] == "S01") & (event_df["velocity"] == 1) & (event_df["trial_num"] == 1))].copy()

    with pytest.raises(ValueError, match="Missing event metadata for EMG trial keys"):
        merge_event_metadata(emg_df.copy(), missing_trial_event_df)


def test_legacy_platform_offset_window_remains_configurable(
    fixture_bundle: dict[str, object],
) -> None:
    """The previous platform_onset to platform_offset mode should still work by config."""
    cfg = deepcopy(load_pipeline_config(str(fixture_bundle["global_config"])))
    cfg["windowing"]["selection"]["mixed_only"] = False
    cfg["windowing"]["offset_column"] = "platform_offset"

    emg_df = pd.read_parquet(fixture_bundle["parquet"])
    event_df = load_event_metadata(str(fixture_bundle["xlsm"]), cfg)
    merged = merge_event_metadata(emg_df.copy(), event_df.copy())
    records = build_trial_records(merged, cfg)

    assert len(records) == 16
    assert {record.key[1] for record in records} == {1, 2}
    legacy_record = next(record for record in records if record.key == ("S01", 2, 4))
    assert int(legacy_record.frame["DeviceFrame"].min()) == 0
    assert int(legacy_record.frame["DeviceFrame"].max()) == 150
    assert legacy_record.metadata["analysis_window_source"] == "platform_offset"
    assert bool(legacy_record.metadata["analysis_window_is_surrogate"]) is False
