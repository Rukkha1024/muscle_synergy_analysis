"""Clustering contract scaffolds for strict duplicate handling."""

from __future__ import annotations

import numpy as np
import pytest

from tests.helpers import resolve_callable


def _sample_w_list() -> tuple[list[np.ndarray], list[tuple[str, int, int]]]:
    """Build per-trial W matrices with clear cross-trial cluster families."""
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    c = np.array([0.9, 0.1, 0.0], dtype=np.float32)
    d = np.array([0.1, 0.9, 0.0], dtype=np.float32)
    w_list = [
        np.stack([a, b], axis=1),
        np.stack([c, d], axis=1),
        np.stack([a, d], axis=1),
    ]
    trial_keys = [("S01", 1, 1), ("S01", 1, 2), ("S01", 2, 1)]
    return w_list, trial_keys


def test_strict_duplicate_policy_returns_zero_duplicate_solution() -> None:
    """Strict clustering should not assign the same cluster twice within one trial."""
    try:
        cluster_func, module_name, attr_name = resolve_callable(
            [
                "src.synergy_stats",
                "src.synergy_stats.clustering",
                "src.synergy_stats.pipeline",
            ],
            [
                "cluster_intra_subject",
                "run_intra_subject_clustering",
                "_cluster_intra_subject",
            ],
        )
    except LookupError as exc:
        pytest.xfail(f"Clustering callable is not implemented yet: {exc}")

    w_list, trial_keys = _sample_w_list()
    cfg = {
        "algorithm": "cuml_kmeans",
        "max_clusters": 4,
        "max_iter": 50,
        "repeats": 5,
        "random_state": 7,
        "disallow_within_trial_duplicate_assignment": True,
    }
    result = cluster_func(w_list, trial_keys, cfg)
    assert isinstance(result, dict), f"{module_name}.{attr_name} should return a dict."
    assert result.get("status") == "success"
    assert len(result.get("duplicate_trials", [])) == 0
    assert len(result.get("labels", [])) == sum(w.shape[1] for w in w_list)
