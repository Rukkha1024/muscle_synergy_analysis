"""Trial slicing and time-axis contract scaffolds."""

from __future__ import annotations

import pandas as pd
import pytest

from tests.helpers import resolve_callable


def test_trial_slicing_and_alignment_contract(fixture_bundle: dict[str, object]) -> None:
    """Sliced trials should preserve provenance and zero the relative frame at onset."""
    emg_df = pd.read_parquet(fixture_bundle["parquet"])
    event_df = pd.read_excel(fixture_bundle["xlsm"])

    try:
        merge_func, _, _ = resolve_callable(
            [
                "src.emg_pipeline",
                "src.emg_pipeline.trials",
                "src.emg_pipeline.io",
            ],
            [
                "merge_event_metadata",
                "merge_platform_meta",
                "_merge_platform_meta",
            ],
        )
    except LookupError as exc:
        pytest.xfail(f"EMG merge callable is not implemented yet: {exc}")
    merged = merge_func(emg_df.copy(), event_df.copy()) if merge_func.__code__.co_argcount >= 2 else merge_func(emg_df.copy())

    try:
        slice_func, _, _ = resolve_callable(
            [
                "src.emg_pipeline",
                "src.emg_pipeline.trials",
                "src.emg_pipeline.pipeline",
            ],
            [
                "slice_trials_by_events",
                "slice_trial_windows",
                "_slice_df_trial_by_on_offset",
            ],
        )
    except LookupError as exc:
        pytest.xfail(f"Trial slicing callable is not implemented yet: {exc}")

    trial_df = merged[
        (merged["subject"].astype(str) == "S01")
        & (merged["velocity"] == 1)
        & (merged["trial_num"] == 1)
    ].copy()
    sliced = slice_func(trial_df.copy())
    if sliced is None:
        pytest.fail("Trial slicing callable returned None for a populated trial.")
    assert not sliced.empty
    assert "original_DeviceFrame" in sliced.columns

    if "DeviceFrame" in sliced.columns:
        assert int(sliced["DeviceFrame"].min()) == 0
    else:
        onset = int(event_df.loc[0, "platform_onset"]) * 10
        derived = sliced["original_DeviceFrame"] - onset
        assert int(derived.min()) == 0
