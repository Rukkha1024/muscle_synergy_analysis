"""Load EMG and metadata tables with polars-first I/O."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl


def load_emg_table(parquet_path: str) -> pd.DataFrame:
    path = Path(parquet_path)
    if not path.exists():
        raise FileNotFoundError(f"EMG parquet not found: {path}")
    table = pl.read_parquet(path)
    required = {"subject", "velocity", "trial_num"}
    missing = sorted(required.difference(set(table.columns)))
    if missing:
        raise ValueError(f"Missing required EMG columns: {missing}")
    return table.to_pandas(use_pyarrow_extension_array=False)


def load_event_metadata(xlsm_path: str) -> pd.DataFrame:
    path = Path(xlsm_path)
    if not path.exists():
        raise FileNotFoundError(f"Event workbook not found: {path}")
    table = pd.read_excel(path, engine="openpyxl")
    if "trial" in table.columns and "trial_num" not in table.columns:
        table = table.rename(columns={"trial": "trial_num"})
    required = {"subject", "velocity", "trial_num", "platform_onset", "platform_offset"}
    missing = sorted(required.difference(set(table.columns)))
    if missing:
        raise ValueError(f"Missing required event columns: {missing}")
    return table


def merge_event_metadata(emg_df: pd.DataFrame, event_df: pd.DataFrame) -> pd.DataFrame:
    base_keys = ["subject", "velocity", "trial_num"]
    merged = emg_df.copy()
    override_columns = [column for column in event_df.columns if column not in base_keys]
    merged = merged.drop(columns=[column for column in override_columns if column in merged.columns], errors="ignore")
    return merged.merge(event_df, on=base_keys, how="left")
