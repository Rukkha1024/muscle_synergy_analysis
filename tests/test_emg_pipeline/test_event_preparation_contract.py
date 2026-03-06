"""Event preparation contract tests for mixed-window selection.

These tests focus on the event workbook rules that select mixed
comparison groups and derive surrogate nonstep step-onset values.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.emg_pipeline import load_event_metadata, load_pipeline_config


def test_event_preparation_fails_without_step_donor(
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """A mixed group without valid step donors should fail early."""
    cfg = load_pipeline_config(str(fixture_bundle["global_config"]))
    invalid_df = pd.DataFrame(
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
        ]
    )
    invalid_path = tmp_path / "invalid_events.xlsx"
    invalid_df.to_excel(invalid_path, index=False, engine="openpyxl")

    with pytest.raises(ValueError, match="No valid mixed-velocity groups remain after event filtering"):
        load_event_metadata(str(invalid_path), cfg)
