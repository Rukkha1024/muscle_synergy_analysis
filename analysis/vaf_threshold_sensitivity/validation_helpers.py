"""Helpers for VAF validity checks in the threshold sensitivity analysis.

This module computes local VAF summaries, source-trial-safe null data,
and fixed-W reconstructions used by hold-out and cross-condition checks.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np


def compute_local_vaf(
    x: np.ndarray,
    x_hat: np.ndarray,
    variance_epsilon: float,
    *,
    channel_names: list[str] | None = None,
    local_vaf_floor: float | None = None,
) -> dict[str, Any]:
    """Return per-channel local VAF values and one-unit summary stats."""
    observed = np.asarray(x, dtype=np.float64)
    reconstructed = np.asarray(x_hat, dtype=np.float64)
    if observed.shape != reconstructed.shape:
        raise ValueError(
            f"x and x_hat must share the same shape (got {observed.shape!r} vs {reconstructed.shape!r})."
        )
    if observed.ndim != 2 or observed.shape[0] == 0 or observed.shape[1] == 0:
        raise ValueError("x and x_hat must be non-empty 2D arrays.")

    resolved_names = channel_names or [f"channel_{index}" for index in range(observed.shape[1])]
    if len(resolved_names) != observed.shape[1]:
        raise ValueError("channel_names must match the number of channels.")

    channel_rows: list[dict[str, Any]] = []
    applicable_values: list[float] = []
    for channel_index, muscle_name in enumerate(resolved_names):
        target = observed[:, channel_index]
        fitted = reconstructed[:, channel_index]
        total_ss = float(np.sum(target**2))
        if total_ss <= float(variance_epsilon):
            channel_rows.append(
                {
                    "channel_index": int(channel_index),
                    "muscle": str(muscle_name),
                    "local_vaf": None,
                    "status": "not_applicable",
                    "pass_floor": None,
                    "is_worst_muscle": False,
                }
            )
            continue

        residual_ss = float(np.sum((target - fitted) ** 2))
        local_vaf = float(1.0 - (residual_ss / total_ss))
        applicable_values.append(local_vaf)
        pass_floor = None if local_vaf_floor is None else bool(local_vaf >= float(local_vaf_floor))
        channel_rows.append(
            {
                "channel_index": int(channel_index),
                "muscle": str(muscle_name),
                "local_vaf": local_vaf,
                "status": "ok",
                "pass_floor": pass_floor,
                "is_worst_muscle": False,
            }
        )

    if applicable_values:
        worst_value = min(applicable_values)
        for row in channel_rows:
            if row["local_vaf"] is not None and np.isclose(float(row["local_vaf"]), float(worst_value)):
                row["is_worst_muscle"] = True

    pass_values = [bool(row["pass_floor"]) for row in channel_rows if row["pass_floor"] is not None]
    return {
        "n_channels": int(observed.shape[1]),
        "n_applicable_channels": int(len(applicable_values)),
        "n_not_applicable_channels": int(observed.shape[1] - len(applicable_values)),
        "muscle_pass_rate": (
            float(sum(pass_values) / len(pass_values))
            if pass_values
            else None
        ),
        "all_muscles_pass": bool(all(pass_values)) if pass_values else None,
        "min_local_vaf": float(min(applicable_values)) if applicable_values else None,
        "median_local_vaf": (
            float(np.median(np.asarray(applicable_values, dtype=np.float64)))
            if applicable_values
            else None
        ),
        "channel_rows": channel_rows,
    }


def generate_null_trial(x: np.ndarray, method: str, rng: np.random.Generator) -> np.ndarray:
    """Generate one null trial without crossing the source-trial boundary."""
    observed = np.asarray(x, dtype=np.float32)
    if observed.ndim != 2 or observed.shape[0] == 0 or observed.shape[1] == 0:
        raise ValueError("x must be a non-empty 2D array.")
    method_name = str(method).strip().lower()
    if method_name not in {"circular_shift", "time_shuffle"}:
        raise ValueError(f"Unsupported null method: {method}")
    if observed.shape[0] == 1:
        return observed.copy()

    null_trial = np.empty_like(observed)
    for channel_index in range(observed.shape[1]):
        column = observed[:, channel_index]
        if method_name == "circular_shift":
            shift = int(rng.integers(0, observed.shape[0]))
            null_trial[:, channel_index] = np.roll(column, shift)
        else:
            order = rng.permutation(observed.shape[0])
            null_trial[:, channel_index] = column[order]
    return null_trial.astype(np.float32, copy=False)


def solve_h_fixed_w(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Estimate H with non-negative least squares while W stays fixed."""
    try:
        from scipy.optimize import nnls
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent.
        raise ModuleNotFoundError("scipy is required for fixed-W NNLS reconstruction.") from exc

    observed = np.asarray(x, dtype=np.float64)
    weights = np.asarray(w, dtype=np.float64)
    if observed.ndim != 2 or weights.ndim != 2:
        raise ValueError("x and w must both be 2D arrays.")
    if observed.shape[1] != weights.shape[0]:
        raise ValueError(
            f"x has {observed.shape[1]} channels, but w has {weights.shape[0]} rows."
        )

    activations = np.empty((observed.shape[0], weights.shape[1]), dtype=np.float64)
    for frame_index in range(observed.shape[0]):
        activations[frame_index, :] = nnls(weights, observed[frame_index, :])[0]
    return activations.astype(np.float32)


