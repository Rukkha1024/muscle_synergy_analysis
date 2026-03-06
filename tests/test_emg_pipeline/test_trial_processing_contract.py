"""Trial slicing and window-resolution contract tests."""

from __future__ import annotations

import pandas as pd

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
    assert step_record.metadata["analysis_window_source"] == "step_onset"
    assert bool(step_record.metadata["analysis_window_is_surrogate"]) is False

    nonstep_record = next(record for record in records if record.key == ("S01", 1, 3))
    assert int(nonstep_record.frame["DeviceFrame"].min()) == 0
    assert int(nonstep_record.frame["DeviceFrame"].max()) == 90
    assert nonstep_record.metadata["analysis_window_source"] == "subject_velocity_mean_step_onset"
    assert bool(nonstep_record.metadata["analysis_window_is_surrogate"]) is True
