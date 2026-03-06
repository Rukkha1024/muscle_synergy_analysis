"""Create per-trial EMG slices and aligned time axes."""

from __future__ import annotations

import logging

from src.emg_pipeline import build_trial_records


def run(context: dict) -> dict:
    trial_records = build_trial_records(context["emg_df"], context["config"])
    context["trial_records"] = trial_records
    logging.info("Prepared %s trial slices.", len(trial_records))
    return context
