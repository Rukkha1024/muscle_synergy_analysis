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


def _transpose_meta_rows_to_meta_sheet(transpose_meta_rows: list[dict[str, object]]) -> pd.DataFrame:
    """Convert subject-row meta into the `meta` sheet layout (field x subject)."""
    fields = ["나이", "주손 or 주발"]
    payload: dict[str, list[object]] = {"subject": fields}
    for row in transpose_meta_rows:
        subject = str(row["subject"])
        payload[subject] = [row.get("나이"), row.get("주손 or 주발")]
    return pd.DataFrame(payload)


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
        _transpose_meta_rows_to_meta_sheet(transpose_meta_rows).to_excel(writer, sheet_name="meta", index=False)
    return workbook_path


def test_event_preparation_drops_selected_nonstep_rows_without_step_donor(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Selected nonstep rows without eligible step donors should be unselected instead of crashing."""
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
            {
                "subject": "S01",
                "velocity": 1,
                "trial": 1,
                "platform_onset": 3,
                "platform_offset": 18,
                "step_onset": 11,
                "state": "step_R",
                "step_TF": "step",
                "RPS": "3",
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
                "RPS": "4",
                "mixed": 1,
            },
        ],
        transpose_meta_rows=[
            {"subject": "S99", "나이": 20, "주손 or 주발": "R"},
            {"subject": "S01", "나이": 24, "주손 or 주발": "R"},
        ],
        name="invalid_events.xlsx",
    )

    prepared = load_event_metadata(str(invalid_path), cfg)
    invalid_rows = prepared.loc[(prepared["subject"] == "S99") & (prepared["velocity"] == 1)]
    assert invalid_rows["analysis_selected_group"].eq(False).all()
    assert prepared["analysis_selected_group"].any()


def test_event_preparation_drops_selected_step_rows_missing_step_onset(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Selected step trials must provide step_onset, otherwise they should be excluded."""
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
                "step_onset": np.nan,
                "state": "step_R",
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
        name="missing_step_onset_drop.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    dropped_step = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 1) & (prepared["trial_num"] == 1)].iloc[0]
    kept_step = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 1) & (prepared["trial_num"] == 2)].iloc[0]
    nonstep = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 1) & (prepared["trial_num"] == 3)].iloc[0]

    assert bool(dropped_step["analysis_selected_group"]) is False
    assert bool(kept_step["analysis_selected_group"]) is True
    assert bool(nonstep["analysis_selected_group"]) is True


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


def test_event_preparation_disabled_surrogate_uses_actual_step_onset_for_nonstep(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """When surrogate is disabled, nonstep trials must provide step_onset and it should be used."""
    cfg = deepcopy(load_pipeline_config(str(fixture_bundle["global_config"])))
    cfg["windowing"]["surrogate_step_onset"]["enabled"] = False

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
                "state": "step_R",
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
                "step_onset": 12,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "2",
                "mixed": 1,
            },
        ],
        transpose_meta_rows=[{"subject": "S01", "나이": 24, "주손 or 주발": "R"}],
        name="disabled_surrogate_with_actual_nonstep.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    row = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 1) & (prepared["trial_num"] == 2)].iloc[0]
    assert bool(row["analysis_selected_group"]) is True
    assert bool(row["analysis_is_nonstep"]) is True
    assert float(row["analysis_window_end"]) == pytest.approx(12.0)
    assert row["analysis_window_source"] == "actual_step_onset"
    assert bool(row["analysis_window_is_surrogate"]) is False


def test_event_preparation_step_latency_means_are_per_subject_velocity(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Mean step-onset/latency metadata should not mix across velocities."""
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
                "step_onset": 23,
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
        name="per_velocity_latency_means.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    v1_step = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 1) & (prepared["trial_num"] == 1)].iloc[0]
    v2_step = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 2) & (prepared["trial_num"] == 1)].iloc[0]

    assert float(v1_step["analysis_subject_mean_step_onset"]) == pytest.approx(13.0)
    assert float(v2_step["analysis_subject_mean_step_onset"]) == pytest.approx(23.0)
    assert float(v1_step["analysis_subject_mean_step_latency"]) == pytest.approx(10.0)
    assert float(v2_step["analysis_subject_mean_step_latency"]) == pytest.approx(20.0)


def test_event_preparation_major_step_side_does_not_leak_across_velocities(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Major step side/stance inference should be scoped to (subject, velocity)."""
    cfg = deepcopy(load_pipeline_config(str(fixture_bundle["global_config"])))
    cfg["windowing"]["surrogate_step_onset"]["enabled"] = False

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
                "step_onset": 12,
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
                "step_onset": 22,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "21",
                "mixed": 1,
            },
        ],
        transpose_meta_rows=[{"subject": "S01", "나이": 24, "주손 or 주발": "R"}],
        name="major_side_per_velocity.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    v1_nonstep = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 1) & (prepared["trial_num"] == 2)].iloc[0]
    v2_nonstep = prepared.loc[(prepared["subject"] == "S01") & (prepared["velocity"] == 2) & (prepared["trial_num"] == 1)].iloc[0]

    assert bool(v1_nonstep["analysis_selected_group"]) is True
    assert bool(v2_nonstep["analysis_selected_group"]) is True
    assert v1_nonstep["analysis_major_step_side"] == "step_r"
    assert v1_nonstep["analysis_stance_side"] == "left"
    assert v2_nonstep["analysis_major_step_side"] == ""
    assert v2_nonstep["analysis_stance_side"] == ""
