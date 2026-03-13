"""Regression tests for duplicate-assignment enforcement."""

from __future__ import annotations

from collections import Counter

import numpy as np

from src.synergy_stats.clustering import _enforce_unique_trial_labels


def _trial_duplicate_count(labels: np.ndarray) -> int:
    """Count excess duplicate labels within one trial."""
    counts = Counter(int(value) for value in np.asarray(labels, dtype=np.int32).tolist())
    return int(sum(max(count - 1, 0) for count in counts.values()))


def test_enforce_unique_trial_labels_removes_same_trial_duplicates() -> None:
    """A duplicated trial assignment should become unique when K is sufficient."""
    data = np.asarray(
        [
            [1.00, 0.00, 0.00],
            [0.98, 0.02, 0.00],
            [0.00, 1.00, 0.00],
            [0.00, 0.00, 1.00],
        ],
        dtype=np.float32,
    )
    sample_map = [
        {
            "subject": "S01",
            "velocity": 1.0,
            "trial_num": 1,
            "trial_key": ("S01", 1.0, 1),
            "trial_id": "S01_v1.0_T1",
            "component_index": 0,
        },
        {
            "subject": "S01",
            "velocity": 1.0,
            "trial_num": 1,
            "trial_key": ("S01", 1.0, 1),
            "trial_id": "S01_v1.0_T1",
            "component_index": 1,
        },
        {
            "subject": "S02",
            "velocity": 1.0,
            "trial_num": 1,
            "trial_key": ("S02", 1.0, 1),
            "trial_id": "S02_v1.0_T1",
            "component_index": 0,
        },
        {
            "subject": "S03",
            "velocity": 1.0,
            "trial_num": 1,
            "trial_key": ("S03", 1.0, 1),
            "trial_id": "S03_v1.0_T1",
            "component_index": 0,
        },
    ]
    raw_labels = np.asarray([0, 0, 1, 2], dtype=np.int32)

    repaired = _enforce_unique_trial_labels(data, sample_map, raw_labels, n_clusters=3)

    assert _trial_duplicate_count(raw_labels[:2]) == 1
    assert _trial_duplicate_count(repaired[:2]) == 0
    assert len(set(repaired[:2].tolist())) == 2


def test_enforce_unique_trial_labels_keeps_unique_trials_stable() -> None:
    """Already unique labels should remain unchanged."""
    data = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    sample_map = [
        {
            "subject": "S01",
            "velocity": 1.0,
            "trial_num": 1,
            "trial_key": ("S01", 1.0, 1),
            "trial_id": "S01_v1.0_T1",
            "component_index": 0,
        },
        {
            "subject": "S01",
            "velocity": 1.0,
            "trial_num": 1,
            "trial_key": ("S01", 1.0, 1),
            "trial_id": "S01_v1.0_T1",
            "component_index": 1,
        },
        {
            "subject": "S02",
            "velocity": 1.0,
            "trial_num": 1,
            "trial_key": ("S02", 1.0, 1),
            "trial_id": "S02_v1.0_T1",
            "component_index": 0,
        },
    ]
    raw_labels = np.asarray([0, 1, 2], dtype=np.int32)

    repaired = _enforce_unique_trial_labels(data, sample_map, raw_labels, n_clusters=3)

    assert repaired.tolist() == raw_labels.tolist()
