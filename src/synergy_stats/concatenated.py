"""Build subject-wise concatenated analysis units.

This module stacks selected trials within one
subject, velocity, and step class, runs one NMF,
then splits and averages H back to the trial grid.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from src.emg_pipeline.trials import TrialRecord
from src.synergy_stats.clustering import SubjectFeatureResult
from src.synergy_stats.nmf import FeatureBundle, extract_trial_features


def _sort_key(value: Any) -> tuple[int, Any]:
    if isinstance(value, (int, np.integer)):
        return (0, int(value))
    if isinstance(value, float) and value.is_integer():
        return (0, int(value))
    return (1, str(value))


def _format_id_part(value: Any) -> str:
    return str(value).strip().replace("/", "-").replace("\\", "-").replace(" ", "_")


def _meta_flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if value is None:
        return False
    try:
        if value != value:
            return False
    except Exception:
        pass
    return bool(value)


def split_and_average_h_by_trial(
    concatenated_h: np.ndarray,
    segment_lengths: list[int],
) -> np.ndarray:
    """Split concatenated H by trial and return the per-frame average."""
    h_matrix = np.asarray(concatenated_h, dtype=np.float32)
    if h_matrix.ndim != 2 or h_matrix.shape[0] == 0 or h_matrix.shape[1] == 0:
        raise ValueError("concatenated_h must have shape (frames, components) with non-zero sizes.")
    if not segment_lengths:
        raise ValueError("segment_lengths must contain at least one trial length.")
    if any(int(length) <= 0 for length in segment_lengths):
        raise ValueError("segment_lengths must contain only positive lengths.")
    total_length = sum(int(length) for length in segment_lengths)
    if total_length != int(h_matrix.shape[0]):
        raise ValueError(
            f"Segment lengths sum to {total_length}, but concatenated H has {h_matrix.shape[0]} rows."
        )

    cursor = 0
    segments = []
    for length in segment_lengths:
        next_cursor = cursor + int(length)
        segments.append(h_matrix[cursor:next_cursor, :])
        cursor = next_cursor
    unique_lengths = {int(length) for length in segment_lengths}
    if len(unique_lengths) == 1:
        return np.mean(np.stack(segments, axis=0), axis=0).astype(np.float32)

    target_length = max(unique_lengths)
    aligned_segments = []
    x_new = np.linspace(0.0, 1.0, target_length)
    for segment in segments:
        x_old = np.linspace(0.0, 1.0, segment.shape[0])
        aligned_columns = [
            np.interp(x_new, x_old, segment[:, component_index]).astype(np.float32)
            for component_index in range(segment.shape[1])
        ]
        aligned_segments.append(np.stack(aligned_columns, axis=1))
    return np.mean(np.stack(aligned_segments, axis=0), axis=0).astype(np.float32)


def build_concatenated_feature_rows(
    trial_records: list[TrialRecord],
    muscle_names: list[str],
    cfg: dict[str, Any],
) -> list[SubjectFeatureResult]:
    """Return concatenated subject-level feature rows for selected trials."""
    grouped: dict[tuple[str, Any, str], list[TrialRecord]] = defaultdict(list)
    for trial in trial_records:
        if not _meta_flag(trial.metadata.get("analysis_selected_group", True)):
            continue
        step_class = str(trial.metadata.get("analysis_step_class", "")).strip().lower()
        if step_class not in {"step", "nonstep"}:
            continue
        grouped[(str(trial.key[0]), trial.key[1], step_class)].append(trial)

    feature_rows: list[SubjectFeatureResult] = []
    for (subject, velocity, step_class), trials in sorted(
        grouped.items(),
        key=lambda item: (_sort_key(item[0][0]), _sort_key(item[0][1]), item[0][2]),
    ):
        ordered_trials = sorted(trials, key=lambda trial: _sort_key(trial.key[2]))
        segment_lengths = [len(trial.frame.index) for trial in ordered_trials]
        matrices = [
            trial.frame[muscle_names].to_numpy(dtype=np.float32, copy=True)
            for trial in ordered_trials
        ]
        concatenated_matrix = np.concatenate(matrices, axis=0)
        bundle = extract_trial_features(concatenated_matrix, cfg)
        averaged_h = split_and_average_h_by_trial(bundle.H_time, segment_lengths)
        source_trial_nums = [trial.key[2] for trial in ordered_trials]
        source_trial_nums_csv = "|".join(str(value) for value in source_trial_nums)
        synthetic_trial_num = f"concat_{step_class}"
        analysis_unit_id = (
            f"{_format_id_part(subject)}_v{_format_id_part(velocity)}_{step_class}_concat"
        )
        meta = dict(bundle.meta)
        meta.update(
            {
                "subject": subject,
                "velocity": velocity,
                "trial_num": synthetic_trial_num,
                "aggregation_mode": "concatenated",
                "analysis_unit_id": analysis_unit_id,
                "source_trial_nums_csv": source_trial_nums_csv,
                "analysis_source_trial_count": len(ordered_trials),
                "analysis_h_alignment_method": (
                    "equal_length_average"
                    if len(set(segment_lengths)) == 1
                    else "interpolated_to_max_length"
                ),
                "analysis_selected_group": True,
                "analysis_is_step": step_class == "step",
                "analysis_is_nonstep": step_class == "nonstep",
                "analysis_step_class": step_class,
            }
        )
        feature_rows.append(
            SubjectFeatureResult(
                subject=subject,
                velocity=velocity,
                trial_num=synthetic_trial_num,
                bundle=FeatureBundle(
                    W_muscle=bundle.W_muscle,
                    H_time=averaged_h,
                    meta=meta,
                ),
            )
        )
    return feature_rows
