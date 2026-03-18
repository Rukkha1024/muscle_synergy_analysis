"""Event preparation contract tests for mixed-window selection.

These tests focus on the event workbook rules that select mixed
comparison groups and derive surrogate nonstep step-onset values.
"""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy

import numpy as np
import pandas as pd
import polars as pl
import pytest

from src.emg_pipeline import load_event_metadata, load_pipeline_config
from src.emg_pipeline import io as io_module


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


def test_event_preparation_keeps_donorless_nonstep_rows_by_using_platform_offset(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Donorless nonstep rows should remain selected and use platform_offset as the window end."""
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
    assert invalid_rows["analysis_selected_group"].any()
    assert invalid_rows["analysis_is_nonstep"].any()
    invalid_nonstep = invalid_rows.loc[invalid_rows["analysis_is_nonstep"]].iloc[0]
    assert invalid_nonstep["analysis_window_source"] == "platform_offset"
    assert bool(invalid_nonstep["analysis_window_is_surrogate"]) is False
    assert float(invalid_nonstep["analysis_window_end"]) == pytest.approx(float(invalid_nonstep["platform_offset"]))


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


def test_event_preparation_falls_back_to_transpose_meta_when_meta_missing(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """If the `meta` sheet is absent, subject metadata should fall back to transpose_meta."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    workbook_path = tmp_path / "fallback_transpose_meta.xlsx"
    platform_rows = [
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
            "step_onset": np.nan,
            "state": "nonstep",
            "step_TF": "nonstep",
            "RPS": "2",
            "mixed": 1,
        },
    ]
    transpose_meta_rows = [{"subject": "S01", "나이": 24, "주손 or 주발": "R"}]
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame(platform_rows).to_excel(writer, sheet_name="platform", index=False)
        pd.DataFrame(transpose_meta_rows).to_excel(writer, sheet_name="transpose_meta", index=False)

    prepared = load_event_metadata(str(workbook_path), cfg)
    assert prepared["analysis_selected_group"].any()


def test_event_preparation_falls_back_to_transpose_meta_when_meta_is_malformed(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """A malformed `meta` sheet should fall back to transpose_meta when available."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    workbook_path = tmp_path / "fallback_transpose_meta_when_meta_malformed.xlsx"
    platform_rows = [
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
            "step_onset": np.nan,
            "state": "nonstep",
            "step_TF": "nonstep",
            "RPS": "2",
            "mixed": 1,
        },
    ]
    malformed_meta = pd.DataFrame({"subject": ["foo", "bar"], "S01": ["x", "y"]})
    transpose_meta_rows = [{"subject": "S01", "나이": 24, "주손 or 주발": "R"}]
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame(platform_rows).to_excel(writer, sheet_name="platform", index=False)
        malformed_meta.to_excel(writer, sheet_name="meta", index=False)
        pd.DataFrame(transpose_meta_rows).to_excel(writer, sheet_name="transpose_meta", index=False)

    prepared = load_event_metadata(str(workbook_path), cfg)
    assert prepared["analysis_selected_group"].any()


def test_event_preparation_ignores_fully_blank_platform_rows(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Fully blank platform rows should be ignored instead of failing metadata joins."""
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
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "2",
                "mixed": 1,
            },
            {
                "subject": np.nan,
                "velocity": np.nan,
                "trial": np.nan,
                "platform_onset": np.nan,
                "platform_offset": np.nan,
                "step_onset": np.nan,
                "state": np.nan,
                "step_TF": np.nan,
                "RPS": np.nan,
                "mixed": np.nan,
            },
        ],
        transpose_meta_rows=[{"subject": "S01", "나이": 24, "주손 or 주발": "R"}],
        name="blank_platform_rows.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    assert prepared["subject"].notna().all()
    assert prepared["subject"].astype(str).str.strip().ne("").all()
    assert prepared.shape[0] == 2
    assert prepared["analysis_selected_group"].any()


def test_event_preparation_ignores_platform_rows_with_unusable_merge_keys(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Rows without mergeable velocity/trial keys should be dropped as workbook noise."""
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
                "step_onset": np.nan,
                "state": "nonstep",
                "step_TF": "nonstep",
                "RPS": "2",
                "mixed": 1,
            },
            {
                "subject": "S99",
                "velocity": "?",
                "trial": "?",
                "platform_onset": np.nan,
                "platform_offset": np.nan,
                "step_onset": np.nan,
                "state": np.nan,
                "step_TF": np.nan,
                "RPS": np.nan,
                "mixed": np.nan,
            },
        ],
        transpose_meta_rows=[{"subject": "S01", "나이": 24, "주손 or 주발": "R"}],
        name="invalid_platform_keys.xlsx",
    )

    prepared = load_event_metadata(str(path), cfg)
    assert set(prepared["subject"].tolist()) == {"S01"}
    assert prepared.shape[0] == 2
    assert prepared["analysis_selected_group"].any()


def test_platform_loader_parses_excel_fallback_numeric_strings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Excel fallback string values like `1.0` should still load as numeric merge keys."""
    workbook_path = tmp_path / "string_numeric_platform.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame(
            [{"subject": "S01", "velocity": 1, "trial": 1, "state": "step_R", "step_TF": "step", "mixed": 1}]
        ).to_excel(writer, sheet_name="platform", index=False)
        _transpose_meta_rows_to_meta_sheet([{"subject": "S01", "나이": 24, "주손 or 주발": "R"}]).to_excel(
            writer,
            sheet_name="meta",
            index=False,
        )

    original_safe_read_excel = io_module._safe_read_excel

    def _fake_safe_read_excel(path: Path, *, sheet_name: str | int | None = None) -> pl.DataFrame:
        if sheet_name == "platform":
            return pl.DataFrame(
                {
                    "subject": ["S01"],
                    "velocity": ["1.0"],
                    "trial": ["1.0"],
                    "state": ["step_R"],
                    "step_TF": ["step"],
                    "RPS": ["1"],
                    "mixed": ["1.0"],
                    "platform_onset": ["3.0"],
                    "platform_offset": ["18.0"],
                    "step_onset": ["11.0"],
                }
            )
        return original_safe_read_excel(path, sheet_name=sheet_name)

    monkeypatch.setattr(io_module, "_safe_read_excel", _fake_safe_read_excel)

    loaded = io_module._load_platform_with_subject_meta(workbook_path)
    assert loaded.shape[0] == 1
    assert loaded.loc[0, "velocity"] == pytest.approx(1.0)
    assert int(loaded.loc[0, "trial_num"]) == 1


def test_event_preparation_raises_when_subject_meta_is_missing(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Missing required subject meta fields should fail-fast to avoid silent cohort loss."""
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
                "state": "step_R",
                "step_TF": "step",
                "RPS": "1",
                "mixed": 1,
            }
        ],
        transpose_meta_rows=[{"subject": "S99", "나이": 24, "주손 or 주발": "R"}],
        name="missing_subject_meta.xlsx",
    )

    with pytest.raises(ValueError, match="Missing subject meta"):
        load_event_metadata(str(path), cfg)


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
