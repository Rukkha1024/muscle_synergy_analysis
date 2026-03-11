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


def _write_event_workbook(
    tmp_path: Path,
    *,
    platform_rows: list[dict[str, object]],
    transpose_meta_rows: list[dict[str, object]],
    name: str,
) -> Path:
    """Persist a small event workbook for contract checks."""
    workbook_path = tmp_path / name
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame(platform_rows).to_excel(writer, sheet_name="platform", index=False)
        pd.DataFrame(transpose_meta_rows).to_excel(writer, sheet_name="transpose_meta", index=False)
    return workbook_path


def test_event_preparation_fails_without_step_donor(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """A mixed group without valid step donors should fail early."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    invalid_path = _write_event_workbook(
        tmp_path,
        platform_rows=[
            {
                "subject": "S99",
                "velocity": 1,
                "trial": 1,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": 11,
                "state": "step_L",  # contralateral for dominant=R
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
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "2",
                "mixed": 1,
            },
        ],
        transpose_meta_rows=[{"subject": "S99", "나이": 20, "주손 or 주발": "R"}],
        name="invalid_events.xlsx",
    )

    with pytest.raises(ValueError, match="no eligible step donor|No eligible step trials"):
        load_event_metadata(str(invalid_path), cfg)


def test_event_preparation_excludes_contralateral_step_trials(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Contralateral step trials should be excluded even if mixed+young."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    path = _write_event_workbook(
        tmp_path,
        platform_rows=[
            {
                "subject": "S01",
                "velocity": 1,
                "trial": 1,
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
                "trial": 2,
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
                "trial": 3,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "3",
                "mixed": 1,
            },
        ],
        transpose_meta_rows=[{"subject": "S01", "나이": 24, "주손 or 주발": "R"}],
        name="ipsilateral_filter_events.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    selected = prepared.loc[prepared["analysis_selected_group"]].copy()
    assert selected.shape[0] > 0
    assert (selected["analysis_is_step"] | selected["analysis_is_nonstep"]).all()
    assert selected.loc[selected["analysis_is_step"], "analysis_state_norm"].eq("step_r").all()


def test_event_preparation_allows_multiple_selected_velocities_per_subject(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """The replace_V3D rule allows multiple velocities if they satisfy the row filter."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    path = _write_event_workbook(
        tmp_path,
        platform_rows=[
            {
                "subject": "S01",
                "velocity": 1,
                "trial": 1,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": 13,
                "state": "step_R",
                "step_TF": "step",
                "RPS": "11",
                "mixed": 1,
            },
            {
                "subject": "S01",
                "velocity": 1,
                "trial": 2,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "12",
                "mixed": 1,
            },
            {
                "subject": "S01",
                "velocity": 2,
                "trial": 1,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": 14,
                "state": "step_R",
                "step_TF": "step",
                "RPS": "21",
                "mixed": 1,
            },
            {
                "subject": "S01",
                "velocity": 2,
                "trial": 2,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "22",
                "mixed": 1,
            },
        ],
        transpose_meta_rows=[{"subject": "S01", "나이": 24, "주손 or 주발": "R"}],
        name="multiple_velocity_events.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    selected = prepared.loc[prepared["analysis_selected_group"]]
    assert set(selected["velocity"].unique().tolist()) == {1, 2}


def test_event_preparation_honors_disabled_surrogate_flag(
    fixture_bundle: dict[str, Path],
) -> None:
    """Disabling surrogate handling should fail selected nonstep trials with missing endpoints."""
    cfg = deepcopy(load_pipeline_config(str(fixture_bundle["global_config"])))
    cfg["windowing"]["surrogate_step_onset"]["enabled"] = False

    with pytest.raises(ValueError, match="surrogate_step_onset.enabled is false"):
        load_event_metadata(str(fixture_bundle["xlsm"]), cfg)
