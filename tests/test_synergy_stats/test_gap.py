"""Unit tests for shared gap-statistic helpers."""

from __future__ import annotations

import numpy as np

from src.synergy_stats.gap import (
    compute_gap_statistic,
    sample_uniform_reference_within_bounds,
    select_k_by_first_se_rule,
)


def test_select_k_by_first_se_rule_returns_smallest_acceptable_k() -> None:
    k_values = [2, 3, 4]
    gap_by_k = {2: 1.25, 3: 1.20, 4: 0.90}
    gap_sd_by_k = {2: 0.10, 3: 0.08, 4: 0.05}

    assert select_k_by_first_se_rule(k_values, gap_by_k, gap_sd_by_k) == 2


def test_compute_gap_statistic_returns_expected_selection_with_stub_fit() -> None:
    data = np.array(
        [
            [0.0, 0.0],
            [0.0, 1.0],
            [5.0, 5.0],
            [5.0, 6.0],
            [10.0, 10.0],
            [10.0, 11.0],
        ],
        dtype=np.float64,
    )

    def _stub_fit(fit_data: np.ndarray, k: int, repeats: int, seed: int):
        labels = np.arange(fit_data.shape[0], dtype=np.int32) % k
        objective = 80.0 if fit_data is data and k == 2 else 100.0 if fit_data is data and k == 3 else 300.0 + float(k)
        return {
            "labels": labels,
            "objective": float(objective),
            "seed_used": int(seed),
            "repeats_used": int(repeats),
        }

    result = compute_gap_statistic(
        data=data,
        k_values=[2, 3],
        fit_best_fn=_stub_fit,
        observed_restarts=5,
        gap_ref_n=3,
        gap_ref_restarts=2,
        seed=7,
    )

    assert result["selected_k"] == 2
    assert set(result["results_by_k"]) == {2, 3}
    assert result["observed_objective_by_k"][2] == 80.0
    assert result["observed_objective_by_k"][3] == 100.0


def test_compute_gap_statistic_uses_reference_batch_hook_when_available() -> None:
    data = np.array(
        [
            [0.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0],
            [1.0, 1.0],
        ],
        dtype=np.float64,
    )
    calls = []

    def _stub_fit(fit_data: np.ndarray, k: int, repeats: int, seed: int):
        return {
            "labels": np.arange(fit_data.shape[0], dtype=np.int32) % k,
            "objective": float(10 + k),
        }

    def _fit_reference_batch(
        fit_data: np.ndarray,
        k: int,
        n_references: int,
        repeats: int,
        sample_seed_start: int,
        fit_seed_start: int,
    ) -> np.ndarray:
        calls.append((k, n_references, repeats, sample_seed_start, fit_seed_start))
        return np.full(n_references, 100.0 + k, dtype=np.float64)

    _stub_fit.fit_reference_batch = _fit_reference_batch
    _stub_fit.reference_batch_size = 2

    result = compute_gap_statistic(
        data=data,
        k_values=[2, 3],
        fit_best_fn=_stub_fit,
        observed_restarts=5,
        gap_ref_n=3,
        gap_ref_restarts=2,
        seed=11,
    )

    assert result["selected_k"] == 2
    assert calls == [
        (2, 2, 2, 20011, 40011),
        (2, 1, 2, 20013, 42011),
        (3, 2, 2, 30011, 60011),
        (3, 1, 2, 30013, 62011),
    ]


def test_compute_gap_statistic_batched_reference_hook_matches_legacy_loop() -> None:
    data = np.array(
        [
            [0.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0],
            [1.0, 1.0],
        ],
        dtype=np.float64,
    )

    def _objective(fit_data: np.ndarray, k: int, repeats: int, seed: int) -> float:
        del repeats
        center = np.mean(fit_data, axis=0)
        spread = np.sum((fit_data - center) ** 2)
        return float(spread + (k * 0.5) + (seed * 1e-6))

    def _legacy_fit(fit_data: np.ndarray, k: int, repeats: int, seed: int):
        return {
            "labels": np.arange(fit_data.shape[0], dtype=np.int32) % k,
            "objective": _objective(fit_data, k, repeats, seed),
        }

    def _batched_fit(fit_data: np.ndarray, k: int, repeats: int, seed: int):
        return {
            "labels": np.arange(fit_data.shape[0], dtype=np.int32) % k,
            "objective": _objective(fit_data, k, repeats, seed),
        }

    def _fit_reference_batch(
        fit_data: np.ndarray,
        k: int,
        n_references: int,
        repeats: int,
        sample_seed_start: int,
        fit_seed_start: int,
    ) -> np.ndarray:
        objectives = []
        for offset in range(n_references):
            rng = np.random.default_rng(sample_seed_start + offset)
            ref_data = sample_uniform_reference_within_bounds(fit_data, rng)
            objectives.append(_objective(ref_data, k, repeats, fit_seed_start + (offset * 1000)))
        return np.asarray(objectives, dtype=np.float64)

    _batched_fit.fit_reference_batch = _fit_reference_batch
    _batched_fit.reference_batch_size = 2

    legacy = compute_gap_statistic(
        data=data,
        k_values=[2, 3],
        fit_best_fn=_legacy_fit,
        observed_restarts=5,
        gap_ref_n=3,
        gap_ref_restarts=2,
        seed=17,
    )
    batched = compute_gap_statistic(
        data=data,
        k_values=[2, 3],
        fit_best_fn=_batched_fit,
        observed_restarts=5,
        gap_ref_n=3,
        gap_ref_restarts=2,
        seed=17,
    )

    assert batched["selected_k"] == legacy["selected_k"]
    assert batched["gap_by_k"] == legacy["gap_by_k"]
    assert batched["gap_sd_by_k"] == legacy["gap_sd_by_k"]
    assert batched["observed_objective_by_k"] == legacy["observed_objective_by_k"]
