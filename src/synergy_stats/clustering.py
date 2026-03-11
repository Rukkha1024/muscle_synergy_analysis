"""Cluster synergy vectors and build group-level exports.

This module pools selected trial-level synergies into global groups,
fits KMeans with the existing within-trial duplicate safeguard,
and exports representative W/H tables plus membership metadata.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


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


def cluster_feature_group(
    feature_rows: list[SubjectFeatureResult],
    cfg: dict[str, Any],
    group_id: str,
) -> dict[str, Any]:
    if not feature_rows:
        return {"status": "failed", "group_id": group_id, "reason": "No feature rows supplied."}

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
        }

    best = None
    for n_clusters in range(k_min, k_max + 1):
        raw_labels, raw_inertia, algorithm_used = _fit_kmeans(data, n_clusters, cfg)
        labels = np.asarray(raw_labels).astype(np.int32, copy=False)
        inertia = float(raw_inertia)
        if cfg.get("disallow_within_trial_duplicate_assignment", True):
            labels = _enforce_unique_trial_labels(data, sample_map, labels, n_clusters)
            if not np.array_equal(labels, raw_labels):
                inertia = _inertia_from_labels(data, labels)
        duplicates = _duplicate_trials(sample_map, labels)
        candidate = {
            "status": "success",
            "group_id": group_id,
            "n_trials": len(feature_rows),
            "n_components": int(data.shape[0]),
            "n_clusters": n_clusters,
            "labels": labels,
            "inertia": inertia,
            "duplicate_trials": duplicates,
            "algorithm_used": algorithm_used,
            "sample_map": sample_map,
        }
        if cfg.get("disallow_within_trial_duplicate_assignment", True):
            if not duplicates:
                return candidate
            if best is None or len(duplicates) < len(best.get("duplicate_trials", [])):
                best = candidate
        elif best is None or len(duplicates) < len(best.get("duplicate_trials", [])):
            best = candidate

    if best is None:
        return {"status": "failed", "group_id": group_id, "reason": "No valid clustering solution."}
    if cfg.get("disallow_within_trial_duplicate_assignment", True):
        return {
            "status": "failed",
            "group_id": group_id,
            "reason": f"No zero-duplicate clustering solution found in K=[{k_min},{k_max}]",
            "duplicate_trials": best.get("duplicate_trials", []),
            "sample_map": sample_map,
            "n_trials": len(feature_rows),
            "n_components": int(data.shape[0]),
        }
    return best


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
                "n_trials": len(feature_rows),
                "n_components": int(sum(item.bundle.W_muscle.shape[1] for item in feature_rows)),
                "n_clusters": cluster_result.get("n_clusters", 0),
                "inertia": cluster_result.get("inertia", np.nan),
                "duplicate_trials": str(cluster_result.get("duplicate_trials", [])),
                "algorithm_used": cluster_result.get("algorithm_used", ""),
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
