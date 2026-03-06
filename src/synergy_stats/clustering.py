"""Cluster synergy vectors and build subject-level exports."""

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


def _stack_weight_vectors(feature_rows: list[SubjectFeatureResult]) -> tuple[np.ndarray, list[dict[str, Any]]]:
    stacked = []
    sample_map = []
    for item in feature_rows:
        W = item.bundle.W_muscle
        for component_index in range(W.shape[1]):
            stacked.append(W[:, component_index].astype(np.float32))
            sample_map.append(
                {
                    "subject": item.subject,
                    "velocity": item.velocity,
                    "trial_num": item.trial_num,
                    "component_index": component_index,
                    "trial_key": f"v{item.velocity}_T{item.trial_num}",
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


def cluster_subject_features(feature_rows: list[SubjectFeatureResult], cfg: dict[str, Any]) -> dict[str, Any]:
    if not feature_rows:
        return {"status": "failed", "reason": "No feature rows supplied."}

    data, sample_map = _stack_weight_vectors(feature_rows)
    per_trial_components = defaultdict(int)
    for item in feature_rows:
        per_trial_components[(item.subject, item.velocity, item.trial_num)] = item.bundle.W_muscle.shape[1]
    max_per_trial = max(per_trial_components.values())
    k_max = int(cfg.get("max_clusters", max_per_trial))
    k_min = min(max(2, max_per_trial), k_max)

    best = None
    for n_clusters in range(k_min, k_max + 1):
        labels, inertia, algorithm_used = _fit_kmeans(data, n_clusters, cfg)
        duplicates = _duplicate_trials(sample_map, labels)
        candidate = {
            "status": "success",
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
            best = candidate
        elif best is None or len(duplicates) < len(best.get("duplicate_trials", [])):
            best = candidate

    if best is None:
        return {"status": "failed", "reason": "No valid clustering solution."}
    if cfg.get("disallow_within_trial_duplicate_assignment", True):
        return {
            "status": "failed",
            "reason": f"No zero-duplicate clustering solution found in K=[{k_min},{k_max}]",
            "duplicate_trials": best.get("duplicate_trials", []),
            "sample_map": sample_map,
        }
    return best


def _cluster_intra_subject(W_list: list[np.ndarray], trial_keys: list[tuple[Any, Any, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper matching the reference clustering signature."""
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
    return cluster_subject_features(feature_rows, cfg)


def cluster_intra_subject(W_list: list[np.ndarray], trial_keys: list[tuple[Any, Any, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """Public alias for contract-style tests and wrappers."""
    return _cluster_intra_subject(W_list, trial_keys, cfg)


def _interpolate_series(values: np.ndarray, target_windows: int) -> np.ndarray:
    if len(values) == target_windows:
        return values.astype(np.float32)
    x_old = np.linspace(0.0, 1.0, len(values))
    x_new = np.linspace(0.0, 1.0, target_windows)
    return np.interp(x_new, x_old, values).astype(np.float32)


def build_subject_exports(
    subject_id: str,
    feature_rows: list[SubjectFeatureResult],
    cluster_result: dict[str, Any],
    muscle_names: list[str],
    target_windows: int,
) -> dict[str, pd.DataFrame]:
    metadata_df = pd.DataFrame(
        [
            {
                "subject": subject_id,
                "status": cluster_result.get("status", "unknown"),
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
                "subject": sample["subject"],
                "velocity": sample["velocity"],
                "trial_num": sample["trial_num"],
                "component_index": sample["component_index"],
                "cluster_id": int(label),
            }
            for sample, label in zip(sample_map, labels)
        ]
    )

    W_store = {f"v{item.velocity}_T{item.trial_num}": item.bundle.W_muscle for item in feature_rows}
    H_store = {f"v{item.velocity}_T{item.trial_num}": item.bundle.H_time for item in feature_rows}
    member_rows = []
    representative_w_rows = []
    representative_h_rows = []
    minimal_w_rows = []
    minimal_h_rows = []

    for item in feature_rows:
        W = item.bundle.W_muscle
        H = item.bundle.H_time
        for component_index in range(W.shape[1]):
            for muscle_index, value in enumerate(W[:, component_index]):
                minimal_w_rows.append(
                    {
                        "subject": item.subject,
                        "velocity": item.velocity,
                        "trial_num": item.trial_num,
                        "component_index": component_index,
                        "muscle": muscle_names[muscle_index],
                        "W_value": float(value),
                    }
                )
            interpolated_h = _interpolate_series(H[:, component_index], target_windows)
            for frame_idx, value in enumerate(interpolated_h.tolist()):
                minimal_h_rows.append(
                    {
                        "subject": item.subject,
                        "velocity": item.velocity,
                        "trial_num": item.trial_num,
                        "component_index": component_index,
                        "frame_idx": frame_idx,
                        "h_value": float(value),
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
                        "subject": sample["subject"],
                        "cluster_id": int(cluster_id),
                        "velocity": sample["velocity"],
                        "trial_num": sample["trial_num"],
                        "component_index": component_index,
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
                        "subject": subject_id,
                        "cluster_id": int(cluster_id),
                        "muscle": muscle_names[muscle_index],
                        "W_value": float(value),
                    }
                )
            for frame_idx, value in enumerate(representative_h.tolist()):
                representative_h_rows.append(
                    {
                        "subject": subject_id,
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
    }


def save_subject_outputs(subject_dir: Path, exports: dict[str, pd.DataFrame]) -> None:
    subject_dir.mkdir(parents=True, exist_ok=True)
    name_map = {
        "metadata": "clustering_metadata.csv",
        "labels": "cluster_labels.csv",
        "members": "cluster_members.csv",
        "rep_W": "representative_W_posthoc.csv",
        "rep_H_long": "representative_H_posthoc_long.csv",
        "minimal_W": "minimal_units_W.csv",
        "minimal_H_long": "minimal_units_H_long.csv",
    }
    for key, filename in name_map.items():
        exports.get(key, pd.DataFrame()).to_csv(subject_dir / filename, index=False, encoding="utf-8-sig")
