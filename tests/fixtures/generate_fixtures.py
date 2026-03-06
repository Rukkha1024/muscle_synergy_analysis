"""Generate deterministic EMG fixture files for pytest scenarios."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl


MUSCLES = ["TA", "MG", "SOL", "RF"]
FRAME_RATIO = 10


def _trial_signal(trial_seed: int, n_frames: int = 20) -> np.ndarray:
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


def _build_emg_table() -> pl.DataFrame:
    """Build a small EMG table covering two subjects and four trials each."""
    rows: list[dict[str, object]] = []
    for subject_idx, subject in enumerate(["S01", "S02"], start=1):
        for velocity in [1, 2]:
            for trial_num in [1, 2]:
                trial_seed = subject_idx * 10 + velocity * 2 + trial_num
                trial_signal = _trial_signal(trial_seed)
                for mocap_frame in range(trial_signal.shape[0]):
                    row = {
                        "subject": subject,
                        "velocity": velocity,
                        "trial_num": trial_num,
                        "MocapFrame": mocap_frame,
                        "original_DeviceFrame": mocap_frame * FRAME_RATIO,
                    }
                    for muscle_idx, muscle in enumerate(MUSCLES):
                        row[muscle] = float(trial_signal[mocap_frame, muscle_idx])
                    rows.append(row)
    return pl.DataFrame(rows)


def _build_event_table() -> pd.DataFrame:
    """Build trial-level event metadata in the MocapFrame domain."""
    rows = []
    for subject in ["S01", "S02"]:
        for velocity in [1, 2]:
            for trial_num in [1, 2]:
                rows.append(
                    {
                        "subject": subject,
                        "velocity": velocity,
                        "trial_num": trial_num,
                        "platform_onset": 3,
                        "platform_offset": 14,
                        "step_onset": 11,
                    }
                )
    return pd.DataFrame(rows)


def _write_yaml(path: Path, payload: str) -> None:
    """Write a UTF-8 BOM YAML file."""
    path.write_text(payload, encoding="utf-8-sig")


def ensure_fixture_bundle(base_dir: Path) -> dict[str, Path]:
    """Create fixture data files and return their resolved paths."""
    base_dir.mkdir(parents=True, exist_ok=True)
    emg_df = _build_emg_table()
    event_df = _build_event_table()

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
                "  offset_column: platform_offset",
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
                "    vaf_threshold: 0.9",
                "    max_components_to_try: 4",
                "    fit_params:",
                "      max_iter: 1000",
                "      tol: 0.0001",
                "synergy_clustering:",
                "  algorithm: cuml_kmeans",
                "  max_clusters: 4",
                "  max_iter: 100",
                "  repeats: 10",
                "  random_state: 7",
                "  disallow_within_trial_duplicate_assignment: true",
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