def reconstruct_with_fixed_w(x: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the fixed-W NNLS activation estimate and reconstruction."""
    h_time = solve_h_fixed_w(x, w)
    x_hat = np.asarray(h_time @ np.asarray(w, dtype=np.float32).T, dtype=np.float32)
    return h_time, x_hat


def split_concatenated_trial_matrix(x: np.ndarray, source_lengths: list[int]) -> list[np.ndarray]:
    """Split one concatenated matrix back into its source-trial matrices."""
    observed = np.asarray(x, dtype=np.float32)
    if observed.ndim != 2 or observed.shape[0] == 0:
        raise ValueError("x must be a non-empty 2D array.")
    if not source_lengths:
        raise ValueError("source_lengths must not be empty.")
    total_length = int(sum(int(length) for length in source_lengths))
    if total_length != int(observed.shape[0]):
        raise ValueError(
            f"source_lengths sum to {total_length}, but x has {observed.shape[0]} rows."
        )

    cursor = 0
    slices: list[np.ndarray] = []
    for length in source_lengths:
        length_int = int(length)
        if length_int <= 0:
            raise ValueError("source_lengths must contain only positive values.")
        next_cursor = cursor + length_int
        slices.append(observed[cursor:next_cursor, :].copy())
        cursor = next_cursor
    return slices


def _summarize_local_vaf_rows(
    rows: list[dict[str, Any]],
    *,
    local_vaf_floor: float,
) -> dict[str, Any]:
    applicable_rows = [row for row in rows if row.get("local_vaf") is not None]
    local_values = [float(row["local_vaf"]) for row in applicable_rows]
    unit_ids = sorted({str(row["unit_id"]) for row in rows if row.get("unit_id") is not None})
    unit_pass_lookup: dict[str, bool | None] = {}
    for unit_id in unit_ids:
        unit_rows = [row for row in rows if str(row.get("unit_id")) == unit_id and row.get("local_vaf") is not None]
        if not unit_rows:
            unit_pass_lookup[unit_id] = None
            continue
        unit_pass_lookup[unit_id] = all(float(row["local_vaf"]) >= float(local_vaf_floor) for row in unit_rows)

    worst_counter = Counter(
        str(row["muscle"])
        for row in applicable_rows
        if bool(row.get("is_worst_muscle"))
    )
    worst_frequency = [
        {
            "muscle": muscle,
            "count": int(count),
            "rate": float(count / len(unit_ids)) if unit_ids else None,
        }
        for muscle, count in worst_counter.most_common()
    ]

    all_pass_values = [value for value in unit_pass_lookup.values() if value is not None]
    return {
        "analysis_unit_count": int(len(unit_ids)),
        "channel_row_count": int(len(rows)),
        "applicable_channel_count": int(len(applicable_rows)),
        "not_applicable_channel_count": int(len(rows) - len(applicable_rows)),
        "muscle_pass_rate_75": (
            float(sum(float(value) >= float(local_vaf_floor) for value in local_values) / len(local_values))
            if local_values
            else None
        ),
        "all_muscles_pass_rate_75": (
            float(sum(bool(value) for value in all_pass_values) / len(all_pass_values))
            if all_pass_values
            else None
        ),
        "min_local_vaf": float(min(local_values)) if local_values else None,
        "median_local_vaf": (
            float(np.median(np.asarray(local_values, dtype=np.float64)))
            if local_values
            else None
        ),
        "worst_muscle_frequency": worst_frequency,
    }


def summarize_subject_muscle_channel_local_vaf(
    local_vaf_by_supertrial: list[dict[str, Any]],
    *,
    local_vaf_floor: float,
) -> dict[str, Any]:
    """Summarize concatenated primary local VAF rows."""
    return _summarize_local_vaf_rows(
        local_vaf_by_supertrial,
        local_vaf_floor=float(local_vaf_floor),
    )


def summarize_source_trial_split_local_vaf(
    local_vaf_by_split_trial: list[dict[str, Any]],
    *,
    local_vaf_floor: float,
) -> dict[str, Any]:
    """Summarize concatenated source-trial-split local VAF rows."""
    return _summarize_local_vaf_rows(
        local_vaf_by_split_trial,
        local_vaf_floor=float(local_vaf_floor),
    )
