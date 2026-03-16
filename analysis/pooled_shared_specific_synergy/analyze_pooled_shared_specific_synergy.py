"""Run pooled step/nonstep synergy clustering as an analysis-only workflow.

This script revalidates baseline trial windows, re-extracts trial NMF,
pools all step/nonstep W vectors into one shared cluster space,
and exports pooled CSV, figure, and report artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

try:
    matplotlib.use("Agg", force=True)
except Exception:
    pass
import matplotlib.pyplot as plt
from matplotlib import font_manager

from src.emg_pipeline import build_trial_records, load_emg_table, load_event_metadata, merge_event_metadata
from src.emg_pipeline.config import load_pipeline_config
from src.synergy_stats.clustering import SubjectFeatureResult, cluster_feature_group, describe_clustering_runtime
from src.synergy_stats.nmf import describe_nmf_runtime, extract_trial_features


KOREAN_FONT_CANDIDATES = (
    "NanumGothic",
    "NanumBarunGothic",
    "Malgun Gothic",
    "AppleGothic",
    "Noto Sans CJK KR",
    "Noto Sans KR",
)


@dataclass
class TrialCase:
    """One baseline-aligned trial that will be re-analyzed in analysis/."""

    key: tuple[str, float, int]
    trial_id: str
    trial_record: Any
    baseline_info: dict[str, Any]
    step_class: str
    group_id: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "configs" / "global_config.yaml")
    parser.add_argument("--baseline-run", type=Path, default=REPO_ROOT / "outputs" / "runs" / "default_run")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=SCRIPT_DIR / "artifacts" / "dev_run",
        help="Output directory for analysis-only pooled artifacts.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and baseline alignment only.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output directory if it exists.")
    parser.add_argument("--seed", type=int, default=None, help="Override runtime/NMF/clustering seed.")
    parser.add_argument("--nmf-backend", type=str, default="", help="Optional NMF backend override.")
    parser.add_argument("--clustering-algorithm", type=str, default="", help="Optional clustering backend override.")
    parser.add_argument("--max-clusters", type=int, default=None, help="Optional clustering max K override.")
    parser.add_argument("--repeats", type=int, default=None, help="Optional observed KMeans restart override.")
    parser.add_argument("--gap-ref-n", type=int, default=None, help="Optional gap-statistic reference sample count.")
    parser.add_argument("--gap-ref-restarts", type=int, default=None, help="Optional gap-statistic fit restart count.")
    parser.add_argument(
        "--uniqueness-candidate-restarts",
        type=int,
        default=None,
        help="Optional zero-duplicate search restart count.",
    )
    return parser.parse_args()


def _configure_fonts() -> None:
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    preferred_font = next((name for name in KOREAN_FONT_CANDIDATES if name in available_fonts), None)
    if preferred_font is not None:
        matplotlib.rcParams["font.family"] = [preferred_font]
    matplotlib.rcParams["axes.unicode_minus"] = False


def _ensure_outdir(path: Path, *, overwrite: bool) -> None:
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"Output directory exists: {path} (use --overwrite)")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_csv(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(path, include_bom=True)


def _md5_file(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_md5_manifest(outdir: Path) -> Path:
    checksum_lines = []
    for path in sorted(outdir.rglob("*")):
        if not path.is_file() or path.name == "checksums.md5":
            continue
        rel = path.relative_to(outdir).as_posix()
        checksum_lines.append(f"{_md5_file(path)}  {rel}")
    checksums_path = outdir / "checksums.md5"
    checksums_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8-sig")
    return checksums_path


def _normalize_trial_key(subject: Any, velocity: Any, trial_num: Any) -> tuple[str, float, int]:
    return (str(subject).strip(), float(velocity), int(trial_num))


def _trial_id(subject: Any, velocity: Any, trial_num: Any) -> str:
    return f"{str(subject).strip()}_v{float(velocity):g}_T{int(trial_num)}"


def _source_trial_key(subject: Any, velocity: Any, trial_num: Any) -> str:
    return f"{str(subject).strip()}|{float(velocity):g}|{int(trial_num)}"


def _coerce_step_class(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
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
    try:
        if value != value:
            return False
    except Exception:
        pass
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _step_class_from_metadata(meta: dict[str, Any]) -> str | None:
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
    return "global_step" if step_class == "step" else "global_nonstep"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, tuple):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, float)):
        scalar = float(value)
        return round(scalar, 8) if math.isfinite(scalar) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _display_repo_relative(path_like: str | Path) -> str:
    path = Path(path_like)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_config(config_path: Path, args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = load_pipeline_config(config_path)
    notes: dict[str, Any] = {
        "config_path": str(config_path),
        "nmf_backend_requested": str(cfg.get("feature_extractor", {}).get("nmf", {}).get("backend", "")),
        "nmf_backend_effective": "",
        "nmf_backend_note": "",
        "clustering_algorithm_requested": str(cfg.get("synergy_clustering", {}).get("algorithm", "")),
        "clustering_algorithm_effective": "",
        "clustering_backend_note": "",
    }
    if args.seed is not None:
        cfg.setdefault("runtime", {})["seed"] = int(args.seed)
        cfg.setdefault("feature_extractor", {}).setdefault("nmf", {})["random_state"] = int(args.seed)
        cfg.setdefault("synergy_clustering", {})["random_state"] = int(args.seed)
    if args.nmf_backend:
        cfg.setdefault("feature_extractor", {}).setdefault("nmf", {})["backend"] = str(args.nmf_backend).strip()
    if args.clustering_algorithm:
        cfg.setdefault("synergy_clustering", {})["algorithm"] = str(args.clustering_algorithm).strip()
    if args.max_clusters is not None:
        cfg.setdefault("synergy_clustering", {})["max_clusters"] = int(args.max_clusters)
    if args.repeats is not None:
        cfg.setdefault("synergy_clustering", {})["repeats"] = int(args.repeats)
    if args.gap_ref_n is not None:
        cfg.setdefault("synergy_clustering", {})["gap_ref_n"] = int(args.gap_ref_n)
    if args.gap_ref_restarts is not None:
        cfg.setdefault("synergy_clustering", {})["gap_ref_restarts"] = int(args.gap_ref_restarts)
    if args.uniqueness_candidate_restarts is not None:
        cfg.setdefault("synergy_clustering", {})["uniqueness_candidate_restarts"] = int(args.uniqueness_candidate_restarts)

    nmf_cfg = cfg.setdefault("feature_extractor", {}).setdefault("nmf", {})
    try:
        runtime = describe_nmf_runtime(nmf_cfg)
        notes["nmf_backend_effective"] = runtime.get("backend", str(nmf_cfg.get("backend", "")))
    except Exception as exc:
        configured = str(nmf_cfg.get("backend", "auto")).strip().lower() or "auto"
        if configured == "torchnmf":
            nmf_cfg["backend"] = "sklearn_nmf"
            notes["nmf_backend_effective"] = "sklearn_nmf"
            notes["nmf_backend_note"] = f"Fell back from torchnmf to sklearn_nmf: {exc}"
        else:
            raise

    clustering_cfg = cfg.setdefault("synergy_clustering", {})
    try:
        runtime = describe_clustering_runtime(clustering_cfg)
        notes["clustering_algorithm_effective"] = runtime.get("algorithm", str(clustering_cfg.get("algorithm", "")))
    except Exception as exc:
        configured = str(clustering_cfg.get("algorithm", "sklearn_kmeans")).strip().lower() or "sklearn_kmeans"
        if configured == "torch_kmeans":
            clustering_cfg["algorithm"] = "sklearn_kmeans"
            notes["clustering_algorithm_effective"] = "sklearn_kmeans"
            notes["clustering_backend_note"] = f"Fell back from torch_kmeans to sklearn_kmeans: {exc}"
        else:
            raise

    notes["seed"] = int(cfg.get("runtime", {}).get("seed", 42))
    notes["target_windows"] = int(
        cfg.get("synergy_clustering", {})
        .get("representative", {})
        .get("h_output_interpolation", {})
        .get("target_windows", 100)
    )
    return cfg, notes


def load_baseline_trial_windows(baseline_run: Path) -> tuple[pl.DataFrame, dict[tuple[str, float, int], dict[str, Any]]]:
    path = baseline_run / "all_trial_window_metadata.csv"
    baseline = pl.read_csv(path)
    lookup: dict[tuple[str, float, int], dict[str, Any]] = {}
    required = {
        "subject",
        "velocity",
        "trial_num",
        "analysis_step_class",
        "analysis_window_start_device",
        "analysis_window_end_device",
        "analysis_window_source",
        "analysis_window_is_surrogate",
    }
    missing = sorted(required.difference(set(baseline.columns)))
    if missing:
        raise ValueError(f"Baseline metadata missing required columns: {missing}")
    for row in baseline.to_dicts():
        key = _normalize_trial_key(row["subject"], row["velocity"], row["trial_num"])
        lookup[key] = row
    return baseline, lookup


def resolve_analysis_inputs(cfg: dict[str, Any]) -> dict[str, Any]:
    inputs = cfg.get("input", {})
    return {
        "emg_parquet_path": str(inputs["emg_parquet_path"]),
        "event_xlsm_path": str(inputs["event_xlsm_path"]),
        "muscle_names": list(cfg["muscles"]["names"]),
    }


def rebuild_selected_trial_table(
    cfg: dict[str, Any],
    baseline_windows: pl.DataFrame,
) -> tuple[list[TrialCase], dict[str, Any]]:
    inputs = resolve_analysis_inputs(cfg)
    emg_df = load_emg_table(inputs["emg_parquet_path"])
    event_df = load_event_metadata(inputs["event_xlsm_path"], cfg)
    merged = merge_event_metadata(emg_df, event_df)
    trial_records = build_trial_records(merged, cfg)

    baseline_keys = {
        _normalize_trial_key(row["subject"], row["velocity"], row["trial_num"])
        for row in baseline_windows.select(["subject", "velocity", "trial_num"]).to_dicts()
    }
    current_keys = {_normalize_trial_key(*trial.key) for trial in trial_records}
    if current_keys != baseline_keys:
        missing = sorted(baseline_keys - current_keys)[:10]
        extra = sorted(current_keys - baseline_keys)[:10]
        raise ValueError(
            "Selected trials do not match baseline_run/all_trial_window_metadata.csv. "
            f"missing(example)={missing} extra(example)={extra}"
        )

    baseline_lookup = {
        _normalize_trial_key(row["subject"], row["velocity"], row["trial_num"]): row for row in baseline_windows.to_dicts()
    }
    selected_trials: list[TrialCase] = []
    label_mismatches: list[dict[str, Any]] = []
    window_mismatches: list[dict[str, Any]] = []
    for trial in trial_records:
        key = _normalize_trial_key(*trial.key)
        baseline_info = baseline_lookup.get(key)
        if baseline_info is None:
            raise KeyError(f"Baseline metadata missing trial key: {key}")
        event_step_class = _step_class_from_metadata(trial.metadata)
        baseline_step_class = _coerce_step_class(baseline_info.get("analysis_step_class"))
        if event_step_class != baseline_step_class:
            label_mismatches.append(
                {
                    "subject": key[0],
                    "velocity": key[1],
                    "trial_num": key[2],
                    "event_step_class": event_step_class,
                    "baseline_step_class": baseline_step_class,
                }
            )
        event_window = (
            int(trial.metadata.get("analysis_window_start_device", -1)),
            int(trial.metadata.get("analysis_window_end_device", -1)),
        )
        baseline_window = (
            int(baseline_info["analysis_window_start_device"]),
            int(baseline_info["analysis_window_end_device"]),
        )
        if event_window != baseline_window:
            window_mismatches.append(
                {
                    "subject": key[0],
                    "velocity": key[1],
                    "trial_num": key[2],
                    "event_window": event_window,
                    "baseline_window": baseline_window,
                }
            )
        if baseline_step_class not in {"step", "nonstep"}:
            raise ValueError(f"Unexpected baseline analysis_step_class for key={key}: {baseline_step_class}")
        selected_trials.append(
            TrialCase(
                key=key,
                trial_id=_trial_id(*key),
                trial_record=trial,
                baseline_info=baseline_info,
                step_class=baseline_step_class,
                group_id=_group_id_for_step_class(baseline_step_class),
            )
        )
    if label_mismatches:
        raise ValueError(f"Baseline/event step labels differ for {len(label_mismatches)} trials: {label_mismatches[:5]}")
    if window_mismatches:
        raise ValueError(f"Baseline/event analysis windows differ for {len(window_mismatches)} trials: {window_mismatches[:5]}")
    summary = {
        "n_trials": len(selected_trials),
        "n_subjects": len({case.key[0] for case in selected_trials}),
        "n_step_trials": sum(case.step_class == "step" for case in selected_trials),
        "n_nonstep_trials": sum(case.step_class == "nonstep" for case in selected_trials),
    }
    return selected_trials, summary


def extract_trial_matrix(trial_case: TrialCase, muscle_cols: list[str]) -> np.ndarray:
    return trial_case.trial_record.frame[muscle_cols].to_numpy(dtype=np.float32)


def fit_trial_nmf_with_vaf(X_trial: np.ndarray, cfg: dict[str, Any]) -> Any:
    return extract_trial_features(X_trial, cfg)


def build_feature_rows(
    trial_cases: list[TrialCase],
    cfg: dict[str, Any],
    muscle_cols: list[str],
) -> tuple[list[SubjectFeatureResult], pl.DataFrame]:
    feature_rows: list[SubjectFeatureResult] = []
    component_rows: list[dict[str, Any]] = []
    for trial_case in trial_cases:
        X_trial = extract_trial_matrix(trial_case, muscle_cols)
        bundle = fit_trial_nmf_with_vaf(X_trial, cfg)
        bundle.meta.update(
            {
                "group_id": trial_case.group_id,
                "trial_id": trial_case.trial_id,
                "source_trial_key": _source_trial_key(*trial_case.key),
                "analysis_step_class": trial_case.step_class,
                "analysis_is_step": trial_case.step_class == "step",
                "analysis_is_nonstep": trial_case.step_class == "nonstep",
                "analysis_window_source": trial_case.baseline_info["analysis_window_source"],
                "analysis_window_is_surrogate": bool(trial_case.baseline_info["analysis_window_is_surrogate"]),
                "analysis_window_start_device": int(trial_case.baseline_info["analysis_window_start_device"]),
                "analysis_window_end_device": int(trial_case.baseline_info["analysis_window_end_device"]),
                "analysis_window_duration_device_frames": int(
                    trial_case.baseline_info["analysis_window_end_device"] - trial_case.baseline_info["analysis_window_start_device"]
                ),
                "analysis_selected_group": True,
                "n_frames": int(X_trial.shape[0]),
                "n_muscles": int(X_trial.shape[1]),
                "analysis_subject_mean_step_latency": trial_case.baseline_info.get("analysis_subject_mean_step_latency"),
            }
        )
        feature_rows.append(
            SubjectFeatureResult(
                subject=trial_case.key[0],
                velocity=trial_case.key[1],
                trial_num=trial_case.key[2],
                bundle=bundle,
            )
        )
        for component_index in range(bundle.W_muscle.shape[1]):
            component_rows.append(
                {
                    "subject": trial_case.key[0],
                    "velocity": trial_case.key[1],
                    "trial_num": trial_case.key[2],
                    "trial_id": trial_case.trial_id,
                    "source_trial_key": _source_trial_key(*trial_case.key),
                    "step_TF": trial_case.step_class,
                    "group_id": trial_case.group_id,
                    "component_idx": int(component_index),
                    "n_components_selected": int(bundle.W_muscle.shape[1]),
                    "n_frames": int(X_trial.shape[0]),
                    "vaf": float(bundle.meta.get("vaf", np.nan)),
                    "extractor_backend": str(bundle.meta.get("extractor_backend", "")),
                    "w_vector": bundle.W_muscle[:, component_index].astype(np.float64).tolist(),
                    "h_vector": bundle.H_time[:, component_index].astype(np.float64).tolist(),
                }
            )
    return feature_rows, pl.from_dicts(component_rows)


def search_pooled_k(feature_rows: list[SubjectFeatureResult], cfg: dict[str, Any]) -> dict[str, Any]:
    cluster_result = cluster_feature_group(feature_rows, cfg["synergy_clustering"], group_id="pooled_step_nonstep")
    if cluster_result.get("status") != "success":
        raise RuntimeError(f"Pooled clustering failed: {cluster_result.get('reason', 'unknown clustering failure')}")
    duplicate_count = int(cluster_result.get("duplicate_trial_count_by_k", {}).get(cluster_result["k_selected"], 0))
    if duplicate_count != 0:
        raise RuntimeError(
            f"Expected zero duplicates at selected K={cluster_result['k_selected']}, got {duplicate_count}."
        )
    return cluster_result


def fit_pooled_clusters(component_df: pl.DataFrame, cluster_result: dict[str, Any]) -> pl.DataFrame:
    labels = np.asarray(cluster_result["labels"], dtype=np.int32)
    sample_map = cluster_result["sample_map"]
    label_rows = []
    for sample, label in zip(sample_map, labels.tolist()):
        label_rows.append(
            {
                "subject": str(sample["subject"]),
                "velocity": float(sample["velocity"]),
                "trial_num": int(sample["trial_num"]),
                "component_idx": int(sample["component_index"]),
                "cluster_id": int(label),
            }
        )
    labels_df = pl.from_dicts(label_rows)
    return component_df.join(labels_df, on=["subject", "velocity", "trial_num", "component_idx"], how="inner")


def interpolate_h_to_100(h_vec: np.ndarray, target_windows: int = 100) -> np.ndarray:
    values = np.asarray(h_vec, dtype=np.float64)
    if values.size == 0:
        return np.zeros(target_windows, dtype=np.float64)
    if values.size == target_windows:
        return values.astype(np.float64)
    x_old = np.linspace(0.0, 1.0, values.size)
    x_new = np.linspace(0.0, 1.0, target_windows)
    return np.interp(x_new, x_old, values).astype(np.float64)


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= 0.0:
        return float("nan")
    return float(np.dot(left, right) / denom)


def _corr_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.size <= 1 or right.size <= 1:
        return float("nan")
    if np.allclose(np.std(left), 0.0) or np.allclose(np.std(right), 0.0):
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    vec = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return vec
    return vec / norm


def _subject_norm_stats(members_pdf: Any, cluster_id: int, strategy: str) -> tuple[float, float]:
    strategy_df = members_pdf[members_pdf["step_TF"] == strategy]
    if strategy_df.empty:
        return float("nan"), float("nan")
    subject_totals = strategy_df.groupby("subject").size().rename("subject_total")
    cluster_counts = (
        strategy_df.loc[strategy_df["cluster_id"] == cluster_id]
        .groupby("subject")
        .size()
        .rename("cluster_count")
    )
    aligned = subject_totals.to_frame().join(cluster_counts, how="left").fillna({"cluster_count": 0.0})
    ratios = (aligned["cluster_count"] / aligned["subject_total"]).to_numpy(dtype=np.float64)
    if ratios.size == 0:
        return float("nan"), float("nan")
    return float(np.mean(ratios)), float(np.std(ratios, ddof=0))


def summarize_cluster_outputs(
    members_df: pl.DataFrame,
    cluster_result: dict[str, Any],
    muscle_names: list[str],
    target_windows: int,
) -> dict[str, pl.DataFrame | dict[str, Any]]:
    members_pdf = members_df.to_pandas()
    cluster_ids = sorted(int(value) for value in members_df["cluster_id"].unique().to_list())
    rep_w_rows: list[dict[str, Any]] = []
    rep_h_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    step_vectors_by_cluster: dict[int, np.ndarray | None] = {}
    nonstep_vectors_by_cluster: dict[int, np.ndarray | None] = {}
    pooled_vectors_by_cluster: dict[int, np.ndarray] = {}
    similarity_matrix = np.full((len(cluster_ids), len(cluster_ids)), np.nan, dtype=np.float64)

    for cluster_id in cluster_ids:
        cluster_members = members_pdf[members_pdf["cluster_id"] == cluster_id].copy()
        pooled_w = np.stack(cluster_members["w_vector"].apply(lambda values: np.asarray(values, dtype=np.float64)).tolist(), axis=0)
        pooled_h = np.stack(
            cluster_members["h_vector"].apply(lambda values: interpolate_h_to_100(values, target_windows)).tolist(),
            axis=0,
        )
        pooled_mean = _normalize_vector(pooled_w.mean(axis=0))
        pooled_vectors_by_cluster[cluster_id] = pooled_mean

        for strategy_view, strategy_filter in [("pooled", None), ("step_only", "step"), ("nonstep_only", "nonstep")]:
            view_members = cluster_members if strategy_filter is None else cluster_members[cluster_members["step_TF"] == strategy_filter]
            if view_members.empty:
                continue
            w_stack = np.stack(view_members["w_vector"].apply(lambda values: np.asarray(values, dtype=np.float64)).tolist(), axis=0)
            w_mean = _normalize_vector(w_stack.mean(axis=0))
            w_sd = w_stack.std(axis=0, ddof=0)
            for muscle_index, muscle in enumerate(muscle_names):
                rep_w_rows.append(
                    {
                        "cluster_id": cluster_id,
                        "muscle": muscle,
                        "weight_mean": float(w_mean[muscle_index]),
                        "weight_sd": float(w_sd[muscle_index]),
                        "strategy_view": strategy_view,
                    }
                )

            h_stack = np.stack(
                view_members["h_vector"].apply(lambda values: interpolate_h_to_100(values, target_windows)).tolist(),
                axis=0,
            )
            h_mean = h_stack.mean(axis=0)
            h_sd = h_stack.std(axis=0, ddof=0)
            strategy_name = "pooled" if strategy_filter is None else strategy_filter
            for time_bin, value in enumerate(h_mean.tolist()):
                rep_h_rows.append(
                    {
                        "cluster_id": cluster_id,
                        "strategy": strategy_name,
                        "time_bin": int(time_bin),
                        "h_mean": float(value),
                        "h_sd": float(h_sd[time_bin]),
                        "n_members": int(h_stack.shape[0]),
                    }
                )

            if strategy_view == "step_only":
                step_vectors_by_cluster[cluster_id] = w_mean
            elif strategy_view == "nonstep_only":
                nonstep_vectors_by_cluster[cluster_id] = w_mean

        step_members = cluster_members[cluster_members["step_TF"] == "step"]
        nonstep_members = cluster_members[cluster_members["step_TF"] == "nonstep"]
        step_vector = step_vectors_by_cluster.get(cluster_id)
        nonstep_vector = nonstep_vectors_by_cluster.get(cluster_id)
        summary_rows.append(
            {
                "cluster_id": cluster_id,
                "n_members_total": int(cluster_members.shape[0]),
                "n_members_step": int(step_members.shape[0]),
                "n_members_nonstep": int(nonstep_members.shape[0]),
                "subject_coverage_step": int(step_members["subject"].nunique()),
                "subject_coverage_nonstep": int(nonstep_members["subject"].nunique()),
                "subject_norm_occupancy_step_mean": _subject_norm_stats(members_pdf, cluster_id, "step")[0],
                "subject_norm_occupancy_step_sd": _subject_norm_stats(members_pdf, cluster_id, "step")[1],
                "subject_norm_occupancy_nonstep_mean": _subject_norm_stats(members_pdf, cluster_id, "nonstep")[0],
                "subject_norm_occupancy_nonstep_sd": _subject_norm_stats(members_pdf, cluster_id, "nonstep")[1],
                "step_nonstep_subcentroid_cosine": _cosine_similarity(step_vector, nonstep_vector)
                if step_vector is not None and nonstep_vector is not None
                else float("nan"),
                "step_nonstep_subcentroid_corr": _corr_similarity(step_vector, nonstep_vector)
                if step_vector is not None and nonstep_vector is not None
                else float("nan"),
            }
        )

    for row_index, step_cluster in enumerate(cluster_ids):
        step_vector = step_vectors_by_cluster.get(step_cluster)
        for col_index, nonstep_cluster in enumerate(cluster_ids):
            nonstep_vector = nonstep_vectors_by_cluster.get(nonstep_cluster)
            if step_vector is None or nonstep_vector is None:
                similarity_matrix[row_index, col_index] = np.nan
            else:
                similarity_matrix[row_index, col_index] = _cosine_similarity(step_vector, nonstep_vector)

    members_export = members_df.select(
        [
            "subject",
            "velocity",
            "trial_num",
            "trial_id",
            "source_trial_key",
            "step_TF",
            "group_id",
            "component_idx",
            "n_components_selected",
            "n_frames",
            "vaf",
            "extractor_backend",
            "cluster_id",
        ]
    )
    return {
        "members": members_export.sort(["cluster_id", "step_TF", "subject", "velocity", "trial_num", "component_idx"]),
        "members_detail": members_df.sort(["cluster_id", "step_TF", "subject", "velocity", "trial_num", "component_idx"]),
        "summary": pl.from_dicts(summary_rows).sort("cluster_id"),
        "rep_w": pl.from_dicts(rep_w_rows).sort(["cluster_id", "strategy_view", "muscle"]),
        "rep_h": pl.from_dicts(rep_h_rows).sort(["cluster_id", "strategy", "time_bin"]),
        "similarity_matrix": {
            "cluster_ids": cluster_ids,
            "values": similarity_matrix,
        },
    }


def _series_from_rep_h(rep_h_pdf: Any, cluster_id: int, strategy: str) -> tuple[np.ndarray, np.ndarray, int]:
    subset = rep_h_pdf[(rep_h_pdf["cluster_id"] == cluster_id) & (rep_h_pdf["strategy"] == strategy)].sort_values("time_bin")
    if subset.empty:
        return np.array([]), np.array([]), 0
    return (
        subset["h_mean"].to_numpy(dtype=np.float64),
        subset["h_sd"].to_numpy(dtype=np.float64),
        int(subset["n_members"].iloc[0]),
    )


def generate_figures(outdir: Path, artifacts: dict[str, Any], cfg: dict[str, Any]) -> list[Path]:
    _configure_fonts()
    figure_dir = outdir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    rep_w_pdf = artifacts["rep_w"].to_pandas()
    rep_h_pdf = artifacts["rep_h"].to_pandas()
    summary_pdf = artifacts["summary"].to_pandas().sort_values("cluster_id")
    cluster_ids = summary_pdf["cluster_id"].astype(int).tolist()
    fig_paths: list[Path] = []

    # Figure 1: pooled centroid overview.
    fig, axes = plt.subplots(max(len(cluster_ids), 1), 2, figsize=(14, 3.5 * max(len(cluster_ids), 1)), squeeze=False)
    fig.suptitle("Pooled shared/specific synergy clusters", fontsize=14, fontweight="bold", y=0.995)
    for row_index, cluster_id in enumerate(cluster_ids or [0]):
        ax_w, ax_h = axes[row_index]
        summary_row = summary_pdf.loc[summary_pdf["cluster_id"] == cluster_id].iloc[0]
        w_subset = rep_w_pdf[(rep_w_pdf["cluster_id"] == cluster_id) & (rep_w_pdf["strategy_view"] == "pooled")]
        h_mean, _, _ = _series_from_rep_h(rep_h_pdf, cluster_id, "pooled")
        if w_subset.empty or h_mean.size == 0:
            ax_w.text(0.5, 0.5, "No pooled centroid", ha="center", va="center")
            ax_h.text(0.5, 0.5, "No pooled H", ha="center", va="center")
        else:
            ax_w.bar(w_subset["muscle"], w_subset["weight_mean"], color="#5C7CFA")
            ax_w.tick_params(axis="x", rotation=45)
            ax_h.plot(np.linspace(0, 100, h_mean.size), h_mean, color="#2F9E44", linewidth=2.0)
            ax_h.set_xlim(0.0, 100.0)
        subtitle = (
            f"cluster {cluster_id} | total={int(summary_row['n_members_total'])} "
            f"(step={int(summary_row['n_members_step'])}, nonstep={int(summary_row['n_members_nonstep'])}) | "
            f"coverage step={int(summary_row['subject_coverage_step'])}, nonstep={int(summary_row['subject_coverage_nonstep'])}"
        )
        ax_w.set_title(f"Pooled W\n{subtitle}", fontsize=10)
        ax_h.set_title(f"Pooled H\n{subtitle}", fontsize=10)
        ax_w.set_ylabel("Weight")
        ax_h.set_ylabel("Activation")
        ax_h.set_xlabel("Normalized window (%)")
    fig.tight_layout()
    fig_path = figure_dir / "pooled_clusters.png"
    fig.savefig(fig_path, dpi=int(cfg.get("figures", {}).get("dpi", 150)), bbox_inches="tight")
    plt.close(fig)
    fig_paths.append(fig_path)

    # Figure 2: step vs nonstep W.
    fig, axes = plt.subplots(max(len(cluster_ids), 1), 2, figsize=(14, 3.5 * max(len(cluster_ids), 1)), squeeze=False)
    fig.suptitle("Step vs nonstep sub-centroid W", fontsize=14, fontweight="bold", y=0.995)
    for row_index, cluster_id in enumerate(cluster_ids or [0]):
        summary_row = summary_pdf.loc[summary_pdf["cluster_id"] == cluster_id].iloc[0]
        for col_index, strategy_view in enumerate(["step_only", "nonstep_only"]):
            ax = axes[row_index, col_index]
            subset = rep_w_pdf[(rep_w_pdf["cluster_id"] == cluster_id) & (rep_w_pdf["strategy_view"] == strategy_view)]
            if subset.empty:
                ax.text(0.5, 0.5, f"No {strategy_view}", ha="center", va="center")
            else:
                color = "#5C7CFA" if strategy_view == "step_only" else "#E64980"
                ax.bar(subset["muscle"], subset["weight_mean"], color=color)
                ax.tick_params(axis="x", rotation=45)
            ax.set_ylabel("Weight")
            ax.set_title(
                f"cluster {cluster_id} | {strategy_view} | cosine={summary_row['step_nonstep_subcentroid_cosine']:.3f}"
                if np.isfinite(summary_row["step_nonstep_subcentroid_cosine"])
                else f"cluster {cluster_id} | {strategy_view} | cosine=n/a",
                fontsize=10,
            )
    fig.tight_layout()
    fig_path = figure_dir / "step_vs_nonstep_W.png"
    fig.savefig(fig_path, dpi=int(cfg.get("figures", {}).get("dpi", 150)), bbox_inches="tight")
    plt.close(fig)
    fig_paths.append(fig_path)

    # Figure 3: step vs nonstep H.
    ncols = 2
    nrows = max(1, math.ceil(max(len(cluster_ids), 1) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4.0 * nrows))
    axes = np.atleast_1d(axes).reshape(nrows, ncols)
    fig.suptitle("Step vs nonstep representative H", fontsize=14, fontweight="bold", y=0.995)
    x_axis = np.linspace(0, 100, int(artifacts["report_inputs"]["target_windows"]))
    for ax in axes.flatten():
        ax.axis("off")
    for index, cluster_id in enumerate(cluster_ids):
        ax = axes.flatten()[index]
        ax.axis("on")
        step_mean, step_sd, step_n = _series_from_rep_h(rep_h_pdf, cluster_id, "step")
        non_mean, non_sd, non_n = _series_from_rep_h(rep_h_pdf, cluster_id, "nonstep")
        mean_y_collections: list[np.ndarray] = []
        if step_mean.size:
            ax.plot(x_axis, step_mean, color="#5C7CFA", linewidth=2.0, label="step")
            ax.fill_between(x_axis, step_mean - step_sd, step_mean + step_sd, color="#5C7CFA", alpha=0.2)
            mean_y_collections.append(step_mean)
        if non_mean.size:
            ax.plot(x_axis, non_mean, color="#E64980", linewidth=2.0, linestyle="--", label="nonstep")
            ax.fill_between(x_axis, non_mean - non_sd, non_mean + non_sd, color="#E64980", alpha=0.2)
            mean_y_collections.append(non_mean)
        ax.set_xlim(0.0, 100.0)
        if mean_y_collections:
            all_y = np.concatenate(mean_y_collections)
            ymin, ymax = float(np.nanmin(all_y)), float(np.nanmax(all_y))
            margin = (ymax - ymin) * 0.05 if ymax > ymin else 0.1
            ax.set_ylim(ymin - margin, ymax + margin)
        ax.set_title(f"cluster {cluster_id} | step n={step_n}, nonstep n={non_n}", fontsize=10)
        ax.set_xlabel("Normalized window (%)")
        ax.set_ylabel("Activation")
        ax.legend(loc="best")
    fig.tight_layout()
    fig_path = figure_dir / "step_vs_nonstep_H.png"
    fig.savefig(fig_path, dpi=int(cfg.get("figures", {}).get("dpi", 150)), bbox_inches="tight")
    plt.close(fig)
    fig_paths.append(fig_path)

    # Figure 4: occupancy summary.
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    positions = np.arange(len(cluster_ids), dtype=float)
    width = 0.35
    step_counts = summary_pdf["n_members_step"].to_numpy(dtype=float)
    non_counts = summary_pdf["n_members_nonstep"].to_numpy(dtype=float)
    step_norm = summary_pdf["subject_norm_occupancy_step_mean"].to_numpy(dtype=float)
    non_norm = summary_pdf["subject_norm_occupancy_nonstep_mean"].to_numpy(dtype=float)
    step_norm_sd = summary_pdf["subject_norm_occupancy_step_sd"].to_numpy(dtype=float)
    non_norm_sd = summary_pdf["subject_norm_occupancy_nonstep_sd"].to_numpy(dtype=float)
    top_step = axes[0].bar(positions - width / 2, step_counts, width=width, color="#5C7CFA", label="step")
    top_non = axes[0].bar(positions + width / 2, non_counts, width=width, color="#E64980", label="nonstep")
    axes[0].set_ylabel("Member count")
    axes[0].set_title("Raw pooled member occupancy")
    axes[0].legend()
    for bars, coverage_values in [
        (top_step, summary_pdf["subject_coverage_step"].to_numpy(dtype=int)),
        (top_non, summary_pdf["subject_coverage_nonstep"].to_numpy(dtype=int)),
    ]:
        for bar, coverage in zip(bars, coverage_values.tolist()):
            axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, str(coverage), ha="center", va="bottom", fontsize=9)
    bottom_step = axes[1].bar(
        positions - width / 2,
        step_norm,
        width=width,
        yerr=step_norm_sd,
        color="#5C7CFA",
        label="step",
        capsize=4,
    )
    bottom_non = axes[1].bar(
        positions + width / 2,
        non_norm,
        width=width,
        yerr=non_norm_sd,
        color="#E64980",
        label="nonstep",
        capsize=4,
    )
    axes[1].set_ylabel("Subject-normalized occupancy")
    axes[1].set_title("Subject-normalized cluster occupancy")
    axes[1].set_xticks(positions)
    axes[1].set_xticklabels([str(cluster_id) for cluster_id in cluster_ids])
    axes[1].set_xlabel("cluster_id")
    for bars, coverage_values in [
        (bottom_step, summary_pdf["subject_coverage_step"].to_numpy(dtype=int)),
        (bottom_non, summary_pdf["subject_coverage_nonstep"].to_numpy(dtype=int)),
    ]:
        for bar, coverage in zip(bars, coverage_values.tolist()):
            y_value = bar.get_height() if math.isfinite(float(bar.get_height())) else 0.0
            axes[1].text(bar.get_x() + bar.get_width() / 2, y_value + 0.01, str(coverage), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig_path = figure_dir / "occupancy_summary.png"
    fig.savefig(fig_path, dpi=int(cfg.get("figures", {}).get("dpi", 150)), bbox_inches="tight")
    plt.close(fig)
    fig_paths.append(fig_path)

    # Figure 5: K selection diagnostic.
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    gap_by_k = artifacts["cluster_result"]["gap_by_k"]
    duplicate_by_k = artifacts["cluster_result"]["duplicate_trial_count_by_k"]
    k_values = sorted(int(key) for key in gap_by_k)
    axes[0].plot(k_values, [float(gap_by_k[key]) for key in k_values], marker="o")
    axes[0].axvline(int(artifacts["cluster_result"]["k_lb"]), color="gray", linestyle="--", linewidth=1.5)
    axes[0].axvline(int(artifacts["cluster_result"]["k_gap_raw"]), color="#E64980", linestyle="--", linewidth=1.5)
    axes[0].set_ylabel("Gap statistic")
    axes[0].set_title("Gap-statistic K search")
    axes[1].plot(k_values, [int(duplicate_by_k[key]) for key in k_values], marker="o")
    axes[1].axvline(int(artifacts["cluster_result"]["k_lb"]), color="gray", linestyle="--", linewidth=1.5)
    axes[1].axvline(int(artifacts["cluster_result"]["k_selected"]), color="#2F9E44", linestyle="--", linewidth=1.5)
    axes[1].set_ylabel("Duplicate trial count")
    axes[1].set_xlabel("K")
    axes[1].set_title("Zero-duplicate feasibility")
    fig.tight_layout()
    fig_path = figure_dir / "k_selection_diagnostic.png"
    fig.savefig(fig_path, dpi=int(cfg.get("figures", {}).get("dpi", 150)), bbox_inches="tight")
    plt.close(fig)
    fig_paths.append(fig_path)

    # Figure 6: similarity heatmap.
    similarity = np.asarray(artifacts["similarity_matrix"]["values"], dtype=np.float64)
    fig, ax = plt.subplots(figsize=(8, 8))
    im = ax.imshow(similarity, vmin=0.0, vmax=1.0, cmap="Blues")
    ax.set_xticks(range(len(cluster_ids)))
    ax.set_yticks(range(len(cluster_ids)))
    ax.set_xticklabels([str(cluster_id) for cluster_id in cluster_ids])
    ax.set_yticklabels([str(cluster_id) for cluster_id in cluster_ids])
    ax.set_xlabel("nonstep cluster_id")
    ax.set_ylabel("step cluster_id")
    ax.set_title("Step vs nonstep sub-centroid cosine similarity")
    for row_index in range(similarity.shape[0]):
        for col_index in range(similarity.shape[1]):
            value = similarity[row_index, col_index]
            label = "n/a" if not np.isfinite(value) else f"{value:.2f}"
            ax.text(col_index, row_index, label, ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig_path = figure_dir / "subcentroid_similarity_heatmap.png"
    fig.savefig(fig_path, dpi=int(cfg.get("figures", {}).get("dpi", 150)), bbox_inches="tight")
    plt.close(fig)
    fig_paths.append(fig_path)

    return fig_paths


def _format_markdown_table(frame: pl.DataFrame, precision: int = 3) -> str:
    if frame.is_empty():
        return "_No rows_"
    rows = frame.to_dicts()
    columns = frame.columns
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                if math.isfinite(value):
                    values.append(f"{value:.{precision}f}")
                else:
                    values.append("n/a")
            else:
                values.append(str(value))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *body])


def write_generated_report(outdir: Path, artifacts: dict[str, Any], runtime_notes: dict[str, Any]) -> Path:
    summary_df = artifacts["summary"]
    members_df = artifacts["members"]
    figure_files = [
        "pooled_clusters.png",
        "step_vs_nonstep_W.png",
        "step_vs_nonstep_H.png",
        "occupancy_summary.png",
        "k_selection_diagnostic.png",
        "subcentroid_similarity_heatmap.png",
    ]
    summary_view = summary_df.select(
        [
            "cluster_id",
            "n_members_total",
            "n_members_step",
            "n_members_nonstep",
            "subject_coverage_step",
            "subject_coverage_nonstep",
            "step_nonstep_subcentroid_cosine",
        ]
    )
    high_similarity = summary_df.filter(pl.col("step_nonstep_subcentroid_cosine") >= 0.8).sort(
        "step_nonstep_subcentroid_cosine",
        descending=True,
    )
    report_lines = [
        "# Pooled Shared/Specific Synergy Report",
        "",
        "## Research Question",
        "",
        "This analysis asks whether step and nonstep synergies occupy the same pooled cluster space when all trial-level `W` vectors are clustered together, and how strongly each shared cluster is dominated by one condition or balanced across both conditions.",
        "",
        "## Inputs",
        "",
        f"- Config: `{runtime_notes['config_path']}`",
        f"- Baseline run: `{artifacts['report_inputs']['baseline_run']}`",
        f"- EMG parquet: `{artifacts['report_inputs']['emg_parquet_path']}`",
        f"- Event workbook: `{artifacts['report_inputs']['event_xlsm_path']}`",
        "",
        "## Methodology",
        "",
        f"- Selected trials were reconstructed from the event workbook and required to match baseline keys exactly (`n_trials={artifacts['report_inputs']['n_trials']}`, `n_subjects={artifacts['report_inputs']['n_subjects']}`).",
        "- Trial-level NMF was re-extracted per selected trial with the pipeline-aligned VAF threshold rule (`VAF >= 0.90`).",
        f"- Effective NMF backend: `{runtime_notes['nmf_backend_effective']}`.",
        f"- Effective clustering backend: `{runtime_notes['clustering_algorithm_effective']}`.",
        f"- Pooled clustering used `k_lb={artifacts['cluster_result']['k_lb']}`, `k_gap_raw={artifacts['cluster_result']['k_gap_raw']}`, and `k_selected={artifacts['cluster_result']['k_selected']}` with a zero-duplicate constraint.",
        f"- Final pooled component count: `{members_df.height}`.",
        "",
    ]
    if runtime_notes.get("nmf_backend_note"):
        report_lines.extend(["### Runtime Note: NMF", "", runtime_notes["nmf_backend_note"], ""])
    if runtime_notes.get("clustering_backend_note"):
        report_lines.extend(["### Runtime Note: Clustering", "", runtime_notes["clustering_backend_note"], ""])

    report_lines.extend(
        [
            "## Results",
            "",
            f"- Duplicate trial count at selected `K`: `{artifacts['cluster_result']['duplicate_trial_count_by_k'][artifacts['cluster_result']['k_selected']]}`.",
            f"- Unique step subjects represented in pooled members: `{members_df.filter(pl.col('step_TF') == 'step').select(pl.col('subject').n_unique()).item()}`.",
            f"- Unique nonstep subjects represented in pooled members: `{members_df.filter(pl.col('step_TF') == 'nonstep').select(pl.col('subject').n_unique()).item()}`.",
            "",
            "### Cluster Occupancy Summary",
            "",
            _format_markdown_table(summary_view, precision=3),
            "",
            "### High Sub-centroid Similarity Clusters",
            "",
            _format_markdown_table(
                high_similarity.select(["cluster_id", "step_nonstep_subcentroid_cosine", "n_members_step", "n_members_nonstep"])
                if not high_similarity.is_empty()
                else high_similarity,
                precision=3,
            ),
            "",
            "## Figure Guide",
            "",
            "- `pooled_clusters.png`: shows each pooled centroid with its pooled representative `H`, so we can see the shared cluster vocabulary at a glance.",
            "- `step_vs_nonstep_W.png`: compares step-only and nonstep-only sub-centroids within each cluster, highlighting whether muscle composition is shared or condition-specific.",
            "- `step_vs_nonstep_H.png`: overlays step and nonstep representative activations within each cluster, exposing timing or magnitude shifts even when `W` stays similar.",
            "- `occupancy_summary.png`: separates raw member counts from subject-normalized occupancy, reducing the risk of over-interpreting clusters dominated by a few subjects.",
            "- `k_selection_diagnostic.png`: shows how the gap-statistic recommendation and the zero-duplicate feasibility rule jointly determined the final `K`.",
            "- `subcentroid_similarity_heatmap.png`: summarizes cross-cluster cosine similarity between step and nonstep sub-centroids, making diagonal or off-diagonal matches easy to spot.",
            "",
            "## Generated Files",
            "",
            *(f"- `figures/{name}`" for name in figure_files),
            "- `pooled_cluster_members.csv`",
            "- `pooled_cluster_summary.csv`",
            "- `pooled_representative_W.csv`",
            "- `pooled_representative_H_long.csv`",
            "- `checksums.md5`",
            "",
            "## Reproduction",
            "",
            "Run from the repository root:",
            "",
            "```bash",
            "conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \\",
            f"  --config {_display_repo_relative(runtime_notes['config_path'])} \\",
            f"  --baseline-run {_display_repo_relative(artifacts['report_inputs']['baseline_run'])} \\",
            "  --outdir analysis/pooled_shared_specific_synergy/artifacts/<run_name> \\",
            "  --overwrite",
            "```",
            "",
        ]
    )
    report_path = outdir / "report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8-sig")
    return report_path


def export_outputs(outdir: Path, artifacts: dict[str, Any], runtime_notes: dict[str, Any]) -> dict[str, Path]:
    members_path = outdir / "pooled_cluster_members.csv"
    summary_path = outdir / "pooled_cluster_summary.csv"
    rep_w_path = outdir / "pooled_representative_W.csv"
    rep_h_path = outdir / "pooled_representative_H_long.csv"
    metadata_path = outdir / "run_metadata.json"

    _write_csv(artifacts["members"], members_path)
    _write_csv(artifacts["summary"], summary_path)
    _write_csv(artifacts["rep_w"], rep_w_path)
    _write_csv(artifacts["rep_h"], rep_h_path)
    metadata_path.write_text(
        json.dumps(
            {
                "runtime_notes": _json_safe(runtime_notes),
                "cluster_result": _json_safe(artifacts["cluster_result"]),
                "report_inputs": _json_safe(artifacts["report_inputs"]),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8-sig",
    )
    report_path = write_generated_report(outdir, artifacts, runtime_notes)
    checksums_path = _write_md5_manifest(outdir)
    return {
        "members": members_path,
        "summary": summary_path,
        "rep_w": rep_w_path,
        "rep_h": rep_h_path,
        "metadata": metadata_path,
        "report": report_path,
        "checksums": checksums_path,
    }


def main() -> int:
    args = parse_args()
    cfg, runtime_notes = load_config(args.config, args)
    baseline_windows, _ = load_baseline_trial_windows(args.baseline_run)
    print("[OK] loaded baseline trial window metadata")
    inputs = resolve_analysis_inputs(cfg)
    print("[OK] resolved EMG parquet and event workbook from config")
    trial_cases, alignment_summary = rebuild_selected_trial_table(cfg, baseline_windows)
    print("[OK] baseline/event step label validation passed")
    print(f"[OK] selected trials: {alignment_summary['n_trials']}")
    print(f"[OK] selected subjects: {alignment_summary['n_subjects']}")
    if args.dry_run:
        print("[OK] dry-run complete")
        return 0

    _ensure_outdir(args.outdir, overwrite=args.overwrite)
    feature_rows, component_df = build_feature_rows(trial_cases, cfg, inputs["muscle_names"])
    print("[OK] trial-level NMF extraction complete")
    print(f"[OK] pooled components: {component_df.height}")

    cluster_result = search_pooled_k(feature_rows, cfg)
    duplicate_count = int(cluster_result["duplicate_trial_count_by_k"][cluster_result["k_selected"]])
    print(
        f"[OK] k_lb={cluster_result['k_lb']}, "
        f"k_gap_raw={cluster_result['k_gap_raw']}, "
        f"k_selected={cluster_result['k_selected']}"
    )
    print(f"[OK] duplicate_trial_count(k_selected)={duplicate_count}")

    members_df = fit_pooled_clusters(component_df, cluster_result)
    artifacts = summarize_cluster_outputs(
        members_df=members_df,
        cluster_result=cluster_result,
        muscle_names=inputs["muscle_names"],
        target_windows=int(runtime_notes["target_windows"]),
    )
    report_inputs = {
        **alignment_summary,
        "baseline_run": str(args.baseline_run),
        "emg_parquet_path": inputs["emg_parquet_path"],
        "event_xlsm_path": inputs["event_xlsm_path"],
        "target_windows": int(runtime_notes["target_windows"]),
    }
    artifacts["cluster_result"] = cluster_result
    artifacts["report_inputs"] = report_inputs
    generated_paths = export_outputs(args.outdir, artifacts, runtime_notes)
    print("[OK] wrote pooled_cluster_members.csv")
    print("[OK] wrote pooled_cluster_summary.csv")
    print("[OK] wrote pooled_representative_W.csv")
    print("[OK] wrote pooled_representative_H_long.csv")

    figure_paths = generate_figures(args.outdir, artifacts, cfg)
    for figure_path in figure_paths:
        print(f"[OK] wrote {figure_path.relative_to(args.outdir).as_posix()}")
    _write_md5_manifest(args.outdir)
    print(f"[OK] wrote {generated_paths['report'].relative_to(args.outdir).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
