"""Cluster pooled synergy vectors into global step and nonstep groups.

This module estimates a structure-first K with the gap statistic,
accepts the first observed zero-duplicate solution at or above it,
and exports representative W/H tables plus clustering diagnostics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .gap import compute_gap_statistic


@dataclass
class SubjectFeatureResult:
    """Synergy features extracted for one trial."""

    subject: str
    velocity: Any
    trial_num: Any
    bundle: Any


def _trial_identity(item: SubjectFeatureResult) -> tuple[Any, Any, Any]:
    return (item.subject, item.velocity, item.trial_num)


def _stack_weight_vectors(
    feature_rows: list[SubjectFeatureResult],
    group_id: str,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    stacked = []
    sample_map = []
    for item in feature_rows:
        W = item.bundle.W_muscle
        trial_key = _trial_identity(item)
        for component_index in range(W.shape[1]):
            stacked.append(W[:, component_index].astype(np.float32))
            sample_map.append(
                {
                    "group_id": group_id,
                    "subject": item.subject,
                    "velocity": item.velocity,
                    "trial_num": item.trial_num,
                    "component_index": component_index,
                    "trial_key": trial_key,
                    "trial_id": f"{item.subject}_v{item.velocity}_T{item.trial_num}",
                }
            )
    if not stacked:
        return np.empty((0, 0), dtype=np.float32), sample_map
    return np.stack(stacked, axis=0), sample_map


def _duplicate_trials(sample_map: list[dict[str, Any]], labels: np.ndarray) -> list[tuple[Any, Any, Any]]:
    grouped: dict[tuple[Any, Any, Any], list[int]] = defaultdict(list)
    for label, sample in zip(labels.tolist(), sample_map):
        key = (sample["subject"], sample["velocity"], sample["trial_num"])
        grouped[key].append(int(label))
    return [key for key, values in grouped.items() if len(values) != len(set(values))]


def _fit_kmeans(data: np.ndarray, n_clusters: int, cfg: dict[str, Any]):
    algorithm = str(cfg.get("algorithm", "cuml_kmeans")).strip().lower()
    random_state = int(cfg.get("random_state", 42))
    repeats = int(cfg.get("repeats", 25))
    max_iter = int(cfg.get("max_iter", 300))
    if algorithm == "cuml_kmeans":
        try:
            import cupy as cp
            from cuml.cluster import KMeans as CuKMeans

            model = CuKMeans(n_clusters=n_clusters, n_init=repeats, random_state=random_state, max_iter=max_iter)
            labels = model.fit_predict(cp.asarray(data))
            return np.asarray(labels.get()), float(model.inertia_), "cuml_kmeans"
        except Exception:
            algorithm = "sklearn_kmeans"
    if algorithm != "sklearn_kmeans":
        raise ValueError(f"Unsupported clustering algorithm: {algorithm}")
    from sklearn.cluster import KMeans

    model = KMeans(n_clusters=n_clusters, n_init=repeats, random_state=random_state, max_iter=max_iter)
    labels = model.fit_predict(data)
    return np.asarray(labels), float(model.inertia_), "sklearn_kmeans"


def _subject_hmax(feature_rows: list[SubjectFeatureResult]) -> int:
    subject_max: dict[str, int] = defaultdict(int)
    for item in feature_rows:
        n_components = int(item.bundle.W_muscle.shape[1])
        if getattr(item.bundle, "H_time", None) is not None:
            h_time = np.asarray(item.bundle.H_time)
            if h_time.ndim == 2 and h_time.shape[1] > 0:
                n_components = int(h_time.shape[1])
        subject_max[str(item.subject)] = max(subject_max[str(item.subject)], n_components)
    return max(subject_max.values()) if subject_max else 1


def _cluster_centroids(data: np.ndarray, labels: np.ndarray, n_clusters: int) -> np.ndarray:
    centroids = np.zeros((n_clusters, data.shape[1]), dtype=np.float32)
    fallback = data.mean(axis=0, dtype=np.float64).astype(np.float32)
    for cluster_id in range(n_clusters):
        cluster_mask = labels == cluster_id
        if np.any(cluster_mask):
            centroids[cluster_id] = data[cluster_mask].mean(axis=0, dtype=np.float64).astype(np.float32)
        else:
            centroids[cluster_id] = fallback
    return centroids


def _minimum_cost_unique_assignment(costs: np.ndarray) -> np.ndarray:
    """Return an exact or greedy unique assignment, depending on matrix size."""
    n_components, n_clusters = costs.shape
    if n_clusters < n_components:
        raise ValueError("Unique assignment requires n_clusters >= n_components.")
    if n_clusters > 16 or n_components > 10:
        return _greedy_unique_assignment(costs)
    states: dict[int, tuple[float, tuple[int, ...]]] = {0: (0.0, tuple())}
    for component_index in range(n_components):
        next_states: dict[int, tuple[float, tuple[int, ...]]] = {}
        for mask, (running_cost, path) in states.items():
            for cluster_id in range(n_clusters):
                if mask & (1 << cluster_id):
                    continue
                next_mask = mask | (1 << cluster_id)
                next_cost = running_cost + float(costs[component_index, cluster_id])
                previous = next_states.get(next_mask)
                if previous is None or (next_cost, path + (cluster_id,)) < (previous[0], previous[1]):
                    next_states[next_mask] = (next_cost, path + (cluster_id,))
        states = next_states
    best_path = min(states.values(), key=lambda pair: (pair[0], pair[1]))[1]
    return np.asarray(best_path, dtype=np.int32)


def _greedy_unique_assignment(costs: np.ndarray) -> np.ndarray:
    n_components, n_clusters = costs.shape
    assigned = np.full(n_components, -1, dtype=np.int32)
    available = set(range(n_clusters))
    margins = []
    for row_index in range(n_components):
        sorted_costs = np.sort(costs[row_index])
        margin = float(sorted_costs[1] - sorted_costs[0]) if n_clusters > 1 else float("inf")
        margins.append((margin, row_index))
    for _, row_index in sorted(margins):
        cluster_id = min(available, key=lambda cid: (float(costs[row_index, cid]), int(cid)))
        assigned[row_index] = int(cluster_id)
        available.remove(cluster_id)
    return assigned


def _enforce_unique_trial_labels(
    data: np.ndarray,
    sample_map: list[dict[str, Any]],
    labels: np.ndarray,
    n_clusters: int,
) -> np.ndarray:
    repaired = np.asarray(labels).astype(np.int32, copy=True)
    if n_clusters <= 1:
        return repaired
    centroids = _cluster_centroids(data, repaired, n_clusters)
    by_trial: dict[tuple[Any, Any, Any], list[int]] = defaultdict(list)
    for sample_index, sample in enumerate(sample_map):
        by_trial[sample["trial_key"]].append(sample_index)
    for indices in by_trial.values():
        if len(indices) <= 1 or n_clusters < len(indices):
            continue
        trial_labels = repaired[indices]
        if len(set(trial_labels.tolist())) == len(indices):
            continue
        trial_data = data[np.asarray(indices, dtype=np.int32)]
        sq_distance = ((trial_data[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2, dtype=np.float64)
        for row_index, current_label in enumerate(trial_labels.tolist()):
            sq_distance[row_index, :] += 1e-6
            sq_distance[row_index, int(current_label)] -= 1e-6
        repaired[indices] = _minimum_cost_unique_assignment(sq_distance)
    return repaired


def _inertia_from_labels(data: np.ndarray, labels: np.ndarray) -> float:
    """Recompute inertia for labels after post-processing reassignment."""
    inertia = 0.0
    for cluster_id in np.unique(labels):
        members = data[labels == cluster_id]
        if members.shape[0] == 0:
            continue
        centroid = members.mean(axis=0, dtype=np.float64)
        residual = members.astype(np.float64) - centroid
        inertia += float(np.sum(residual * residual))
    return inertia


def _selection_method(cfg: dict[str, Any]) -> str:
    return str(cfg.get("selection_method", "gap_statistic")).strip().lower() or "gap_statistic"


def _validated_selection_method(cfg: dict[str, Any]) -> str:
    selection_method = _selection_method(cfg)
    if selection_method != "gap_statistic":
        raise ValueError(f"Unsupported selection_method: {selection_method}")
    return selection_method


def _require_zero_duplicate_solution(cfg: dict[str, Any]) -> bool:
    if "require_zero_duplicate_solution" in cfg:
        return bool(cfg.get("require_zero_duplicate_solution"))
    return bool(cfg.get("disallow_within_trial_duplicate_assignment", True))


def _duplicate_resolution(cfg: dict[str, Any]) -> str:
    return str(cfg.get("duplicate_resolution", "none")).strip().lower() or "none"


def _fit_best_kmeans_result(
    data: np.ndarray,
    n_clusters: int,
    repeats: int,
    seed: int,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    fit_cfg = dict(cfg)
    fit_cfg["repeats"] = int(repeats)
    fit_cfg["random_state"] = int(seed)
    labels, inertia, algorithm_used = _fit_kmeans(data, n_clusters, fit_cfg)
    return {
        "labels": np.asarray(labels, dtype=np.int32),
        "objective": float(inertia),
        "algorithm_used": algorithm_used,
    }


def _uniqueness_candidate_restarts(cfg: dict[str, Any]) -> int:
    return max(1, int(cfg.get("uniqueness_candidate_restarts", cfg.get("repeats", 25))))


def _fit_single_kmeans_candidate(
    data: np.ndarray,
    n_clusters: int,
    seed: int,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    return _fit_best_kmeans_result(data, n_clusters, repeats=1, seed=seed, cfg=cfg)


def _search_zero_duplicate_candidate_at_k(
    data: np.ndarray,
    sample_map: list[dict[str, Any]],
    n_clusters: int,
    cfg: dict[str, Any],
    observed_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_restarts = _uniqueness_candidate_restarts(cfg)
    base_seed = int(cfg.get("random_state", 42)) + (int(n_clusters) * 100000)
    best_zero_duplicate_result: dict[str, Any] | None = None
    feasible_objective = np.nan
    min_duplicate_trial_count: int | None = None
    representative_duplicate_trials: list[tuple[Any, Any, Any]] = []
    min_duplicate_objective = float("inf")

    if observed_result is not None:
        observed_labels = np.asarray(observed_result["labels"], dtype=np.int32)
        observed_duplicates = _duplicate_trials(sample_map, observed_labels)
        observed_objective = float(observed_result["objective"])
        min_duplicate_trial_count = len(observed_duplicates)
        representative_duplicate_trials = observed_duplicates
        min_duplicate_objective = observed_objective
        if not observed_duplicates:
            best_zero_duplicate_result = {
                "labels": observed_labels,
                "objective": observed_objective,
                "algorithm_used": observed_result.get("algorithm_used", ""),
            }
            feasible_objective = observed_objective

    for restart_index in range(candidate_restarts):
        seed = base_seed + restart_index
        candidate_result = _fit_single_kmeans_candidate(data, n_clusters, seed, cfg)
        duplicate_trials = _duplicate_trials(sample_map, np.asarray(candidate_result["labels"], dtype=np.int32))
        duplicate_count = len(duplicate_trials)
        objective = float(candidate_result["objective"])

        if (
            min_duplicate_trial_count is None
            or duplicate_count < min_duplicate_trial_count
            or (duplicate_count == min_duplicate_trial_count and objective < min_duplicate_objective)
        ):
            min_duplicate_trial_count = duplicate_count
            representative_duplicate_trials = duplicate_trials
            min_duplicate_objective = objective

        if duplicate_count == 0 and (
            best_zero_duplicate_result is None or objective < float(best_zero_duplicate_result["objective"])
        ):
            best_zero_duplicate_result = {
                "labels": np.asarray(candidate_result["labels"], dtype=np.int32),
                "objective": objective,
                "algorithm_used": candidate_result.get("algorithm_used", ""),
            }
            feasible_objective = objective

    return {
        "best_zero_duplicate_result": best_zero_duplicate_result,
        "feasible_objective": feasible_objective,
        "min_duplicate_trial_count": (
            int(min_duplicate_trial_count) if min_duplicate_trial_count is not None else np.nan
        ),
        "representative_duplicate_trials": representative_duplicate_trials,
        "searched_restarts": candidate_restarts,
    }


def _json_metric_dict(values: dict[Any, Any]) -> str:
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        normalized_key = str(key)
        if isinstance(value, (np.floating, float)):
            scalar = float(value)
            normalized[normalized_key] = scalar if np.isfinite(scalar) else None
            continue
        normalized[normalized_key] = value
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, allow_nan=False)


def cluster_feature_group(
    feature_rows: list[SubjectFeatureResult],
    cfg: dict[str, Any],
    group_id: str,
) -> dict[str, Any]:
    selection_method = _validated_selection_method(cfg)
    require_zero_duplicate = _require_zero_duplicate_solution(cfg)
    duplicate_resolution = _duplicate_resolution(cfg)
    repeats = int(cfg.get("repeats", 25))
    gap_ref_n = int(cfg.get("gap_ref_n", 500))
    gap_ref_restarts = int(cfg.get("gap_ref_restarts", 100))
    uniqueness_candidate_restarts = _uniqueness_candidate_restarts(cfg)

    if not feature_rows:
        return {
            "status": "failed",
            "group_id": group_id,
            "reason": "No feature rows supplied.",
            "selection_method": selection_method,
            "selection_status": "failed_no_feature_rows",
            "duplicate_resolution": duplicate_resolution,
            "require_zero_duplicate_solution": require_zero_duplicate,
            "gap_ref_n": gap_ref_n,
            "gap_ref_restarts": gap_ref_restarts,
            "repeats": repeats,
            "uniqueness_candidate_restarts": uniqueness_candidate_restarts,
        }

    data, sample_map = _stack_weight_vectors(feature_rows, group_id)
    subject_hmax = _subject_hmax(feature_rows)
    k_min = max(2, subject_hmax)
    k_max = min(int(cfg.get("max_clusters", subject_hmax)), int(data.shape[0]))
    if k_max < k_min:
        return {
            "status": "failed",
            "group_id": group_id,
            "reason": (
                f"Invalid K range: subject Hmax requires k_min={k_min}, "
                f"but resolved k_max={k_max}. Increase synergy_clustering.max_clusters."
            ),
            "n_trials": len(feature_rows),
            "n_components": int(data.shape[0]),
            "selection_method": selection_method,
            "selection_status": "failed_invalid_k_range",
            "duplicate_resolution": duplicate_resolution,
            "require_zero_duplicate_solution": require_zero_duplicate,
            "k_lb": k_min,
            "k_gap_raw": np.nan,
            "k_selected": np.nan,
            "k_min_unique": np.nan,
            "gap_ref_n": gap_ref_n,
            "gap_ref_restarts": gap_ref_restarts,
            "repeats": repeats,
            "uniqueness_candidate_restarts": uniqueness_candidate_restarts,
        }

    k_values = list(range(k_min, k_max + 1))
    gap_result = compute_gap_statistic(
        data=data,
        k_values=k_values,
        fit_best_fn=lambda fit_data, n_clusters, fit_repeats, fit_seed: _fit_best_kmeans_result(
            fit_data,
            n_clusters,
            fit_repeats,
            fit_seed,
            cfg,
        ),
        observed_restarts=repeats,
        gap_ref_n=gap_ref_n,
        gap_ref_restarts=gap_ref_restarts,
        seed=int(cfg.get("random_state", 42)),
    )

    results_by_k = gap_result["results_by_k"]
    feasible_summary_by_k: dict[int, dict[str, Any]] = {}
    feasible_objective_by_k: dict[int, float] = {}
    duplicate_trial_count_by_k: dict[int, int] = {}
    k_min_unique: int | None = None
    if require_zero_duplicate:
        for n_clusters in k_values:
            feasible_summary = _search_zero_duplicate_candidate_at_k(
                data,
                sample_map,
                n_clusters,
                cfg,
                observed_result=results_by_k[n_clusters],
            )
            feasible_summary_by_k[n_clusters] = feasible_summary
            feasible_objective_by_k[n_clusters] = feasible_summary["feasible_objective"]
            duplicate_trial_count_by_k[n_clusters] = int(feasible_summary["min_duplicate_trial_count"])
            if k_min_unique is None and feasible_summary["best_zero_duplicate_result"] is not None:
                k_min_unique = int(n_clusters)
    else:
        for n_clusters in k_values:
            observed_labels = np.asarray(results_by_k[n_clusters]["labels"], dtype=np.int32)
            duplicate_count = len(_duplicate_trials(sample_map, observed_labels))
            feasible_objective_by_k[n_clusters] = np.nan
            duplicate_trial_count_by_k[n_clusters] = duplicate_count
            if k_min_unique is None and duplicate_count == 0:
                k_min_unique = int(n_clusters)

    k_gap_raw = int(gap_result["selected_k"])
    selected_k = k_gap_raw
    selection_status = "success_gap_without_uniqueness_requirement"
    selected_result = results_by_k[selected_k]
    duplicate_trials = _duplicate_trials(sample_map, np.asarray(selected_result["labels"], dtype=np.int32))
    if require_zero_duplicate:
        selected_k = -1
        for n_clusters in k_values:
            if n_clusters < k_gap_raw:
                continue
            if feasible_summary_by_k[n_clusters]["best_zero_duplicate_result"] is not None:
                selected_k = int(n_clusters)
                break
        if selected_k < 0:
            return {
                "status": "failed",
                "group_id": group_id,
                "reason": f"No zero-duplicate clustering solution found in K=[{k_gap_raw},{k_max}]",
                "duplicate_trials": feasible_summary_by_k.get(k_gap_raw, {}).get("representative_duplicate_trials", []),
                "sample_map": sample_map,
                "n_trials": len(feature_rows),
                "n_components": int(data.shape[0]),
                "selection_method": selection_method,
                "selection_status": "failed_no_zero_duplicate_at_or_above_gap_k",
                "duplicate_resolution": duplicate_resolution,
                "require_zero_duplicate_solution": require_zero_duplicate,
                "k_lb": k_min,
                "k_gap_raw": k_gap_raw,
                "k_selected": np.nan,
                "k_min_unique": float(k_min_unique) if k_min_unique is not None else np.nan,
                "gap_ref_n": gap_ref_n,
                "gap_ref_restarts": gap_ref_restarts,
                "repeats": repeats,
                "uniqueness_candidate_restarts": uniqueness_candidate_restarts,
                "gap_by_k": gap_result["gap_by_k"],
                "gap_sd_by_k": gap_result["gap_sd_by_k"],
                "observed_objective_by_k": gap_result["observed_objective_by_k"],
                "feasible_objective_by_k": feasible_objective_by_k,
                "duplicate_trial_count_by_k": duplicate_trial_count_by_k,
            }
        selection_status = "success_gap_unique" if selected_k == k_gap_raw else "success_gap_escalated_unique"
        selected_result = feasible_summary_by_k[selected_k]["best_zero_duplicate_result"]
        labels = np.asarray(selected_result["labels"], dtype=np.int32)
        duplicate_trials = []
    else:
        labels = np.asarray(selected_result["labels"], dtype=np.int32)
    if require_zero_duplicate and duplicate_trials:
        return {
            "status": "failed",
            "group_id": group_id,
            "reason": "Selected clustering result still contains duplicate trial assignments.",
            "duplicate_trials": duplicate_trials,
            "sample_map": sample_map,
            "n_trials": len(feature_rows),
            "n_components": int(data.shape[0]),
            "selection_method": selection_method,
            "selection_status": "failed_selected_result_contains_duplicates",
            "duplicate_resolution": duplicate_resolution,
            "require_zero_duplicate_solution": require_zero_duplicate,
            "k_lb": k_min,
            "k_gap_raw": k_gap_raw,
            "k_selected": selected_k,
            "k_min_unique": float(k_min_unique) if k_min_unique is not None else np.nan,
            "gap_ref_n": gap_ref_n,
            "gap_ref_restarts": gap_ref_restarts,
            "repeats": repeats,
            "uniqueness_candidate_restarts": uniqueness_candidate_restarts,
            "gap_by_k": gap_result["gap_by_k"],
            "gap_sd_by_k": gap_result["gap_sd_by_k"],
            "observed_objective_by_k": gap_result["observed_objective_by_k"],
            "feasible_objective_by_k": feasible_objective_by_k,
            "duplicate_trial_count_by_k": duplicate_trial_count_by_k,
        }
    return {
        "status": "success",
        "group_id": group_id,
        "n_trials": len(feature_rows),
        "n_components": int(data.shape[0]),
        "n_clusters": selected_k,
        "labels": labels,
        "inertia": float(selected_result["objective"]),
        "duplicate_trials": duplicate_trials,
        "algorithm_used": selected_result.get("algorithm_used", ""),
        "sample_map": sample_map,
        "selection_method": selection_method,
        "selection_status": selection_status,
        "duplicate_resolution": duplicate_resolution,
        "require_zero_duplicate_solution": require_zero_duplicate,
        "k_lb": k_min,
        "k_gap_raw": k_gap_raw,
        "k_selected": selected_k,
        "k_min_unique": float(k_min_unique) if k_min_unique is not None else np.nan,
        "gap_ref_n": gap_ref_n,
        "gap_ref_restarts": gap_ref_restarts,
        "repeats": repeats,
        "uniqueness_candidate_restarts": uniqueness_candidate_restarts,
        "gap_by_k": gap_result["gap_by_k"],
        "gap_sd_by_k": gap_result["gap_sd_by_k"],
        "observed_objective_by_k": gap_result["observed_objective_by_k"],
        "feasible_objective_by_k": feasible_objective_by_k,
        "duplicate_trial_count_by_k": duplicate_trial_count_by_k,
    }


def cluster_intra_subject(
    W_list: list[np.ndarray],
    trial_keys: list[tuple[Any, Any, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Compatibility wrapper retained for contract-style tests."""
    feature_rows = []
    for trial_key, W_muscle in zip(trial_keys, W_list):
        feature_rows.append(
            SubjectFeatureResult(
                subject=str(trial_key[0]),
                velocity=trial_key[1],
                trial_num=trial_key[2],
                bundle=type("Bundle", (), {"W_muscle": W_muscle, "H_time": np.zeros((1, W_muscle.shape[1])), "meta": {}})(),
            )
        )
    return cluster_feature_group(feature_rows, cfg, "compatibility_group")


