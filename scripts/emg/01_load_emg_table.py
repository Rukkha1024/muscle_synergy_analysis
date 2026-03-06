"""Load the EMG parquet and event workbook into pipeline context."""

from __future__ import annotations

import logging

from src.emg_pipeline import load_emg_table, load_event_metadata, merge_event_metadata


def run(context: dict) -> dict:
    cfg = context["config"]
    emg_df = load_emg_table(cfg["input"]["emg_parquet_path"])
    event_df = load_event_metadata(cfg["input"]["event_xlsm_path"], cfg)
    merged = merge_event_metadata(emg_df, event_df)
    context["emg_df"] = merged
    logging.info("Loaded EMG rows=%s, merged columns=%s", len(merged), len(merged.columns))
    return context
