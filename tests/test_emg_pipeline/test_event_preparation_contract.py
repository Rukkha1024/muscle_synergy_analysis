"""Event preparation contract tests for mixed-window selection.

These tests focus on the event workbook rules that select mixed
comparison groups and derive surrogate nonstep step-onset values.
"""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from src.emg_pipeline import load_event_metadata, load_pipeline_config


def _write_event_workbook(tmp_path: Path, rows: list[dict[str, object]], name: str) -> Path:
    """Persist a small event workbook for contract checks."""
    workbook_path = tmp_path / name
    pd.DataFrame(rows).to_excel(workbook_path, index=False, engine="openpyxl")
    return workbook_path


def test_event_preparation_fails_without_step_donor(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """A mixed group without valid step donors should fail early."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    invalid_path = _write_event_workbook(
        tmp_path,
        [
            {
                "subject": "S99",
                "velocity": 1,
                "trial_num": trial_num,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": str(trial_num),
                "mixed": 1,
            }
            for trial_num in range(1, 5)
        ],
        "invalid_events.xlsx",
    )

    with pytest.raises(ValueError, match="No valid mixed-velocity groups remain after event filtering"):
        load_event_metadata(str(invalid_path), cfg)


def test_event_preparation_rejects_groups_with_extra_trials(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Only exact 2-step plus 2-nonstep groups should be selected."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    invalid_path = _write_event_workbook(
        tmp_path,
        [
            {
                "subject": "S01",
                "velocity": 1,
                "trial_num": 1,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": 11,
                "state": "step_L",
                "step_TF": "step",
                "RPS": "1",
                "mixed": 1,
            },
            {
                "subject": "S01",
                "velocity": 1,
                "trial_num": 2,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": 13,
                "state": "step_R",
                "step_TF": "step",
                "RPS": "2",
                "mixed": 1,
            },
            {
                "subject": "S01",
                "velocity": 1,
                "trial_num": 3,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "3",
                "mixed": 1,
            },
            {
                "subject": "S01",
                "velocity": 1,
                "trial_num": 4,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "4",
                "mixed": 1,
            },
            {
                "subject": "S01",
                "velocity": 1,
                "trial_num": 5,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": 9,
                "state": "other",
                "step_TF": "other",
                "RPS": "5",
                "mixed": 1,
            },
        ],
        "extra_trial_events.xlsx",
    )

    with pytest.raises(ValueError, match="No valid mixed-velocity groups remain after event filtering"):
        load_event_metadata(str(invalid_path), cfg)


def test_event_preparation_rejects_multiple_selected_velocities_per_subject(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """A subject should not retain more than one mixed comparison velocity."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    invalid_rows: list[dict[str, object]] = []
    for velocity in [1, 2]:
        invalid_rows.extend(
            [
                {
                    "subject": "S01",
                    "velocity": velocity,
                    "trial_num": 1,
                    "platform_onset": 3,
                    "platform_offset": 18,
                    "step_onset": 11,
                    "state": "step_L",
                    "step_TF": "step",
                    "RPS": f"{velocity}1",
                    "mixed": 1,
                },
                {
                    "subject": "S01",
                    "velocity": velocity,
                    "trial_num": 2,
                    "platform_onset": 3,
                    "platform_offset": 18,
                    "step_onset": 13,
                    "state": "step_R",
                    "step_TF": "step",
                    "RPS": f"{velocity}2",
                    "mixed": 1,
                },
                {
                    "subject": "S01",
                    "velocity": velocity,
                    "trial_num": 3,
                    "platform_onset": 3,
                    "platform_offset": 18,
                    "step_onset": np.nan,
                    "state": "nonstep",
                    "step_TF": "nonstep",
                    "RPS": f"{velocity}3",
                    "mixed": 1,
                },
                {
                    "subject": "S01",
                    "velocity": velocity,
                    "trial_num": 4,
                    "platform_onset": 3,
                    "platform_offset": 18,
                    "step_onset": np.nan,
                    "state": "nonstep",
                    "step_TF": "nonstep",
                    "RPS": f"{velocity}4",
                    "mixed": 1,
                },
            ]
        )
    invalid_path = _write_event_workbook(tmp_path, invalid_rows, "multiple_velocity_events.xlsx")

    with pytest.raises(ValueError, match="Multiple mixed velocities remain for subject"):
        load_event_metadata(str(invalid_path), cfg)


def test_event_preparation_honors_disabled_surrogate_flag(
    fixture_bundle: dict[str, Path],
) -> None:
    """Disabling surrogate handling should fail selected nonstep trials with missing endpoints."""
    cfg = deepcopy(load_pipeline_config(str(fixture_bundle["global_config"])))
    cfg["windowing"]["surrogate_step_onset"]["enabled"] = False

    with pytest.raises(ValueError, match="surrogate_step_onset.enabled is false"):
        load_event_metadata(str(fixture_bundle["xlsm"]), cfg)