def _interpolate_series(values: np.ndarray, target_windows: int) -> np.ndarray:
    if len(values) == target_windows:
        return values.astype(np.float32)
    x_old = np.linspace(0.0, 1.0, len(values))
    x_new = np.linspace(0.0, 1.0, target_windows)
    return np.interp(x_new, x_old, values).astype(np.float32)


def _scalar_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    excluded = {"extractor_metric_elapsed_sec"}
    exported = {}
    for key, value in meta.items():
        if key in excluded:
            continue
        if isinstance(value, (str, int, float, bool, np.integer, np.floating, np.bool_)) or pd.isna(value):
            exported[key] = value
    return exported


def build_group_exports(
    group_id: str,
    feature_rows: list[SubjectFeatureResult],
    cluster_result: dict[str, Any],
    muscle_names: list[str],
    target_windows: int,
) -> dict[str, pd.DataFrame]:
    trial_meta_lookup = {_trial_identity(item): _scalar_metadata(item.bundle.meta) for item in feature_rows}
    metadata_df = pd.DataFrame(
        [
            {
                "group_id": group_id,
                "status": cluster_result.get("status", "unknown"),
                "reason": cluster_result.get("reason", ""),
                "n_trials": len(feature_rows),
                "n_components": int(sum(item.bundle.W_muscle.shape[1] for item in feature_rows)),
                "n_clusters": cluster_result.get("n_clusters", 0),
                "inertia": cluster_result.get("inertia", np.nan),
                "duplicate_trials": str(cluster_result.get("duplicate_trials", [])),
                "algorithm_used": cluster_result.get("algorithm_used", ""),
                "selection_method": cluster_result.get("selection_method", ""),
                "selection_status": cluster_result.get("selection_status", ""),
                "duplicate_resolution": cluster_result.get("duplicate_resolution", ""),
                "require_zero_duplicate_solution": cluster_result.get("require_zero_duplicate_solution", np.nan),
                "k_lb": cluster_result.get("k_lb", np.nan),
                "k_gap_raw": cluster_result.get("k_gap_raw", np.nan),
                "k_selected": cluster_result.get("k_selected", np.nan),
                "k_min_unique": cluster_result.get("k_min_unique", np.nan),
                "repeats": cluster_result.get("repeats", np.nan),
                "gap_ref_n": cluster_result.get("gap_ref_n", np.nan),
                "gap_ref_restarts": cluster_result.get("gap_ref_restarts", np.nan),
                "uniqueness_candidate_restarts": cluster_result.get("uniqueness_candidate_restarts", np.nan),
                "gap_by_k_json": _json_metric_dict(cluster_result.get("gap_by_k", {})),
                "gap_sd_by_k_json": _json_metric_dict(cluster_result.get("gap_sd_by_k", {})),
                "observed_objective_by_k_json": _json_metric_dict(cluster_result.get("observed_objective_by_k", {})),
                "feasible_objective_by_k_json": _json_metric_dict(cluster_result.get("feasible_objective_by_k", {})),
                "duplicate_trial_count_by_k_json": _json_metric_dict(cluster_result.get("duplicate_trial_count_by_k", {})),
            }
        ]
    )
    labels = np.asarray(cluster_result.get("labels", np.array([])))
    sample_map = cluster_result.get("sample_map", [])
    labels_df = pd.DataFrame(
        [
            {
                "group_id": group_id,
                "subject": sample["subject"],
                "velocity": sample["velocity"],
                "trial_num": sample["trial_num"],
                "trial_id": sample["trial_id"],
                "component_index": sample["component_index"],
                "cluster_id": int(label),
                **trial_meta_lookup.get(sample["trial_key"], {}),
            }
            for sample, label in zip(sample_map, labels)
        ]
    )

    W_store = {_trial_identity(item): item.bundle.W_muscle for item in feature_rows}
    H_store = {_trial_identity(item): item.bundle.H_time for item in feature_rows}
    member_rows = []
    representative_w_rows = []
    representative_h_rows = []
    minimal_w_rows = []
    minimal_h_rows = []
    trial_window_rows = []

    for item in feature_rows:
        W = item.bundle.W_muscle
        H = item.bundle.H_time
        trial_key = _trial_identity(item)
        trial_id = f"{item.subject}_v{item.velocity}_T{item.trial_num}"
        trial_meta = trial_meta_lookup.get(trial_key, {})
        trial_window_rows.append(
            {
                "group_id": group_id,
                "subject": item.subject,
                "velocity": item.velocity,
                "trial_num": item.trial_num,
                "trial_id": trial_id,
                **trial_meta,
            }
        )
        for component_index in range(W.shape[1]):
            for muscle_index, value in enumerate(W[:, component_index]):
                minimal_w_rows.append(
                    {
                        "group_id": group_id,
                        "subject": item.subject,
                        "velocity": item.velocity,
                        "trial_num": item.trial_num,
                        "trial_id": trial_id,
                        "component_index": component_index,
                        "muscle": muscle_names[muscle_index],
                        "W_value": float(value),
                        **trial_meta,
                    }
                )
            interpolated_h = _interpolate_series(H[:, component_index], target_windows)
            for frame_idx, value in enumerate(interpolated_h.tolist()):
                minimal_h_rows.append(
                    {
                        "group_id": group_id,
                        "subject": item.subject,
                        "velocity": item.velocity,
                        "trial_num": item.trial_num,
                        "trial_id": trial_id,
                        "component_index": component_index,
                        "frame_idx": frame_idx,
                        "h_value": float(value),
                        **trial_meta,
                    }
                )

    if len(labels) > 0:
        for cluster_id in sorted(np.unique(labels).tolist()):
            cluster_indices = np.where(labels == cluster_id)[0].tolist()
            W_members = []
            H_members = []
            for sample_index in cluster_indices:
                sample = sample_map[sample_index]
                trial_key = sample["trial_key"]
                component_index = sample["component_index"]
                W_members.append(W_store[trial_key][:, component_index])
                H_members.append(_interpolate_series(H_store[trial_key][:, component_index], target_windows))
                member_rows.append(
                    {
                        "group_id": group_id,
                        "subject": sample["subject"],
                        "velocity": sample["velocity"],
                        "trial_num": sample["trial_num"],
                        "trial_id": sample["trial_id"],
                        "cluster_id": int(cluster_id),
                        "component_index": component_index,
                        **trial_meta_lookup.get(trial_key, {}),
                    }
                )
            representative_w = np.mean(np.stack(W_members, axis=1), axis=1)
            norm = np.linalg.norm(representative_w)
            if norm > 0:
                representative_w = representative_w / norm
            representative_h = np.mean(np.stack(H_members, axis=1), axis=1)
            for muscle_index, value in enumerate(representative_w.tolist()):
                representative_w_rows.append(
                    {
                        "group_id": group_id,
                        "cluster_id": int(cluster_id),
                        "muscle": muscle_names[muscle_index],
                        "W_value": float(value),
                    }
                )
            for frame_idx, value in enumerate(representative_h.tolist()):
                representative_h_rows.append(
                    {
                        "group_id": group_id,
                        "cluster_id": int(cluster_id),
                        "frame_idx": frame_idx,
                        "h_value": float(value),
                    }
                )

    return {
        "metadata": metadata_df,
        "labels": labels_df,
        "members": pd.DataFrame(member_rows),
        "rep_W": pd.DataFrame(representative_w_rows),
        "rep_H_long": pd.DataFrame(representative_h_rows),
        "minimal_W": pd.DataFrame(minimal_w_rows),
        "minimal_H_long": pd.DataFrame(minimal_h_rows),
        "trial_windows": pd.DataFrame(trial_window_rows).drop_duplicates(),
    }


def save_group_outputs(group_dir: Path, exports: dict[str, pd.DataFrame]) -> None:
    group_dir.mkdir(parents=True, exist_ok=True)
    name_map = {
        "metadata": "clustering_metadata.csv",
        "labels": "cluster_labels.csv",
        "members": "cluster_members.csv",
        "rep_W": "representative_W_posthoc.csv",
        "rep_H_long": "representative_H_posthoc_long.csv",
        "minimal_W": "minimal_units_W.csv",
        "minimal_H_long": "minimal_units_H_long.csv",
        "trial_windows": "trial_window_metadata.csv",
    }
    for key, filename in name_map.items():
        exports.get(key, pd.DataFrame()).to_csv(
            group_dir / filename,
            index=False,
            encoding="utf-8-sig",
            float_format="%.10f",
        )
