"""Tests for subject-wise concatenated synergy analysis helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import src.synergy_stats.concatenated as concatenated_module
from src.emg_pipeline.trials import TrialRecord
from src.synergy_stats.concatenated import (
    build_concatenated_feature_rows,
    split_and_average_h_by_trial,
)
from src.synergy_stats.nmf import FeatureBundle


def test_concatenated_h_is_split_by_trial_and_averaged() -> None:
    """The stitched H timeline should be averaged back onto the trial grid."""
    concatenated_h = np.array(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [5.0, 50.0],
            [6.0, 60.0],
        ],
        dtype=np.float32,
    )

    averaged = split_and_average_h_by_trial(concatenated_h, [2, 2])

    expected = np.array(
        [
            [3.0, 30.0],
            [4.0, 40.0],
        ],
        dtype=np.float32,
    )
    assert np.allclose(averaged, expected)


def test_split_and_average_h_interpolates_mismatched_segment_lengths() -> None:
    """Concatenated H should align unequal segments onto a common trial grid."""
    concatenated_h = np.array(
        [
            [1.0],
            [3.0],
            [2.0],
            [4.0],
            [6.0],
        ],
        dtype=np.float32,
    )
    averaged = split_and_average_h_by_trial(concatenated_h, [2, 3])
    expected = np.array(
        [
            [1.5],
            [3.0],
            [4.5],
        ],
        dtype=np.float32,
    )
    assert np.allclose(averaged, expected)


def test_build_concatenated_feature_rows_creates_subject_level_units(monkeypatch) -> None:
    """The builder should emit one row per subject, velocity, and step class."""

    def _fake_extract_trial_features(x_trial, _cfg):
        n_frames = int(np.asarray(x_trial).shape[0])
        return FeatureBundle(
            W_muscle=np.array([[1.0], [0.0]], dtype=np.float32),
            H_time=np.arange(1, n_frames + 1, dtype=np.float32).reshape(-1, 1),
            meta={"status": "ok", "n_components": 1, "vaf": 0.95},
        )

    monkeypatch.setattr(concatenated_module, "extract_trial_features", _fake_extract_trial_features)

    def _trial(trial_num: int, step_class: str) -> TrialRecord:
        return TrialRecord(
            key=("S01", 1, trial_num),
            frame=pd.DataFrame(
                {
                    "TA": [0.1, 0.2],
                    "MG": [0.3, 0.4],
                }
            ),
            onset_device=0,
            offset_device=1,
            onset_column="platform_onset",
            offset_column="analysis_window_end",
            metadata={
                "analysis_selected_group": True,
                "analysis_step_class": step_class,
                "analysis_is_step": step_class == "step",
                "analysis_is_nonstep": step_class == "nonstep",
            },
        )

    rows = build_concatenated_feature_rows(
        trial_records=[_trial(1, "step"), _trial(3, "step"), _trial(2, "nonstep")],
        muscle_names=["TA", "MG"],
        cfg={},
    )

    step_row = next(row for row in rows if row.trial_num == "concat_step")
    nonstep_row = next(row for row in rows if row.trial_num == "concat_nonstep")

    assert step_row.bundle.meta["aggregation_mode"] == "concatenated"
    assert step_row.bundle.meta["analysis_unit_id"] == "S01_v1_step_concat"
    assert step_row.bundle.meta["source_trial_nums_csv"] == "1|3"
    assert step_row.bundle.meta["analysis_source_trial_count"] == 2
    assert np.allclose(step_row.bundle.H_time, np.array([[2.0], [3.0]], dtype=np.float32))

    assert nonstep_row.bundle.meta["analysis_step_class"] == "nonstep"
    assert nonstep_row.bundle.meta["source_trial_nums_csv"] == "2"


def test_build_concatenated_feature_rows_preserves_source_trial_details(monkeypatch) -> None:
    """Concatenated rows should keep one provenance payload per source trial."""

    def _fake_extract_trial_features(x_trial, _cfg):
        n_frames = int(np.asarray(x_trial).shape[0])
        return FeatureBundle(
            W_muscle=np.array([[1.0], [0.0]], dtype=np.float32),
            H_time=np.arange(1, n_frames + 1, dtype=np.float32).reshape(-1, 1),
            meta={"status": "ok", "n_components": 1, "vaf": 0.95},
        )

    monkeypatch.setattr(concatenated_module, "extract_trial_features", _fake_extract_trial_features)

    def _trial(
        trial_num: int,
        step_class: str,
        window_start: float,
        window_end: float,
        window_length: int,
        is_surrogate: bool,
    ) -> TrialRecord:
        return TrialRecord(
            key=("S01", 1, trial_num),
            frame=pd.DataFrame(
                {
                    "TA": [0.1, 0.2],
                    "MG": [0.3, 0.4],
                }
            ),
            onset_device=0,
            offset_device=1,
            onset_column="platform_onset",
            offset_column="analysis_window_end",
            metadata={
                "analysis_selected_group": True,
                "analysis_step_class": step_class,
                "analysis_is_step": step_class == "step",
                "analysis_is_nonstep": step_class == "nonstep",
                "analysis_window_source": "actual_step_onset" if not is_surrogate else "subject_mean_step_onset",
                "analysis_window_start": window_start,
                "analysis_window_end": window_end,
                "analysis_window_duration_device_frames": window_length,
                "analysis_window_is_surrogate": is_surrogate,
            },
        )

    rows = build_concatenated_feature_rows(
        trial_records=[
            _trial(1, "step", 100.0, 180.0, 80, False),
            _trial(3, "step", 105.0, 185.0, 80, False),
        ],
        muscle_names=["TA", "MG"],
        cfg={},
    )

    step_row = next(row for row in rows if row.trial_num == "concat_step")
    source_trial_details = step_row.bundle.meta["source_trial_details"]

    assert len(source_trial_details) == 2
    assert source_trial_details[0]["source_trial_num"] == 1
    assert source_trial_details[0]["source_trial_order"] == 1
    assert source_trial_details[0]["analysis_window_start"] == 100.0
    assert source_trial_details[0]["analysis_window_end"] == 180.0
    assert source_trial_details[0]["analysis_window_length"] == 80
    assert bool(source_trial_details[0]["analysis_window_is_surrogate"]) is False
    assert source_trial_details[1]["source_trial_num"] == 3
    assert source_trial_details[1]["source_trial_order"] == 2
