"""Unit tests for shared gap-statistic helpers."""

from __future__ import annotations

import numpy as np

from src.synergy_stats.gap import compute_gap_statistic, select_k_by_first_se_rule


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
