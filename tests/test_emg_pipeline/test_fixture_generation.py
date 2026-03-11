"""Fixture generation contract tests."""

from __future__ import annotations

import pandas as pd
import polars as pl


def test_fixture_bundle_contains_expected_files(fixture_bundle: dict[str, object]) -> None:
    """Synthetic fixture generation writes the expected reusable inputs."""
    for path in fixture_bundle.values():
        assert path.exists(), f"Fixture file was not created: {path}"


def test_emg_fixture_schema(fixture_bundle: dict[str, object]) -> None:
    """EMG parquet keeps the expected trial and muscle schema."""
    df = pl.read_parquet(fixture_bundle["parquet"])
    required = {"subject", "velocity", "trial_num", "MocapFrame", "original_DeviceFrame"}
    assert required.issubset(df.columns)
    assert {"TA", "MG", "SOL", "RF"}.issubset(df.columns)
    assert df.select(pl.len()).item() == 384


def test_event_fixture_schema(fixture_bundle: dict[str, object]) -> None:
    """Event workbook stores the trial-level onset and offset contract."""
    platform = pd.read_excel(fixture_bundle["xlsm"], sheet_name="platform")
    assert set(["subject", "velocity", "trial"]).issubset(platform.columns)
    assert set(["platform_onset", "platform_offset", "step_onset", "step_TF", "state", "mixed"]).issubset(platform.columns)
    assert platform["platform_onset"].nunique() == 1

    meta = pd.read_excel(fixture_bundle["xlsm"], sheet_name="meta")
    assert "subject" in meta.columns
    assert {"S01", "S02"}.issubset(set(meta.columns))
    fields = set(meta["subject"].astype(str).str.strip().tolist())
    assert set(["나이", "주손 or 주발"]).issubset(fields)
