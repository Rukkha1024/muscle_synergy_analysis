﻿"""Professor-style step/nonstep synergy comparison.

Re-extracts trial synergies with NMF(init='random', random_state=0) and the
minimum-rank VAF>0.9 rule, clusters synergy structures per group while
avoiding within-trial duplicate cluster labels, then compares against the
baseline pipeline representative synergies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sklearn.cluster import KMeans
from sklearn.decomposition import NMF
from sklearn.exceptions import ConvergenceWarning

from src.emg_pipeline import build_trial_records, load_emg_table, load_event_metadata, load_pipeline_config, merge_event_metadata
from src.synergy_stats.figures import save_group_cluster_figure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "configs" / "global_config.yaml")
    parser.add_argument("--baseline-run", type=Path, default=REPO_ROOT / "outputs" / "runs" / "default_run")
    parser.add_argument("--outdir", type=Path, default=SCRIPT_DIR / "artifacts" / "professor_step_nonstep_compare")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output directory if it exists.")
    parser.add_argument("--vaf-threshold", type=float, default=0.90)
    parser.add_argument("--seed", type=int, default=0, help="Random seed (used for NMF and KMeans).")
    parser.add_argument("--k-max", type=int, default=26, help="Max clusters to try when enforcing within-trial uniqueness.")
    return parser.parse_args()


def _ensure_outdir(path: Path, *, overwrite: bool) -> None:
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"Output directory exists: {path} (use --overwrite)")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _md5_file(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8-sig") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)


def _read_baseline_trial_keys(baseline_run: Path) -> set[tuple[str, float, int]]:
    metadata_path = baseline_run / "all_trial_window_metadata.csv"
    df = pd.read_csv(metadata_path, encoding="utf-8-sig")
    keys: set[tuple[str, float, int]] = set()
    for row in df.itertuples(index=False):
        keys.add((str(row.subject).strip(), float(row.velocity), int(row.trial_num)))
    return keys


def _read_baseline_trial_lookup(baseline_run: Path) -> dict[tuple[str, float, int], dict[str, Any]]:
    metadata_path = baseline_run / "all_trial_window_metadata.csv"
    df = pd.read_csv(metadata_path, encoding="utf-8-sig")
    df["subject"] = df["subject"].astype(str).str.strip()
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").astype(float)
    df["trial_num"] = pd.to_numeric(df["trial_num"], errors="coerce").round().astype(int)
    lookup: dict[tuple[str, float, int], dict[str, Any]] = {}
    for row in df.itertuples(index=False):
        key = (str(row.subject).strip(), float(row.velocity), int(row.trial_num))
        lookup[key] = {
            "trial_id": str(row.trial_id),
            "status": str(row.status),
            "analysis_step_class": str(row.analysis_step_class),
            "analysis_window_start_device": int(row.analysis_window_start_device),
            "analysis_window_end_device": int(row.analysis_window_end_device),
            "n_components": int(row.n_components),
            "vaf": float(row.vaf),
        }
    return lookup


def _normalize_trial_key(key: tuple[str, Any, Any]) -> tuple[str, float, int]:
    subject, velocity, trial_num = key
    return (str(subject).strip(), float(velocity), int(trial_num))


def _coerce_step_class(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text == "step":
        return "step"
    if text in {"nonstep", "non-step", "non_step", "non step"}:
        return "nonstep"
    return None


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and np.isnan(value):
        return False
    if pd.isna(value):
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value) != 0
    if isinstance(value, (float, np.floating)):
        return float(value) != 0.0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _step_class_from_metadata(meta: dict[str, Any]) -> str | None:
    if not isinstance(meta, dict):
        return None
    direct = _coerce_step_class(meta.get("analysis_step_class"))
    if direct is not None:
        return direct
    is_step = _truthy(meta.get("analysis_is_step"))
    is_nonstep = _truthy(meta.get("analysis_is_nonstep"))
    if is_step and not is_nonstep:
        return "step"
    if is_nonstep and not is_step:
        return "nonstep"
    return None


def _group_id_for_step_class(step_class: str) -> str:
    if step_class == "step":
        return "global_step"
    if step_class == "nonstep":
        return "global_nonstep"
    return "unknown"


@dataclass(frozen=True)
class ProfessorNmfResult:
    status: str
    n_components: int
    vaf: float
    H_structure: np.ndarray  # (k, muscles)
    W_activation: np.ndarray  # (frames, k)


def _compute_vaf(X: np.ndarray, recon: np.ndarray) -> float:
    denom = float(np.sum(X * X))
    if denom <= 0:
        return 0.0
    resid = float(np.sum((X - recon) ** 2))
    return 1.0 - (resid / denom)


def professor_nmf_min_rank(
    X_trial: np.ndarray,
    *,
    vaf_threshold: float,
    seed: int,
) -> ProfessorNmfResult:
    X = np.asarray(X_trial, dtype=np.float64)
    if X.ndim != 2 or X.shape[0] == 0 or X.shape[1] == 0:
        return ProfessorNmfResult(
            status="invalid_shape",
            n_components=0,
            vaf=float("nan"),
            H_structure=np.empty((0, 0)),
            W_activation=np.empty((0, 0)),
        )
    if np.isnan(X).any():
        return ProfessorNmfResult(
            status="nan_in_input",
            n_components=0,
            vaf=float("nan"),
            H_structure=np.empty((0, 0)),
            W_activation=np.empty((0, 0)),
        )

    X = np.where(X < 0, 0.0, X)
    n_muscles = int(X.shape[1])

    best = None
    for rank in range(1, n_muscles + 1):
        model = NMF(n_components=rank, init="random", random_state=int(seed))
        with np.errstate(all="ignore"):
            try:
                with warnings_suppressed():
                    W = model.fit_transform(X)
            except Exception:
                continue
        recon = model.inverse_transform(W)
        vaf = _compute_vaf(X, recon)
        candidate = {
            "rank": rank,
            "vaf": vaf,
            "H": np.asarray(model.components_, dtype=np.float64),
            "W": np.asarray(W, dtype=np.float64),
        }
        if best is None or vaf > best["vaf"]:
            best = candidate
        if vaf > vaf_threshold:
            return ProfessorNmfResult(
                status="ok",
                n_components=rank,
                vaf=float(vaf),
                H_structure=candidate["H"],
                W_activation=candidate["W"],
            )

    if best is None:
        return ProfessorNmfResult(
            status="nmf_failed",
            n_components=0,
            vaf=float("nan"),
            H_structure=np.empty((0, 0)),
            W_activation=np.empty((0, 0)),
        )
    return ProfessorNmfResult(
        status="below_threshold_best_effort",
        n_components=int(best["rank"]),
        vaf=float(best["vaf"]),
        H_structure=np.asarray(best["H"], dtype=np.float64),
        W_activation=np.asarray(best["W"], dtype=np.float64),
    )


class warnings_suppressed:
    def __enter__(self):  # noqa: D401
        import warnings

        self._ctx = warnings.catch_warnings()
        self._ctx.__enter__()
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._ctx.__exit__(exc_type, exc, tb)


def _trial_duplicate_labels(trial_ids: list[str], labels: np.ndarray) -> list[str]:
    by_trial: dict[str, list[int]] = {}
    for trial_id, label in zip(trial_ids, labels.tolist()):
        by_trial.setdefault(trial_id, []).append(int(label))
    return [trial_id for trial_id, values in by_trial.items() if len(values) != len(set(values))]


def _repair_within_trial_unique_labels(
    data: np.ndarray,
    trial_ids: list[str],
    labels: np.ndarray,
    centroids: np.ndarray,
) -> np.ndarray:
    try:
        from scipy.optimize import linear_sum_assignment
    except Exception as exc:  # pragma: no cover - depends on environment
        raise ImportError("scipy is required for within-trial unique-assignment repair.") from exc

    repaired = np.asarray(labels, dtype=int).copy()
    by_trial: dict[str, list[int]] = {}
    for idx, trial_id in enumerate(trial_ids):
        by_trial.setdefault(trial_id, []).append(int(idx))

    for trial_id, indices in by_trial.items():
        trial_labels = repaired[np.asarray(indices, dtype=int)]
        if len(trial_labels) == len(set(trial_labels.tolist())):
            continue
        trial_data = data[np.asarray(indices, dtype=int)]
        costs = ((trial_data[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2, dtype=np.float64)
        for row_index, current_label in enumerate(trial_labels.tolist()):
            costs[row_index, :] += 1e-6
            costs[row_index, int(current_label)] -= 1e-6
        row_ind, col_ind = linear_sum_assignment(costs)
        if len(row_ind) != len(indices):
            raise RuntimeError(f"Assignment size mismatch while repairing trial_id={trial_id}")
        repaired[np.asarray(indices, dtype=int)[row_ind]] = col_ind.astype(int)
    return repaired


def professor_kmeans_within_trial_unique(
    data: np.ndarray,
    trial_ids: list[str],
    *,
    k_min: int,
    k_max: int,
    seed: int,
    allow_repair: bool = True,
) -> dict[str, Any]:
    if data.ndim != 2 or data.shape[0] == 0:
        return {"status": "failed", "reason": "empty_data"}
    k_max = min(int(k_max), int(data.shape[0]))
    if k_max < k_min:
        return {"status": "failed", "reason": f"invalid_k_range(k_min={k_min}, k_max={k_max})"}

    for k in range(int(k_min), int(k_max) + 1):
        model = KMeans(n_clusters=int(k), n_init="auto", random_state=int(seed))
        labels = model.fit_predict(data).astype(int)
        duplicates = _trial_duplicate_labels(trial_ids, labels)
        if not duplicates:
            return {
                "status": "success_no_repair",
                "n_clusters": int(k),
                "labels": labels,
                "duplicates": [],
                "inertia": float(model.inertia_),
                "repair_applied": False,
            }

    if allow_repair:
        model = KMeans(n_clusters=int(k_min), n_init="auto", random_state=int(seed))
        labels = model.fit_predict(data).astype(int)
        centroids = np.asarray(model.cluster_centers_, dtype=np.float64)
        duplicates = _trial_duplicate_labels(trial_ids, labels)
        repaired_labels = _repair_within_trial_unique_labels(data, trial_ids, labels, centroids)
        repaired_duplicates = _trial_duplicate_labels(trial_ids, repaired_labels)
        if repaired_duplicates:
            return {
                "status": "failed",
                "reason": "repair_failed_to_remove_duplicates",
                "n_clusters": int(k_min),
                "duplicates": repaired_duplicates,
            }
        return {
            "status": "success_with_repair",
            "n_clusters": int(k_min),
            "labels": repaired_labels,
            "inertia": float(model.inertia_),
            "repair_applied": True,
            "original_duplicates_count": int(len(duplicates)),
            "original_duplicates_preview": duplicates[:10],
        }

    return {"status": "failed", "reason": f"no_zero_duplicate_solution_in_k[{k_min},{k_max}]", "n_clusters": int(k_max)}


def _centroids_from_labels(data: np.ndarray, labels: np.ndarray, n_clusters: int) -> np.ndarray:
    centroids = np.zeros((n_clusters, data.shape[1]), dtype=np.float64)
    for k in range(n_clusters):
        mask = labels == k
        if not np.any(mask):
            continue
        centroids[k] = data[mask].mean(axis=0, dtype=np.float64)
    return centroids


def _l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms <= 0, 1.0, norms)
    return matrix / norms


def _load_pipeline_representative_W(path: Path, muscle_order: list[str]) -> np.ndarray:
    table = pl.read_csv(path, encoding="utf8-lossy")
    pivot = (
        table.select(["cluster_id", "muscle", "W_value"])
        .with_columns(pl.col("cluster_id").cast(pl.Int64, strict=False))
        .pivot(values="W_value", index="cluster_id", on="muscle", aggregate_function="first")
        .sort("cluster_id")
    )
    missing = [muscle for muscle in muscle_order if muscle not in pivot.columns]
    if missing:
        raise ValueError(f"Missing muscle columns in pipeline representative W: {missing}")
    pivot = pivot.select(["cluster_id", *muscle_order]).fill_null(0.0)
    return pivot.drop("cluster_id").to_numpy()


def _write_long_centroids(path: Path, group_id: str, centroids: np.ndarray, muscle_names: list[str]) -> None:
    rows = []
    for cluster_id, vector in enumerate(centroids.tolist()):
        for muscle, value in zip(muscle_names, vector):
            rows.append({"group_id": group_id, "cluster_id": int(cluster_id), "muscle": muscle, "W_value": float(value)})
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _resample_series(values: np.ndarray, target_len: int = 100) -> np.ndarray:
    series = np.asarray(values, dtype=np.float64).reshape(-1)
    if series.size == 0:
        return np.zeros(target_len, dtype=np.float64)
    if series.size == 1:
        return np.repeat(series, target_len)
    original = np.linspace(0.0, 1.0, num=series.size)
    target = np.linspace(0.0, 1.0, num=target_len)
    return np.interp(target, original, series)


def _save_pipeline_style_centroids_figure(
    path: Path,
    group_id: str,
    centroids: np.ndarray,
    muscle_names: list[str],
    cluster_members: pd.DataFrame,
    trial_summary: pd.DataFrame,
    activation_map: dict[tuple[str, int], np.ndarray],
    cfg: dict[str, Any],
) -> None:
    rep_w_rows: list[dict[str, Any]] = []
    rep_h_rows: list[dict[str, Any]] = []

    for cluster_id, centroid in enumerate(np.asarray(centroids, dtype=np.float64)):
        for muscle, value in zip(muscle_names, centroid.tolist()):
            rep_w_rows.append(
                {
                    "group_id": group_id,
                    "cluster_id": int(cluster_id),
                    "muscle": muscle,
                    "W_value": float(value),
                }
            )
        member_subset = cluster_members.loc[cluster_members["cluster_id"] == int(cluster_id)]
        activation_members = [
            activation_map[(str(row["trial_id"]), int(row["component_index"]))]
            for row in member_subset.to_dict("records")
            if (str(row["trial_id"]), int(row["component_index"])) in activation_map
        ]
        mean_activation = (
            np.mean(np.stack(activation_members, axis=0), axis=0)
            if activation_members
            else np.zeros(100, dtype=np.float64)
        )
        for frame_idx, value in enumerate(mean_activation.tolist()):
            rep_h_rows.append(
                {
                    "group_id": group_id,
                    "cluster_id": int(cluster_id),
                    "frame_idx": int(frame_idx),
                    "h_value": float(value),
                }
            )

    step_class = "step" if group_id == "global_step" else "nonstep"
    trial_metadata = trial_summary.loc[
        trial_summary["analysis_step_class"] == step_class,
        ["trial_id", "subject"],
    ].copy()
    save_group_cluster_figure(
        group_id=group_id,
        rep_w=pd.DataFrame(rep_w_rows),
        rep_h=pd.DataFrame(rep_h_rows),
        muscle_names=muscle_names,
        cfg=cfg,
        output_path=path,
        cluster_labels=cluster_members.loc[:, ["cluster_id", "trial_id", "subject"]].copy(),
        trial_metadata=trial_metadata,
    )


def _plot_similarity_heatmap(
    path: Path,
    title: str,
    similarity: np.ndarray,
    professor_labels: list[str],
    pipeline_labels: list[str],
) -> None:
    import matplotlib

    try:
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
    import matplotlib.pyplot as plt

    sim = np.asarray(similarity, dtype=np.float64)
    fig, ax = plt.subplots(figsize=(max(6.0, 0.5 * sim.shape[1]), max(4.0, 0.4 * sim.shape[0])))
    im = ax.imshow(sim, vmin=-1.0, vmax=1.0, cmap="coolwarm", aspect="auto")
    ax.set_title(title)
    ax.set_yticks(range(len(professor_labels)))
    ax.set_yticklabels(professor_labels)
    ax.set_xticks(range(len(pipeline_labels)))
    ax.set_xticklabels(pipeline_labels, rotation=45, ha="right")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _summarize_group_result(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"status": "failed", "reason": "invalid_result_type"}
    duplicates = result.get("duplicates", [])
    summarized = {key: value for key, value in result.items() if key not in {"labels", "sample_map"}}
    for key in ["inertia", "similarity_mean_best"]:
        if key in summarized and summarized[key] is not None and not (isinstance(summarized[key], str)):
            try:
                summarized[key] = float(round(float(summarized[key]), 9))
            except Exception:
                pass
    if isinstance(duplicates, list):
        summarized["duplicates_count"] = int(len(duplicates))
        summarized["duplicates_preview"] = duplicates[:10]
        summarized.pop("duplicates", None)
    return summarized


def main() -> int:
    args = parse_args()
    _ensure_outdir(args.outdir, overwrite=args.overwrite)

    cfg = load_pipeline_config(args.config)
    muscle_names = list(cfg["muscles"]["names"])
    emg_path = str(cfg["input"]["emg_parquet_path"])
    event_path = str(cfg["input"]["event_xlsm_path"])

    baseline_keys = _read_baseline_trial_keys(args.baseline_run)
    baseline_lookup = _read_baseline_trial_lookup(args.baseline_run)

    emg_df = load_emg_table(emg_path)
    event_df = load_event_metadata(event_path, cfg)
    merged = merge_event_metadata(emg_df, event_df)
    trial_records = build_trial_records(merged, cfg)

    current_keys = {_normalize_trial_key(trial.key) for trial in trial_records}
    if current_keys != baseline_keys:
        missing = sorted(baseline_keys - current_keys)[:10]
        extra = sorted(current_keys - baseline_keys)[:10]
        raise ValueError(
            "Selected trials do not match baseline_run/all_trial_window_metadata.csv. "
            f"missing(example)={missing} extra(example)={extra}"
        )

    label_mismatch_rows: list[dict[str, Any]] = []
    for trial in trial_records:
        meta = trial.metadata
        trial_key = _normalize_trial_key(trial.key)
        baseline_info = baseline_lookup.get(trial_key)
        if baseline_info is None:
            raise KeyError(f"Baseline metadata missing trial key: {trial_key}")

        baseline_start = int(baseline_info["analysis_window_start_device"])
        baseline_end = int(baseline_info["analysis_window_end_device"])
        meta_start = int(meta.get("analysis_window_start_device", -1))
        meta_end = int(meta.get("analysis_window_end_device", -1))
        if (meta_start, meta_end) != (baseline_start, baseline_end):
            raise ValueError(
                "Trial window mismatch vs baseline metadata: "
                f"key={trial_key} current=({meta_start},{meta_end}) baseline=({baseline_start},{baseline_end})"
            )

        baseline_step_class = _coerce_step_class(baseline_info.get("analysis_step_class"))
        event_step_class = _step_class_from_metadata(meta)
        if baseline_step_class is None:
            raise ValueError(f"Baseline analysis_step_class is invalid: key={trial_key} value={baseline_info.get('analysis_step_class')}")
        if event_step_class is None:
            raise ValueError(
                "Event-derived analysis_step_class is missing/invalid for trial: "
                f"key={trial_key} meta.analysis_step_class={meta.get('analysis_step_class')} "
                f"meta.analysis_is_step={meta.get('analysis_is_step')} meta.analysis_is_nonstep={meta.get('analysis_is_nonstep')}"
            )
        if baseline_step_class != event_step_class:
            label_mismatch_rows.append(
                {
                    "subject": trial_key[0],
                    "velocity": float(trial_key[1]),
                    "trial_num": int(trial_key[2]),
                    "baseline_step_class": baseline_step_class,
                    "event_step_class": event_step_class,
                }
            )

    if label_mismatch_rows:
        mismatch_path = args.outdir / "step_label_mismatches.csv"
        pd.DataFrame(label_mismatch_rows).to_csv(mismatch_path, index=False, encoding="utf-8-sig")
        raise ValueError(
            "Step/nonstep labels differ between baseline metadata and event-derived metadata "
            f"for {len(label_mismatch_rows)} trials. See: {mismatch_path}"
        )

    trial_rows: list[dict[str, Any]] = []
    synergy_vectors: list[np.ndarray] = []
    synergy_rows: list[dict[str, Any]] = []
    activation_map: dict[tuple[str, int], np.ndarray] = {}

    for trial in trial_records:
        meta = trial.metadata
        trial_key = _normalize_trial_key(trial.key)
        baseline_info = baseline_lookup.get(trial_key)
        if baseline_info is None:
            raise KeyError(f"Baseline metadata missing trial key: {trial_key}")

        baseline_step_class = _coerce_step_class(baseline_info.get("analysis_step_class"))
        event_step_class = _step_class_from_metadata(meta)
        if baseline_step_class is None or event_step_class is None:
            raise RuntimeError("Step label validation should have been enforced before NMF execution.")
        step_class = event_step_class
        group_id = _group_id_for_step_class(step_class)

        trial_id = f"{trial.key[0]}_v{trial.key[1]}_T{trial.key[2]}"
        X_trial = trial.frame[muscle_names].to_numpy(dtype=np.float64)
        result = professor_nmf_min_rank(X_trial, vaf_threshold=args.vaf_threshold, seed=args.seed)

        trial_rows.append(
            {
                "subject": str(trial.key[0]),
                "velocity": float(trial.key[1]),
                "trial_num": int(trial.key[2]),
                "trial_id": trial_id,
                "analysis_step_class": step_class,
                "baseline_step_class": baseline_step_class,
                "analysis_group_id": group_id,
                "n_frames": int(X_trial.shape[0]),
                "n_muscles": int(X_trial.shape[1]),
                "prof_status": result.status,
                "prof_n_components": int(result.n_components),
                "prof_vaf": float(result.vaf) if not np.isnan(result.vaf) else np.nan,
                "pipeline_status": baseline_info["status"],
                "pipeline_n_components": int(baseline_info["n_components"]),
                "pipeline_vaf": float(baseline_info["vaf"]),
            }
        )

        if result.status != "ok":
            continue
        H = np.asarray(result.H_structure, dtype=np.float64)
        activations = np.asarray(result.W_activation, dtype=np.float64)
        for component_index in range(H.shape[0]):
            synergy_vectors.append(H[component_index].astype(np.float64, copy=False))
            component_scale = float(np.max(H[component_index])) if H.shape[1] else 1.0
            if component_scale <= 0.0:
                component_scale = 1.0
            activation_map[(trial_id, int(component_index))] = _resample_series(
                activations[:, component_index] * component_scale,
                100,
            )
            synergy_rows.append(
                {
                    "group_id": group_id,
                    "analysis_step_class": step_class,
                    "baseline_step_class": baseline_step_class,
                    "trial_id": trial_id,
                    "subject": str(trial.key[0]),
                    "velocity": float(trial.key[1]),
                    "trial_num": int(trial.key[2]),
                    "component_index": int(component_index),
                    "trial_synergy_count": int(H.shape[0]),
                }
            )

    trial_summary = pd.DataFrame(trial_rows).sort_values(["analysis_step_class", "subject", "velocity", "trial_num"])
    trial_summary_path = args.outdir / "professor_trial_summary.csv"
    trial_summary.to_csv(trial_summary_path, index=False, encoding="utf-8-sig")

    synergy_meta = pd.DataFrame(synergy_rows)
    if synergy_meta.empty:
        raise RuntimeError("No professor-style synergy vectors were produced.")

    group_results: dict[str, Any] = {}
    for group_id, class_name in [("global_step", "step"), ("global_nonstep", "nonstep")]:
        mask = synergy_meta["group_id"] == group_id
        if not mask.any():
            group_results[group_id] = {"status": "failed", "reason": "no_vectors"}
            continue

        indices = synergy_meta.index[mask].to_numpy()
        vectors = np.stack([synergy_vectors[int(i)] for i in indices], axis=0)
        trial_ids = synergy_meta.loc[mask, "trial_id"].astype(str).tolist()
        k_min = int(max(2, synergy_meta.loc[mask, "trial_synergy_count"].max()))

        cluster_result = professor_kmeans_within_trial_unique(
            vectors,
            trial_ids,
            k_min=k_min,
            k_max=int(args.k_max),
            seed=int(args.seed),
        )
        group_results[group_id] = cluster_result
        if not str(cluster_result.get("status", "")).startswith("success"):
            continue

        labels = np.asarray(cluster_result["labels"], dtype=int)
        n_clusters = int(cluster_result["n_clusters"])
        centroids = _centroids_from_labels(vectors, labels, n_clusters=n_clusters)

        members = synergy_meta.loc[mask].copy()
        members["cluster_id"] = labels
        members.to_csv(args.outdir / f"{group_id}_cluster_members.csv", index=False, encoding="utf-8-sig")

        _write_long_centroids(args.outdir / f"{group_id}_centroids_professor.csv", group_id, centroids, muscle_names)
        _save_pipeline_style_centroids_figure(
            args.outdir / f"{group_id}_centroids_professor.png",
            group_id,
            centroids,
            muscle_names,
            members,
            trial_summary,
            activation_map,
            cfg,
        )

        pipeline_path = args.baseline_run / group_id / "representative_W_posthoc.csv"
        pipeline_centroids = _load_pipeline_representative_W(pipeline_path, muscle_names)
        similarity = _l2_normalize_rows(centroids) @ _l2_normalize_rows(pipeline_centroids).T
        pd.DataFrame(similarity).to_csv(args.outdir / f"{group_id}_similarity_professor_vs_pipeline.csv", index=False, encoding="utf-8-sig")
        _plot_similarity_heatmap(
            args.outdir / f"{group_id}_similarity_professor_vs_pipeline.png",
            f"{group_id} similarity (cosine): professor vs pipeline",
            similarity,
            professor_labels=[f"P{idx}" for idx in range(similarity.shape[0])],
            pipeline_labels=[f"Pipe{idx}" for idx in range(similarity.shape[1])],
        )

        group_results[group_id]["pipeline_n_clusters"] = int(pipeline_centroids.shape[0])
        group_results[group_id]["similarity_mean_best"] = float(np.max(similarity, axis=1).mean()) if similarity.size else float("nan")

    summary = {
        "baseline_run": str(args.baseline_run),
        "config_path": str(args.config),
        "inputs": {"emg_parquet_path": emg_path, "event_xlsm_path": event_path},
        "parameters": {
            "vaf_threshold": float(args.vaf_threshold),
            "seed": int(args.seed),
            "k_max": int(args.k_max),
            "nmf_init": "random",
            "nmf_random_state": int(args.seed),
        },
        "assumptions": {
            "step_label_source": "event_metadata",
            "step_label_matches_baseline": True,
            "nmf_vectors_included": ["ok"],
        },
        "counts": {
            "n_trials": int(trial_summary.shape[0]),
            "n_step": int((trial_summary["analysis_step_class"] == "step").sum()),
            "n_nonstep": int((trial_summary["analysis_step_class"] == "nonstep").sum()),
            "n_synergy_vectors": int(synergy_meta.shape[0]),
        },
        "rank_distributions": {
            "professor_all": trial_summary["prof_n_components"].value_counts().sort_index().to_dict(),
            "pipeline_all": trial_summary["pipeline_n_components"].value_counts().sort_index().to_dict(),
            "professor_step": trial_summary.loc[trial_summary["analysis_step_class"] == "step", "prof_n_components"]
            .value_counts()
            .sort_index()
            .to_dict(),
            "professor_nonstep": trial_summary.loc[trial_summary["analysis_step_class"] == "nonstep", "prof_n_components"]
            .value_counts()
            .sort_index()
            .to_dict(),
        },
        "versions": {
            "python": sys.version,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "polars": pl.__version__,
        },
    }
    summary["group_results"] = {group_id: _summarize_group_result(result) for group_id, result in group_results.items()}
    summary_path = args.outdir / "summary.json"
    _write_json(summary_path, summary)

    checksum_lines: list[str] = []
    for path in sorted(args.outdir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "checksums.md5":
            continue
        if path.suffix.lower() not in {".csv", ".json"}:
            continue
        rel = path.relative_to(args.outdir).as_posix()
        checksum_lines.append(f"{_md5_file(path)}  {rel}")
    checksums_path = args.outdir / "checksums.md5"
    with checksums_path.open("w", encoding="utf-8-sig") as handle:
        handle.write("\n".join(checksum_lines) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
