"""Generate deterministic fixture inputs for windowed synergy tests.

The fixtures model mixed step/nonstep comparison groups, surrogate
nonstep end points, and a second velocity that should be filtered out
by the mixed-comparison selection rule.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl


MUSCLES = ["TA", "MG", "SOL", "RF"]
FRAME_RATIO = 10
N_FRAMES = 24


def _trial_signal(trial_seed: int, n_frames: int = N_FRAMES) -> np.ndarray:
    """Return a smooth nonnegative trial matrix shaped (frames, muscles)."""
    t = np.linspace(0.0, 1.0, n_frames, dtype=np.float32)
    basis = np.stack(
        [
            1.2 + 0.4 * np.sin(2.0 * np.pi * t),
            0.9 + 0.3 * np.cos(2.0 * np.pi * t),
            0.7 + 0.5 * t,
            0.6 + 0.4 * (1.0 - t),
        ],
        axis=1,
    )
    weights = np.array(
        [
            [0.80, 0.20, 0.10, 0.05],
            [0.15, 0.75, 0.20, 0.10],
            [0.10, 0.15, 0.70, 0.30],
            [0.05, 0.10, 0.15, 0.80],
        ],
        dtype=np.float32,
    )
    signal = basis @ weights
    signal += np.float32(trial_seed) * 0.02
    return np.maximum(signal.astype(np.float32), 0.0)


def _event_rows_for_subject(subject: str) -> list[dict[str, object]]:
    """Build two velocity groups: one valid mixed set and one filtered-out set."""
    return [
        {
            "subject": subject,
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
            "subject": subject,
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
            "subject": subject,
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
            "subject": subject,
            "velocity": 1,
            "trial_num": 4,
            "platform_onset": 3,
            "platform_offset": 18,
            "step_onset": np.nan,
            "state": "footlift",
            "step_TF": "nonstep",
            "RPS": "4",
            "mixed": 1,
        },
        {
            "subject": subject,
            "velocity": 2,
            "trial_num": 1,
            "platform_onset": 3,
            "platform_offset": 18,
            "step_onset": 10,
            "state": "step_L",
            "step_TF": "step",
            "RPS": "5",
            "mixed": 0,
        },
        {
            "subject": subject,
            "velocity": 2,
            "trial_num": 2,
            "platform_onset": 3,
            "platform_offset": 18,
            "step_onset": 12,
            "state": "step_R",
            "step_TF": "step",
            "RPS": "6",
            "mixed": 0,
        },
        {
            "subject": subject,
            "velocity": 2,
            "trial_num": 3,
            "platform_onset": 3,
            "platform_offset": 18,
            "step_onset": 14,
            "state": "step_L",
            "step_TF": "step",
            "RPS": "7",
            "mixed": 0,
        },
        {
            "subject": subject,
            "velocity": 2,
            "trial_num": 4,
            "platform_onset": 3,
            "platform_offset": 18,
            "step_onset": 15,
            "state": "step_R",
            "step_TF": "step",
            "RPS": "8",
            "mixed": 0,
        },
    ]


def _build_emg_table(event_rows: list[dict[str, object]]) -> pl.DataFrame:
    """Build EMG rows that mirror the event-table trial structure."""
    rows: list[dict[str, object]] = []
    for subject_idx, event_row in enumerate(event_rows, start=1):
        trial_seed = subject_idx * 10 + int(event_row["velocity"]) * 2 + int(event_row["trial_num"])
        trial_signal = _trial_signal(trial_seed)
        for mocap_frame in range(trial_signal.shape[0]):
            row = {
                "subject": event_row["subject"],
                "velocity": event_row["velocity"],
                "trial_num": event_row["trial_num"],
                "MocapFrame": mocap_frame,
                "original_DeviceFrame": mocap_frame * FRAME_RATIO,
            }
            for muscle_idx, muscle in enumerate(MUSCLES):
                row[muscle] = float(trial_signal[mocap_frame, muscle_idx])
            rows.append(row)
    return pl.DataFrame(rows)


def _build_event_table() -> pd.DataFrame:
    """Build trial-level event metadata in the MocapFrame domain."""
    rows: list[dict[str, object]] = []
    for subject in ["S01", "S02"]:
        rows.extend(_event_rows_for_subject(subject))
    return pd.DataFrame(rows)


def _write_yaml(path: Path, payload: str) -> None:
    """Write a UTF-8 BOM YAML file."""
    path.write_text(payload, encoding="utf-8-sig")


def ensure_fixture_bundle(base_dir: Path) -> dict[str, Path]:
    """Create fixture data files and return their resolved paths."""
    base_dir.mkdir(parents=True, exist_ok=True)
    event_df = _build_event_table()
    emg_df = _build_emg_table(event_df.to_dict(orient="records"))

    parquet_path = base_dir / "emg_fixture.parquet"
    csv_path = base_dir / "emg_fixture.csv"
    xlsm_path = base_dir / "perturb_inform_fixture.xlsm"
    global_config_path = base_dir / "global_config.yaml"
    emg_config_path = base_dir / "emg_pipeline_config.yaml"
    synergy_config_path = base_dir / "synergy_stats_config.yaml"

    emg_df.write_parquet(parquet_path)
    emg_df.to_pandas().to_csv(csv_path, index=False, encoding="utf-8-sig")
    event_df.to_excel(xlsm_path, index=False, engine="openpyxl")

    _write_yaml(
        emg_config_path,
        "\n".join(
            [
                "muscles:",
                f"  names: {MUSCLES}",
                "windowing:",
                f"  mocap_to_device_ratio: {FRAME_RATIO}",
                "  onset_column: platform_onset",
                "  offset_column: analysis_window_end",
                "  selection:",
                "    mixed_only: true",
                "    mixed_column: mixed",
                "    require_total_trials: 4",
                "    require_step_trials: 2",
                "    require_nonstep_trials: 2",
                "    single_velocity_per_subject: true",
                "  surrogate_step_onset:",
                "    enabled: true",
                "    source_column: step_onset",
                "    output_column: analysis_window_end",
                "    step_class_column: step_TF",
                "    step_value: step",
                "    nonstep_value: nonstep",
                "  stance_metadata:",
                "    state_column: state",
                "",
            ]
        ),
    )
    _write_yaml(
        synergy_config_path,
        "\n".join(
            [
                "feature_extractor:",
                "  type: nmf",
                "  nmf:",
                "    backend: sklearn_nmf",
                "    vaf_threshold: 0.9",
                "    max_components_to_try: 4",
                "    fit_params:",
                "      max_iter: 1000",
                "      tol: 0.0001",
                "synergy_clustering:",
                "  algorithm: sklearn_kmeans",
                "  max_clusters: 4",
                "  max_iter: 100",
                "  repeats: 10",
                "  random_state: 7",
                "  disallow_within_trial_duplicate_assignment: true",
                "  representative:",
                "    h_output_interpolation:",
                "      target_windows: 100",
                "figures:",
                "  format: png",
                "  dpi: 120",
                "  overview_columns: 2",
                "",
            ]
        ),
    )
    _write_yaml(
        global_config_path,
        "\n".join(
            [
                "input:",
                f"  emg_parquet_path: {parquet_path.as_posix()}",
                f"  event_xlsm_path: {xlsm_path.as_posix()}",
                "runtime:",
                "  gpu_required: false",
                "  seed: 7",
                "  output_dir: outputs/runs/fixture_run",
                "  log_dir: outputs/manifests",
                "configs:",
                f"  emg_pipeline: {emg_config_path.as_posix()}",
                f"  synergy_stats: {synergy_config_path.as_posix()}",
                "",
            ]
        ),
    )

    return {
        "parquet": parquet_path,
        "csv": csv_path,
        "xlsm": xlsm_path,
        "global_config": global_config_path,
        "emg_config": emg_config_path,
        "synergy_config": synergy_config_path,
    }
