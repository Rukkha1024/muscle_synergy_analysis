"""Compute gap-statistic diagnostics for pooled synergy clustering.

This helper evaluates observed and reference KMeans objectives,
applies the 1-SE selection rule, and returns per-K diagnostics
plus the best observed solution for each candidate K.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np


GapFitFn = Callable[[np.ndarray, int, int, int], dict[str, Any]]


def sample_uniform_reference_within_bounds(data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    data = np.asarray(data, dtype=np.float64)
    mins = np.min(data, axis=0)
    maxs = np.max(data, axis=0)
    return rng.uniform(mins, maxs, size=data.shape)


def select_k_by_first_se_rule(
    k_values: list[int],
    gap_by_k: dict[int, float],
    gap_sd_by_k: dict[int, float],
) -> int:
    if not k_values:
        raise ValueError("k_values must not be empty.")
    if len(k_values) == 1:
        return int(k_values[0])
    for index, k in enumerate(k_values[:-1]):
        k_next = k_values[index + 1]
        if float(gap_by_k[k]) >= float(gap_by_k[k_next]) - float(gap_sd_by_k[k_next]):
            return int(k)
    return int(k_values[-1])


def compute_gap_statistic(
    data: np.ndarray,
    k_values: list[int],
    fit_best_fn: GapFitFn,
    observed_restarts: int,
    gap_ref_n: int,
    gap_ref_restarts: int,
    seed: int,
) -> dict[str, Any]:
    data = np.asarray(data, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] == 0:
        raise ValueError("Gap statistic expects a non-empty 2D array.")
    if not k_values:
        raise ValueError("k_values must not be empty.")
    if int(gap_ref_n) < 1:
        raise ValueError("gap_ref_n must be at least 1.")

    observed_objective_by_k: dict[int, float] = {}
    gap_by_k: dict[int, float] = {}
    gap_sd_by_k: dict[int, float] = {}
    results_by_k: dict[int, dict[str, Any]] = {}

    for k in [int(value) for value in k_values]:
        observed_result = fit_best_fn(data, k, int(observed_restarts), int(seed) + (k * 1000))
        results_by_k[k] = observed_result
        observed_objective = float(observed_result["objective"])
        observed_objective_by_k[k] = observed_objective

        reference_logs: list[float] = []
        for ref_idx in range(int(gap_ref_n)):
            ref_rng = np.random.default_rng(int(seed) + (k * 10000) + ref_idx)
            ref_data = sample_uniform_reference_within_bounds(data, ref_rng)
            ref_result = fit_best_fn(
                ref_data,
                k,
                int(gap_ref_restarts),
                int(seed) + (k * 20000) + (ref_idx * 1000),
            )
            reference_logs.append(float(np.log(float(ref_result["objective"]) + 1e-12)))

        gap_by_k[k] = float(np.mean(reference_logs) - np.log(observed_objective + 1e-12))
        reference_sd = float(np.std(reference_logs, ddof=1)) if len(reference_logs) > 1 else 0.0
        gap_sd_by_k[k] = float(reference_sd * math.sqrt(1.0 + 1.0 / float(gap_ref_n)))

    selected_k = select_k_by_first_se_rule(k_values, gap_by_k, gap_sd_by_k)
    return {
        "selected_k": int(selected_k),
        "gap_by_k": gap_by_k,
        "gap_sd_by_k": gap_sd_by_k,
        "observed_objective_by_k": observed_objective_by_k,
        "results_by_k": results_by_k,
    }
