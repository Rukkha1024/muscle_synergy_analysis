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


def test_merge_event_metadata_rejects_fractional_trial_num() -> None:
    """trial_num should fail-fast on non-integer numeric values."""
    emg_df = pd.DataFrame({"subject": ["S01"], "velocity": [1], "trial_num": [1]})
    event_df = pd.DataFrame({"subject": ["S01"], "velocity": [1], "trial_num": [1.5], "analysis_window_end": [10]})

    with pytest.raises(ValueError, match="integer-valued"):
        merge_event_metadata(emg_df, event_df)


def test_donorless_nonstep_group_slices_using_platform_offset(
    fixture_bundle: dict[str, object],
    tmp_path,
) -> None:
    """Donorless nonstep trials should still slice when platform_offset exists."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    workbook_path = tmp_path / "donorless_nonstep_slice.xlsx"
    platform_rows = [
        {
            "subject": "S99",
            "velocity": 1,
            "trial": 1,
            "platform_onset": 3,
            "platform_offset": 18,
            "step_onset": 11,
            "state": "step_L",  # contralateral for dominant=R => filtered out
            "step_TF": "step",
            "RPS": "1",
            "mixed": 1,
        },
        {
            "subject": "S99",
            "velocity": 1,
            "trial": 2,
            "platform_onset": 3,
            "platform_offset": 18,
            "step_onset": pd.NA,
            "state": "nonstep",
            "step_TF": "nonstep",
            "RPS": "2",
            "mixed": 1,
        },
    ]
    meta = pd.DataFrame(
        {
            "subject": ["나이", "주손 or 주발"],
            "S99": [24, "R"],
        }
    )
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame(platform_rows).to_excel(writer, sheet_name="platform", index=False)
        meta.to_excel(writer, sheet_name="meta", index=False)

    event_df = load_event_metadata(str(workbook_path), cfg)
    assert event_df.loc[event_df["analysis_selected_group"]].shape[0] == 1

    mocap_frames = list(range(21))
    emg_df = pd.DataFrame(
        {
            "subject": ["S99"] * len(mocap_frames),
            "velocity": [1] * len(mocap_frames),
            "trial_num": [2] * len(mocap_frames),
            "MocapFrame": mocap_frames,
            "original_DeviceFrame": [frame * 10 for frame in mocap_frames],
        }
    )
    merged = merge_event_metadata(emg_df, event_df)
    records = build_trial_records(merged, cfg)
    assert len(records) == 1
    record = records[0]
    assert int(record.frame["DeviceFrame"].max()) == 150
    assert record.metadata["analysis_window_source"] == "platform_offset"


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
