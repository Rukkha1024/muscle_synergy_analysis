# -*- coding: utf-8 -*-
"""Analyze VAF-threshold sensitivity for synergy rank and pooled K.

Runs the main trial-selection, trialwise NMF, concatenated NMF,
and pooled clustering logic for VAF thresholds 0.85-0.95.
Summarizes rank burden, clustering burden, and pooled-structure validity.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from statistics import stdev
import sys
import time
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from src.emg_pipeline import (
    build_trial_records,
    load_emg_table,
    load_event_metadata,
    load_pipeline_config,
    merge_event_metadata,
)
from src.synergy_stats.clustering import SubjectFeatureResult, cluster_feature_group
from src.synergy_stats.concatenated import split_and_average_h_by_trial
from src.synergy_stats.nmf import FeatureBundle, _compute_vaf, _fit_rank, _normalize_components


DEFAULT_THRESHOLDS = tuple(round(value / 100, 2) for value in range(85, 96))
DEFAULT_OUT_DIR = SCRIPT_DIR / "artifacts" / "default_run"
MODE_ORDER = ("trialwise", "concatenated")
STEP_CLASS_ORDER = ("step", "nonstep")
SHARED_CLUSTER_SUBJECT_FLOOR = 2
TINY_CLUSTER_MEMBER_CEILING = 2


@dataclass
class ThresholdModeResult:
    """Container for one mode's VAF-threshold rerun outputs."""

    threshold: float
    mode: str
    feature_rows: list[SubjectFeatureResult]
    cluster_result: dict[str, Any]


@dataclass
class RankCandidate:
    """One fitted NMF rank candidate cached for threshold reuse."""

    rank: int
    W_muscle: np.ndarray
    H_time: np.ndarray
    vaf: float
    extractor_backend: str
    extractor_torch_device: str
    extractor_torch_dtype: str


@dataclass
class PreparedFeatureUnit:
    """Threshold-agnostic cached NMF candidates for one analysis unit."""

    subject: str
    velocity: Any
    trial_num: Any
    candidates: list[RankCandidate]
    elapsed_sec: float
    meta: dict[str, Any]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for dry-run and full reruns."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "global_config.yaml",
        help="Merged pipeline entry config.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory where analysis artifacts will be written.",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=list(DEFAULT_THRESHOLDS),
        help="VAF thresholds to rerun.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate inputs and trial extraction; skip NMF/clustering reruns.",
    )
    parser.add_argument(
        "--cluster-repeats",
        type=int,
        default=None,
        help="Optional override for synergy_clustering.repeats.",
    )
    parser.add_argument(
        "--gap-ref-n",
        type=int,
        default=None,
        help="Optional override for synergy_clustering.gap_ref_n.",
    )
    parser.add_argument(
        "--gap-ref-restarts",
        type=int,
        default=None,
        help="Optional override for synergy_clustering.gap_ref_restarts.",
    )
    parser.add_argument(
        "--uniqueness-candidate-restarts",
        type=int,
        default=None,
        help="Optional override for synergy_clustering.uniqueness_candidate_restarts.",
    )
    return parser.parse_args()


def _print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def _format_threshold(threshold: float) -> str:
    return f"{int(round(threshold * 100)):d}%"


def _trial_id(subject: str, velocity: Any, trial_num: Any) -> str:
    return f"{subject}_v{velocity}_T{trial_num}"


def _meta_flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if value is None:
        return False
    try:
        if value != value:
            return False
    except Exception:
        pass
    return bool(value)


def _sort_key(value: Any) -> tuple[int, Any]:
    if isinstance(value, (int, np.integer)):
        return (0, int(value))
    if isinstance(value, float) and value.is_integer():
        return (0, int(value))
    return (1, str(value))


def _format_id_part(value: Any) -> str:
    return str(value).strip().replace("/", "-").replace("\\", "-").replace(" ", "_")


def _source_trial_detail(trial: Any, source_trial_order: int, step_class: str) -> dict[str, Any]:
    metadata = trial.metadata
    return {
        "source_trial_num": trial.key[2],
        "source_trial_order": int(source_trial_order),
        "source_step_class": step_class,
        "analysis_window_source": metadata.get("analysis_window_source"),
        "analysis_window_start": metadata.get("analysis_window_start"),
        "analysis_window_end": metadata.get("analysis_window_end"),
        "analysis_window_length": metadata.get(
            "analysis_window_duration_device_frames",
            metadata.get("analysis_window_length"),
        ),
        "analysis_window_is_surrogate": metadata.get("analysis_window_is_surrogate"),
    }


def _fit_rank_candidates(x_trial: np.ndarray, cfg: dict[str, Any]) -> tuple[list[RankCandidate], float]:
    trial = np.maximum(np.asarray(x_trial, dtype=np.float32), 0.0)
    nmf_cfg = cfg.get("feature_extractor", {}).get("nmf", {})
    max_components = int(nmf_cfg.get("max_components_to_try", min(trial.shape)))
    start = time.perf_counter()
    candidates: list[RankCandidate] = []
    for rank in range(1, max_components + 1):
        (w_muscle, h_time), backend, runtime = _fit_rank(trial, rank, nmf_cfg)
        w_norm, h_scaled = _normalize_components(w_muscle, h_time)
        candidates.append(
            RankCandidate(
                rank=int(rank),
                W_muscle=w_norm,
                H_time=h_scaled,
                vaf=float(_compute_vaf(trial, w_norm, h_scaled)),
                extractor_backend=str(backend),
                extractor_torch_device=str(runtime.get("torch_device", "")),
                extractor_torch_dtype=str(runtime.get("torch_dtype", "")),
            )
        )
    return candidates, time.perf_counter() - start


def _select_bundle_for_threshold(
    candidates: list[RankCandidate],
    threshold: float,
    elapsed_sec: float,
    meta: dict[str, Any],
) -> FeatureBundle:
    selected = None
    best = max(candidates, key=lambda item: item.vaf)
    for candidate in candidates:
        if candidate.vaf >= threshold:
            selected = candidate
            break
    if selected is None:
        selected = best
    bundle_meta = dict(meta)
    bundle_meta.update(
        {
            "status": "ok",
            "n_components": int(selected.rank),
            "vaf": float(selected.vaf),
            "extractor_type": "nmf",
            "extractor_backend": selected.extractor_backend,
            "extractor_torch_device": selected.extractor_torch_device,
            "extractor_torch_dtype": selected.extractor_torch_dtype,
            "extractor_metric_elapsed_sec": float(elapsed_sec),
        }
    )
    return FeatureBundle(
        W_muscle=selected.W_muscle,
        H_time=selected.H_time,
        meta=bundle_meta,
    )


def _build_feature_rows_from_prepared_units(
    prepared_units: list[PreparedFeatureUnit],
    threshold: float,
) -> list[SubjectFeatureResult]:
    rows: list[SubjectFeatureResult] = []
    for unit in prepared_units:
        rows.append(
            SubjectFeatureResult(
                subject=unit.subject,
                velocity=unit.velocity,
                trial_num=unit.trial_num,
                bundle=_select_bundle_for_threshold(unit.candidates, threshold, unit.elapsed_sec, unit.meta),
            )
        )
    return rows


def _prepare_trialwise_units(
    trial_records: list[Any],
    cfg: dict[str, Any],
    muscle_names: list[str],
) -> list[PreparedFeatureUnit]:
    prepared_units: list[PreparedFeatureUnit] = []
    for trial in trial_records:
        x_trial = trial.frame[muscle_names].to_numpy(dtype="float32")
        candidates, elapsed_sec = _fit_rank_candidates(x_trial, cfg)
        prepared_units.append(
            PreparedFeatureUnit(
                subject=str(trial.key[0]),
                velocity=trial.key[1],
                trial_num=trial.key[2],
                candidates=candidates,
                elapsed_sec=elapsed_sec,
                meta={
                    "subject": trial.key[0],
                    "velocity": trial.key[1],
                    "trial_num": trial.key[2],
                    "aggregation_mode": "trialwise",
                    "analysis_unit_id": _trial_id(trial.key[0], trial.key[1], trial.key[2]),
                    "source_trial_nums_csv": str(trial.key[2]),
                    "analysis_source_trial_count": 1,
                    **trial.metadata,
                },
            )
        )
    return prepared_units


def _prepare_concatenated_units(
    trial_records: list[Any],
    muscle_names: list[str],
    cfg: dict[str, Any],
) -> list[PreparedFeatureUnit]:
    grouped: dict[tuple[str, Any, str], list[Any]] = defaultdict(list)
    for trial in trial_records:
        if not _meta_flag(trial.metadata.get("analysis_selected_group", True)):
            continue
        step_class = str(trial.metadata.get("analysis_step_class", "")).strip().lower()
        if step_class not in STEP_CLASS_ORDER:
            continue
        grouped[(str(trial.key[0]), trial.key[1], step_class)].append(trial)

    prepared_units: list[PreparedFeatureUnit] = []
    for (subject, velocity, step_class), trials in sorted(
        grouped.items(),
        key=lambda item: (_sort_key(item[0][0]), _sort_key(item[0][1]), item[0][2]),
    ):
        ordered_trials = sorted(trials, key=lambda trial: _sort_key(trial.key[2]))
        source_trial_details = [
            _source_trial_detail(trial, source_trial_order=index + 1, step_class=step_class)
            for index, trial in enumerate(ordered_trials)
        ]
        segment_lengths = [len(trial.frame.index) for trial in ordered_trials]
        concatenated_matrix = np.concatenate(
            [trial.frame[muscle_names].to_numpy(dtype=np.float32, copy=True) for trial in ordered_trials],
            axis=0,
        )
        raw_candidates, elapsed_sec = _fit_rank_candidates(concatenated_matrix, cfg)
        candidates = [
            RankCandidate(
                rank=candidate.rank,
                W_muscle=candidate.W_muscle,
                H_time=split_and_average_h_by_trial(candidate.H_time, segment_lengths),
                vaf=candidate.vaf,
                extractor_backend=candidate.extractor_backend,
                extractor_torch_device=candidate.extractor_torch_device,
                extractor_torch_dtype=candidate.extractor_torch_dtype,
            )
            for candidate in raw_candidates
        ]
        synthetic_trial_num = f"concat_{step_class}"
        analysis_unit_id = f"{_format_id_part(subject)}_v{_format_id_part(velocity)}_{step_class}_concat"
        source_trial_nums_csv = "|".join(str(trial.key[2]) for trial in ordered_trials)
        prepared_units.append(
            PreparedFeatureUnit(
                subject=subject,
                velocity=velocity,
                trial_num=synthetic_trial_num,
                candidates=candidates,
                elapsed_sec=elapsed_sec,
                meta={
                    "subject": subject,
                    "velocity": velocity,
                    "trial_num": synthetic_trial_num,
                    "aggregation_mode": "concatenated",
                    "analysis_unit_id": analysis_unit_id,
                    "source_trial_nums_csv": source_trial_nums_csv,
                    "analysis_source_trial_count": len(ordered_trials),
                    "source_trial_details": source_trial_details,
                    "analysis_h_alignment_method": (
                        "equal_length_average"
                        if len(set(segment_lengths)) == 1
                        else "interpolated_to_max_length"
                    ),
                    "analysis_selected_group": True,
                    "analysis_is_step": step_class == "step",
                    "analysis_is_nonstep": step_class == "nonstep",
                    "analysis_step_class": step_class,
                },
            )
        )
    return prepared_units


def _build_trialwise_feature_rows(
    trial_records: list[Any],
    cfg: dict[str, Any],
    muscle_names: list[str],
) -> list[SubjectFeatureResult]:
    threshold = float(cfg.get("feature_extractor", {}).get("nmf", {}).get("vaf_threshold", 0.90))
    prepared_units = _prepare_trialwise_units(trial_records, cfg, muscle_names)
    return _build_feature_rows_from_prepared_units(prepared_units, threshold)


def _collect_pooled_feature_rows(feature_rows: list[SubjectFeatureResult]) -> list[SubjectFeatureResult]:
    pooled_rows: list[SubjectFeatureResult] = []
    invalid_trials: list[str] = []
    for item in feature_rows:
        if not _meta_flag(item.bundle.meta.get("analysis_selected_group")):
            continue
        is_step = _meta_flag(item.bundle.meta.get("analysis_is_step"))
        is_nonstep = _meta_flag(item.bundle.meta.get("analysis_is_nonstep"))
        if is_step == is_nonstep:
            invalid_trials.append(f"{item.subject}_v{item.velocity}_T{item.trial_num}")
            continue
        pooled_rows.append(item)
    if invalid_trials:
        raise ValueError(
            "Selected trials must belong to exactly one strategy label: " + ", ".join(invalid_trials)
        )
    return pooled_rows


def _load_trial_records(cfg: dict[str, Any]) -> tuple[pd.DataFrame, list[Any]]:
    emg_df = load_emg_table(cfg["input"]["emg_parquet_path"])
    event_df = load_event_metadata(cfg["input"]["event_xlsm_path"], cfg)
    merged = merge_event_metadata(emg_df, event_df)
    trial_records = build_trial_records(merged, cfg)
    return merged, trial_records


def _prepare_threshold_cfg(base_cfg: dict[str, Any], threshold: float, args: argparse.Namespace | None = None) -> dict[str, Any]:
    cfg = deepcopy(base_cfg)
    cfg.setdefault("synergy_analysis", {})["mode"] = "both"
    cfg.setdefault("feature_extractor", {}).setdefault("nmf", {})["vaf_threshold"] = float(threshold)
    cluster_cfg = cfg.setdefault("synergy_clustering", {})
    if args is not None:
        if args.cluster_repeats is not None:
            cluster_cfg["repeats"] = int(args.cluster_repeats)
        if args.gap_ref_n is not None:
            cluster_cfg["gap_ref_n"] = int(args.gap_ref_n)
        if args.gap_ref_restarts is not None:
            cluster_cfg["gap_ref_restarts"] = int(args.gap_ref_restarts)
        if args.uniqueness_candidate_restarts is not None:
            cluster_cfg["uniqueness_candidate_restarts"] = int(args.uniqueness_candidate_restarts)
    return cfg


def _effective_clustering_config(
    base_cfg: dict[str, Any],
    args: argparse.Namespace | None = None,
) -> dict[str, int | None]:
    cluster_cfg = deepcopy(base_cfg.get("synergy_clustering", {}))
    if args is not None:
        if args.cluster_repeats is not None:
            cluster_cfg["repeats"] = int(args.cluster_repeats)
        if args.gap_ref_n is not None:
            cluster_cfg["gap_ref_n"] = int(args.gap_ref_n)
        if args.gap_ref_restarts is not None:
            cluster_cfg["gap_ref_restarts"] = int(args.gap_ref_restarts)
        if args.uniqueness_candidate_restarts is not None:
            cluster_cfg["uniqueness_candidate_restarts"] = int(args.uniqueness_candidate_restarts)
    return {
        "repeats": int(cluster_cfg["repeats"]) if cluster_cfg.get("repeats") is not None else None,
        "gap_ref_n": int(cluster_cfg["gap_ref_n"]) if cluster_cfg.get("gap_ref_n") is not None else None,
        "gap_ref_restarts": (
            int(cluster_cfg["gap_ref_restarts"])
            if cluster_cfg.get("gap_ref_restarts") is not None
            else None
        ),
        "uniqueness_candidate_restarts": (
            int(cluster_cfg["uniqueness_candidate_restarts"])
            if cluster_cfg.get("uniqueness_candidate_restarts") is not None
            else None
        ),
    }


def _subject_strategy_summary_rows(
    feature_rows: list[SubjectFeatureResult],
    mode: str,
    threshold: float,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in feature_rows:
        step_class = str(item.bundle.meta.get("analysis_step_class", "")).strip().lower()
        if step_class not in STEP_CLASS_ORDER:
            continue
        grouped[(str(item.subject), step_class)].append(
            {
                "velocity": item.velocity,
                "trial_num": item.trial_num,
                "n_components": int(item.bundle.meta.get("n_components", item.bundle.W_muscle.shape[1])),
                "vaf": float(item.bundle.meta.get("vaf", 0.0)),
            }
        )

    rows: list[dict[str, Any]] = []
    for (subject, step_class), values in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        component_values = [entry["n_components"] for entry in values]
        vaf_values = [entry["vaf"] for entry in values]
        velocity_values = sorted({str(entry["velocity"]) for entry in values})
        rows.append(
            {
                "mode": mode,
                "threshold": threshold,
                "threshold_label": _format_threshold(threshold),
                "subject": subject,
                "step_class": step_class,
                "analysis_unit_count": len(values),
                "velocity_count": len(velocity_values),
                "velocities": velocity_values,
                "n_components_mean": round(_mean(component_values), 4),
                "n_components_sd": round(_sd(component_values), 4),
                "n_components_min": min(component_values),
                "n_components_max": max(component_values),
                "n_components_values": component_values,
                "vaf_mean": round(_mean(vaf_values), 6),
                "vaf_min": round(min(vaf_values), 6),
                "vaf_max": round(max(vaf_values), 6),
            }
        )
    return rows


def _overall_mode_summary_row(result: ThresholdModeResult, max_components_to_try: int) -> dict[str, Any]:
    step_unit_count = sum(
        1 for item in result.feature_rows if str(item.bundle.meta.get("analysis_step_class", "")).strip().lower() == "step"
    )
    nonstep_unit_count = sum(
        1
        for item in result.feature_rows
        if str(item.bundle.meta.get("analysis_step_class", "")).strip().lower() == "nonstep"
    )
    component_counts = [
        int(item.bundle.meta.get("n_components", item.bundle.W_muscle.shape[1])) for item in result.feature_rows
    ]
    vaf_values = [float(item.bundle.meta.get("vaf", 0.0)) for item in result.feature_rows]
    cluster_result = result.cluster_result
    k_gap_raw = int(cluster_result.get("k_gap_raw", 0) or 0)
    k_selected = int(cluster_result.get("k_selected", 0) or 0)
    duplicate_trial_count_by_k = {
        int(key): int(value) for key, value in (cluster_result.get("duplicate_trial_count_by_k") or {}).items()
    }
    ceiling_hit_count = sum(1 for value in component_counts if value >= max_components_to_try)
    return {
        "mode": result.mode,
        "threshold": result.threshold,
        "threshold_label": _format_threshold(result.threshold),
        "analysis_unit_count": len(result.feature_rows),
        "step_unit_count": step_unit_count,
        "nonstep_unit_count": nonstep_unit_count,
        "component_count_total": int(sum(component_counts)),
        "component_mean": round(sum(component_counts) / len(component_counts), 4),
        "component_min": min(component_counts),
        "component_max": max(component_counts),
        "max_components_to_try": int(max_components_to_try),
        "component_ceiling_hit_count": int(ceiling_hit_count),
        "component_ceiling_hit_rate": round(ceiling_hit_count / len(component_counts), 4),
        "vaf_mean": round(sum(vaf_values) / len(vaf_values), 6),
        "vaf_min": round(min(vaf_values), 6),
        "vaf_max": round(max(vaf_values), 6),
        "unexplained_variance_mean": round(1.0 - (sum(vaf_values) / len(vaf_values)), 6),
        "k_lb": cluster_result.get("k_lb"),
        "k_gap_raw": k_gap_raw,
        "k_selected": k_selected,
        "k_min_unique": cluster_result.get("k_min_unique"),
        "selection_status": cluster_result.get("selection_status"),
        "algorithm_used": cluster_result.get("algorithm_used"),
        "n_components_clustered": cluster_result.get("n_components"),
        "k_selected_minus_gap_raw": int(k_selected - k_gap_raw),
        "k_selected_over_gap_raw": round((k_selected / k_gap_raw), 4) if k_gap_raw > 0 else None,
        "duplicate_trial_count_at_gap_raw": duplicate_trial_count_by_k.get(k_gap_raw, 0),
        "duplicate_trial_count_at_selected_k": duplicate_trial_count_by_k.get(k_selected, 0),
    }


def _component_join_key(subject: Any, velocity: Any, trial_num: Any, component_index: int) -> tuple[str, str, str, int]:
    return (str(subject), str(velocity), str(trial_num), int(component_index))


def _component_count(item: SubjectFeatureResult) -> int:
    return int(item.bundle.meta.get("n_components", item.bundle.W_muscle.shape[1]))


def _safe_divide(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator / denominator)


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    if not np.isfinite(value):
        return None
    return round(float(value), digits)


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(values))
    if norm <= 0.0:
        return values
    return values / norm


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float | None:
    left_vec = np.asarray(left, dtype=np.float64)
    right_vec = np.asarray(right, dtype=np.float64)
    denom = float(np.linalg.norm(left_vec) * np.linalg.norm(right_vec))
    if denom <= 0.0:
        return None
    return float(np.dot(left_vec, right_vec) / denom)


def _component_rows_from_feature_rows(
    feature_rows: list[SubjectFeatureResult],
    mode: str,
    threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    threshold_label = _format_threshold(threshold)
    for item in feature_rows:
        step_class = str(item.bundle.meta.get("analysis_step_class", "")).strip().lower()
        n_components = _component_count(item)
        for component_index in range(item.bundle.W_muscle.shape[1]):
            rows.append(
                {
                    "mode": mode,
                    "threshold": threshold,
                    "threshold_label": threshold_label,
                    "subject": str(item.subject),
                    "velocity": item.velocity,
                    "trial_num": item.trial_num,
                    "trial_id": _trial_id(str(item.subject), item.velocity, item.trial_num),
                    "step_TF": step_class,
                    "component_idx": int(component_index),
                    "n_components_selected": int(n_components),
                    "vaf": float(item.bundle.meta.get("vaf", 0.0)),
                    "w_vector": np.asarray(item.bundle.W_muscle[:, component_index], dtype=np.float64),
                }
            )
    return rows


def _members_rows_with_clusters(
    component_rows: list[dict[str, Any]],
    cluster_result: dict[str, Any],
) -> list[dict[str, Any]]:
    labels = np.asarray(cluster_result["labels"], dtype=np.int32)
    sample_map = cluster_result["sample_map"]
    label_map = {
        _component_join_key(sample["subject"], sample["velocity"], sample["trial_num"], int(sample["component_index"])): int(label)
        for sample, label in zip(sample_map, labels.tolist())
    }
    members_rows: list[dict[str, Any]] = []
    for row in component_rows:
        key = _component_join_key(row["subject"], row["velocity"], row["trial_num"], int(row["component_idx"]))
        cluster_id = label_map.get(key)
        if cluster_id is None:
            continue
        member_row = dict(row)
        member_row["cluster_id"] = int(cluster_id)
        members_rows.append(member_row)
    return members_rows


def _subject_norm_stats(
    cluster_members: list[dict[str, Any]],
    strategy: str,
    subject_total_counts: dict[str, int],
) -> tuple[float | None, float | None]:
    strategy_rows = [row for row in cluster_members if row["step_TF"] == strategy]
    if not strategy_rows:
        return None, None
    cluster_subject_counts: dict[str, int] = defaultdict(int)
    for row in strategy_rows:
        cluster_subject_counts[str(row["subject"])] += 1
    ratios = [
        cluster_subject_counts.get(subject, 0) / total
        for subject, total in subject_total_counts.items()
        if total > 0
    ]
    if not ratios:
        return None, None
    return float(np.mean(ratios)), float(np.std(ratios, ddof=0))


def _cluster_validity_rows(
    feature_rows: list[SubjectFeatureResult],
    result: ThresholdModeResult,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    component_rows = _component_rows_from_feature_rows(feature_rows, result.mode, result.threshold)
    members_rows = _members_rows_with_clusters(component_rows, result.cluster_result)
    threshold_label = _format_threshold(result.threshold)
    if not members_rows:
        empty_summary = {
            "mode": result.mode,
            "threshold": result.threshold,
            "threshold_label": threshold_label,
            "cluster_count_total": 0,
            "shared_cluster_count": 0,
            "exclusive_cluster_count": 0,
            "shared_cluster_rate": 0.0,
            "shared_member_rate": 0.0,
            "substantial_shared_cluster_count": 0,
            "substantial_shared_cluster_rate": 0.0,
            "singleton_cluster_count": 0,
            "singleton_cluster_rate": 0.0,
            "tiny_cluster_count": 0,
            "tiny_cluster_rate": 0.0,
            "pooled_member_cosine_mean": None,
            "pooled_member_cosine_sd": None,
            "shared_subcentroid_cosine_mean": None,
            "shared_subcentroid_cosine_weighted_mean": None,
            "cluster_member_count_mean": None,
            "cluster_member_count_sd": None,
        }
        return empty_summary, []

    cluster_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in members_rows:
        cluster_groups[int(row["cluster_id"])].append(row)

    total_member_count = len(members_rows)
    cluster_member_counts = [len(rows) for rows in cluster_groups.values()]
    pooled_member_cosines: list[float] = []
    shared_cluster_cosines: list[float] = []
    shared_cluster_cosines_weighted: list[float] = []
    shared_cluster_count = 0
    substantial_shared_cluster_count = 0
    shared_member_count = 0
    singleton_cluster_count = 0
    tiny_cluster_count = 0
    cluster_rows: list[dict[str, Any]] = []
    subject_total_counts_by_strategy: dict[str, dict[str, int]] = {
        "step": defaultdict(int),
        "nonstep": defaultdict(int),
    }
    for row in members_rows:
        strategy = str(row["step_TF"])
        if strategy in subject_total_counts_by_strategy:
            subject_total_counts_by_strategy[strategy][str(row["subject"])] += 1

    for cluster_id in sorted(cluster_groups):
        cluster_members = cluster_groups[cluster_id]
        member_vectors = [row["w_vector"] for row in cluster_members]
        pooled_centroid = _normalize_vector(np.mean(np.stack(member_vectors, axis=0), axis=0))
        member_cosines = [value for value in (_cosine_similarity(vector, pooled_centroid) for vector in member_vectors) if value is not None]
        pooled_member_cosines.extend(member_cosines)

        step_members = [row for row in cluster_members if row["step_TF"] == "step"]
        nonstep_members = [row for row in cluster_members if row["step_TF"] == "nonstep"]
        step_subjects = sorted({str(row["subject"]) for row in step_members})
        nonstep_subjects = sorted({str(row["subject"]) for row in nonstep_members})
        step_stats = _subject_norm_stats(cluster_members, "step", subject_total_counts_by_strategy["step"])
        nonstep_stats = _subject_norm_stats(
            cluster_members,
            "nonstep",
            subject_total_counts_by_strategy["nonstep"],
        )

        step_vector = (
            _normalize_vector(np.mean(np.stack([row["w_vector"] for row in step_members], axis=0), axis=0))
            if step_members
            else None
        )
        nonstep_vector = (
            _normalize_vector(np.mean(np.stack([row["w_vector"] for row in nonstep_members], axis=0), axis=0))
            if nonstep_members
            else None
        )
        shared_cosine = (
            _cosine_similarity(step_vector, nonstep_vector)
            if step_vector is not None and nonstep_vector is not None
            else None
        )

        member_count = len(cluster_members)
        if len(step_members) > 0 and len(nonstep_members) > 0:
            shared_cluster_count += 1
            shared_member_count += member_count
            if shared_cosine is not None:
                shared_cluster_cosines.append(shared_cosine)
                shared_cluster_cosines_weighted.extend([shared_cosine] * member_count)
            if len(step_subjects) >= SHARED_CLUSTER_SUBJECT_FLOOR and len(nonstep_subjects) >= SHARED_CLUSTER_SUBJECT_FLOOR:
                substantial_shared_cluster_count += 1
        if member_count == 1:
            singleton_cluster_count += 1
        if member_count <= TINY_CLUSTER_MEMBER_CEILING:
            tiny_cluster_count += 1

        cluster_rows.append(
            {
                "mode": result.mode,
                "threshold": result.threshold,
                "threshold_label": threshold_label,
                "cluster_id": int(cluster_id),
                "n_members_total": int(member_count),
                "n_members_step": int(len(step_members)),
                "n_members_nonstep": int(len(nonstep_members)),
                "subject_coverage_step": int(len(step_subjects)),
                "subject_coverage_nonstep": int(len(nonstep_subjects)),
                "subject_norm_occupancy_step_mean": _round_or_none(step_stats[0], 4),
                "subject_norm_occupancy_step_sd": _round_or_none(step_stats[1], 4),
                "subject_norm_occupancy_nonstep_mean": _round_or_none(nonstep_stats[0], 4),
                "subject_norm_occupancy_nonstep_sd": _round_or_none(nonstep_stats[1], 4),
                "pooled_member_cosine_mean": _round_or_none(float(np.mean(member_cosines)) if member_cosines else None, 4),
                "pooled_member_cosine_sd": _round_or_none(float(np.std(member_cosines, ddof=0)) if member_cosines else None, 4),
                "step_nonstep_subcentroid_cosine": _round_or_none(shared_cosine, 4),
                "is_shared_cluster": bool(step_members and nonstep_members),
                "is_substantial_shared_cluster": bool(
                    step_members
                    and nonstep_members
                    and len(step_subjects) >= SHARED_CLUSTER_SUBJECT_FLOOR
                    and len(nonstep_subjects) >= SHARED_CLUSTER_SUBJECT_FLOOR
                ),
                "is_singleton_cluster": bool(member_count == 1),
                "is_tiny_cluster": bool(member_count <= TINY_CLUSTER_MEMBER_CEILING),
            }
        )

    cluster_count_total = len(cluster_groups)
    return (
        {
            "mode": result.mode,
            "threshold": result.threshold,
            "threshold_label": threshold_label,
            "cluster_count_total": int(cluster_count_total),
            "shared_cluster_count": int(shared_cluster_count),
            "exclusive_cluster_count": int(cluster_count_total - shared_cluster_count),
            "shared_cluster_rate": round(shared_cluster_count / cluster_count_total, 4),
            "shared_member_rate": round(shared_member_count / total_member_count, 4),
            "substantial_shared_cluster_count": int(substantial_shared_cluster_count),
            "substantial_shared_cluster_rate": round(substantial_shared_cluster_count / cluster_count_total, 4),
            "singleton_cluster_count": int(singleton_cluster_count),
            "singleton_cluster_rate": round(singleton_cluster_count / cluster_count_total, 4),
            "tiny_cluster_count": int(tiny_cluster_count),
            "tiny_cluster_rate": round(tiny_cluster_count / cluster_count_total, 4),
            "pooled_member_cosine_mean": _round_or_none(float(np.mean(pooled_member_cosines)) if pooled_member_cosines else None, 4),
            "pooled_member_cosine_sd": _round_or_none(float(np.std(pooled_member_cosines, ddof=0)) if pooled_member_cosines else None, 4),
            "shared_subcentroid_cosine_mean": _round_or_none(float(np.mean(shared_cluster_cosines)) if shared_cluster_cosines else None, 4),
            "shared_subcentroid_cosine_weighted_mean": _round_or_none(
                float(np.mean(shared_cluster_cosines_weighted)) if shared_cluster_cosines_weighted else None,
                4,
            ),
            "cluster_member_count_mean": _round_or_none(float(np.mean(cluster_member_counts)) if cluster_member_counts else None, 4),
            "cluster_member_count_sd": _round_or_none(float(np.std(cluster_member_counts, ddof=0)) if cluster_member_counts else None, 4),
        },
        cluster_rows,
    )


def _cluster_k_curve_rows(result: ThresholdModeResult) -> list[dict[str, Any]]:
    cluster_result = result.cluster_result
    gap_by_k = {int(key): float(value) for key, value in (cluster_result.get("gap_by_k") or {}).items()}
    duplicate_by_k = {
        int(key): int(value) for key, value in (cluster_result.get("duplicate_trial_count_by_k") or {}).items()
    }
    k_gap_raw = int(cluster_result.get("k_gap_raw", 0) or 0)
    k_selected = int(cluster_result.get("k_selected", 0) or 0)
    k_min_unique_raw = cluster_result.get("k_min_unique")
    k_min_unique = int(k_min_unique_raw) if k_min_unique_raw not in ("", None) else None
    rows: list[dict[str, Any]] = []
    for k_value in sorted(gap_by_k):
        rows.append(
            {
                "mode": result.mode,
                "threshold": result.threshold,
                "threshold_label": _format_threshold(result.threshold),
                "k": int(k_value),
                "gap": round(float(gap_by_k[k_value]), 6),
                "duplicate_trial_count": int(duplicate_by_k.get(k_value, 0)),
                "is_gap_raw_k": bool(k_value == k_gap_raw),
                "is_selected_k": bool(k_value == k_selected),
                "is_min_unique_k": bool(k_min_unique is not None and k_value == k_min_unique),
            }
        )
    return rows


def _subject_strategy_matrix(
    subject_rows: list[dict[str, Any]],
    *,
    mode: str,
    step_class: str,
    threshold_labels: list[str],
) -> list[dict[str, Any]]:
    filtered = [row for row in subject_rows if row["mode"] == mode and row["step_class"] == step_class]
    grouped: dict[str, dict[str, Any]] = {}
    for row in filtered:
        subject_row = grouped.setdefault(
            row["subject"],
            {
                "subject": row["subject"],
                "analysis_unit_count": row["analysis_unit_count"],
                "velocity_count": row["velocity_count"],
            },
        )
        subject_row[_format_threshold(row["threshold"])] = (
            f"{row['n_components_mean']:.2f} [{row['n_components_min']}-{row['n_components_max']}]"
        )
    ordered_rows = []
    for subject in sorted(grouped):
        row = grouped[subject]
        for threshold_label in threshold_labels:
            row.setdefault(threshold_label, "n/a")
        ordered_rows.append(row)
    return ordered_rows


def _render_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows_"
    frame = pd.DataFrame(rows)
    frame = frame.loc[:, columns].fillna("n/a")
    rendered_rows = [columns, ["---"] * len(columns)]
    for record in frame.to_dict(orient="records"):
        rendered_rows.append([str(record[column]) for column in columns])
    return "\n".join("| " + " | ".join(row) + " |" for row in rendered_rows)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _sd(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(stdev(values))


def _format_mean_sd(mean_value: float, sd_value: float) -> str:
    return f"{mean_value:.2f} ± {sd_value:.2f}"


def _format_range(min_value: float, max_value: float) -> str:
    return f"{min_value:.2f}-{max_value:.2f}"


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _checksum_lines(base_dir: Path, paths: list[Path]) -> list[str]:
    lines = []
    for path in paths:
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        try:
            display_path = path.relative_to(base_dir)
        except ValueError:
            display_path = path.name
        lines.append(f"{digest}  {display_path}")
    return lines


def _run_threshold_analysis(
    prepared_trialwise_units: list[PreparedFeatureUnit],
    prepared_concatenated_units: list[PreparedFeatureUnit],
    cfg: dict[str, Any],
    threshold: float,
    args: argparse.Namespace,
) -> dict[str, ThresholdModeResult]:
    threshold_cfg = _prepare_threshold_cfg(cfg, threshold, args=args)
    trialwise_rows = _build_feature_rows_from_prepared_units(prepared_trialwise_units, threshold)
    concatenated_rows = _build_feature_rows_from_prepared_units(prepared_concatenated_units, threshold)
    mode_feature_rows = {
        "trialwise": trialwise_rows,
        "concatenated": concatenated_rows,
    }

    results: dict[str, ThresholdModeResult] = {}
    for mode in MODE_ORDER:
        pooled_rows = _collect_pooled_feature_rows(mode_feature_rows[mode])
        cluster_result = cluster_feature_group(
            pooled_rows,
            threshold_cfg["synergy_clustering"],
            group_id="pooled_step_nonstep",
        )
        if cluster_result.get("status") != "success":
            raise RuntimeError(
                f"Clustering failed for mode={mode}, threshold={threshold}: {cluster_result.get('reason', 'unknown')}"
            )
        results[mode] = ThresholdModeResult(
            threshold=threshold,
            mode=mode,
            feature_rows=mode_feature_rows[mode],
            cluster_result=cluster_result,
        )
    return results


def _build_report_payload(
    args: argparse.Namespace,
    cfg: dict[str, Any],
    merged_df: pd.DataFrame,
    trial_records: list[Any],
    threshold_results: dict[str, list[ThresholdModeResult]],
) -> dict[str, Any]:
    max_components_to_try = int(cfg.get("feature_extractor", {}).get("nmf", {}).get("max_components_to_try", 0) or 0)
    base_clustering_cfg = _effective_clustering_config(cfg, None)
    effective_clustering_cfg = _effective_clustering_config(cfg, args)
    selected_trial_frame = merged_df.drop_duplicates(subset=["subject", "velocity", "trial_num"]).copy()
    if "analysis_selected_group" in selected_trial_frame.columns:
        selected_trial_frame = selected_trial_frame.loc[selected_trial_frame["analysis_selected_group"].fillna(False)].copy()

    subject_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    cluster_curve_rows: list[dict[str, Any]] = []
    cluster_validity_summary_rows: list[dict[str, Any]] = []
    cluster_validity_by_cluster_rows: list[dict[str, Any]] = []
    for mode in MODE_ORDER:
        for result in threshold_results[mode]:
            overall_row = _overall_mode_summary_row(result, max_components_to_try=max_components_to_try)
            overall_rows.append(overall_row)
            cluster_rows.append(
                {
                    "mode": mode,
                    "threshold": result.threshold,
                    "threshold_label": overall_row["threshold_label"],
                    "analysis_unit_count": overall_row["analysis_unit_count"],
                    "component_count_total": overall_row["component_count_total"],
                    "k_lb": overall_row["k_lb"],
                    "k_gap_raw": overall_row["k_gap_raw"],
                    "k_selected": overall_row["k_selected"],
                    "k_min_unique": overall_row["k_min_unique"],
                    "k_selected_minus_gap_raw": overall_row["k_selected_minus_gap_raw"],
                    "duplicate_trial_count_at_gap_raw": overall_row["duplicate_trial_count_at_gap_raw"],
                    "selection_status": overall_row["selection_status"],
                }
            )
            cluster_curve_rows.extend(_cluster_k_curve_rows(result))
            validity_summary_row, validity_cluster_rows = _cluster_validity_rows(result.feature_rows, result)
            cluster_validity_summary_rows.append(validity_summary_row)
            cluster_validity_by_cluster_rows.extend(validity_cluster_rows)
            subject_rows.extend(_subject_strategy_summary_rows(result.feature_rows, mode, result.threshold))

    threshold_component_rows: list[dict[str, Any]] = []
    for mode in MODE_ORDER:
        result_map = {result.threshold: result for result in threshold_results[mode]}
        for threshold in args.thresholds:
            threshold_value = float(threshold)
            threshold_label = _format_threshold(threshold_value)
            mode_rows = [row for row in subject_rows if row["mode"] == mode and row["threshold_label"] == threshold_label]
            result = result_map[threshold_value]
            row: dict[str, Any] = {
                "mode": mode,
                "threshold": threshold_value,
                "threshold_label": threshold_label,
                "subject_count_total": len({str(item["subject"]) for item in mode_rows}),
            }
            for step_class in STEP_CLASS_ORDER:
                step_rows = [item for item in mode_rows if item["step_class"] == step_class]
                component_values = [
                    _component_count(item)
                    for item in result.feature_rows
                    if str(item.bundle.meta.get("analysis_step_class", "")).strip().lower() == step_class
                ]
                component_means = [float(item["n_components_mean"]) for item in step_rows]
                row[f"{step_class}_subject_count"] = len({str(item["subject"]) for item in step_rows})
                row[f"{step_class}_component_mean"] = round(_mean(component_means), 4)
                row[f"{step_class}_component_sd"] = round(_sd(component_means), 4)
                row[f"{step_class}_component_min"] = round(min(component_means), 4)
                row[f"{step_class}_component_max"] = round(max(component_means), 4)
                row[f"{step_class}_component_mean_sd"] = _format_mean_sd(
                    row[f"{step_class}_component_mean"],
                    row[f"{step_class}_component_sd"],
                )
                row[f"{step_class}_component_range"] = _format_range(
                    row[f"{step_class}_component_min"],
                    row[f"{step_class}_component_max"],
                )
                row[f"{step_class}_ceiling_hit_count"] = int(sum(1 for value in component_values if value >= max_components_to_try))
                row[f"{step_class}_ceiling_hit_rate"] = round(
                    row[f"{step_class}_ceiling_hit_count"] / len(component_values),
                    4,
                )
            threshold_component_rows.append(row)

    transition_rows: list[dict[str, Any]] = []
    overall_map = {(row["mode"], row["threshold_label"]): row for row in overall_rows}
    component_map = {(row["mode"], row["threshold_label"]): row for row in threshold_component_rows}
    validity_map = {(row["mode"], row["threshold_label"]): row for row in cluster_validity_summary_rows}
    threshold_values = [float(value) for value in args.thresholds]
    for mode in MODE_ORDER:
        for left_threshold, right_threshold in zip(threshold_values[:-1], threshold_values[1:]):
            left_label = _format_threshold(left_threshold)
            right_label = _format_threshold(right_threshold)
            left_overall = overall_map[(mode, left_label)]
            right_overall = overall_map[(mode, right_label)]
            left_component = component_map[(mode, left_label)]
            right_component = component_map[(mode, right_label)]
            left_validity = validity_map[(mode, left_label)]
            right_validity = validity_map[(mode, right_label)]
            component_delta = right_overall["component_mean"] - left_overall["component_mean"]
            vaf_delta = right_overall["vaf_mean"] - left_overall["vaf_mean"]
            transition_rows.append(
                {
                    "mode": mode,
                    "from_threshold": left_threshold,
                    "to_threshold": right_threshold,
                    "from_threshold_label": left_label,
                    "to_threshold_label": right_label,
                    "threshold_transition": f"{left_label}->{right_label}",
                    "component_mean_delta": round(component_delta, 4),
                    "vaf_mean_delta": round(vaf_delta, 6),
                    "vaf_gain_per_component": _round_or_none(_safe_divide(vaf_delta, component_delta), 6),
                    "component_ceiling_hit_rate_delta": round(
                        right_overall["component_ceiling_hit_rate"] - left_overall["component_ceiling_hit_rate"],
                        4,
                    ),
                    "step_ceiling_hit_rate_delta": round(
                        right_component["step_ceiling_hit_rate"] - left_component["step_ceiling_hit_rate"],
                        4,
                    ),
                    "nonstep_ceiling_hit_rate_delta": round(
                        right_component["nonstep_ceiling_hit_rate"] - left_component["nonstep_ceiling_hit_rate"],
                        4,
                    ),
                    "k_selected_delta": int(right_overall["k_selected"] - left_overall["k_selected"]),
                    "k_selected_minus_gap_raw_delta": int(
                        right_overall["k_selected_minus_gap_raw"] - left_overall["k_selected_minus_gap_raw"]
                    ),
                    "duplicate_trial_count_at_gap_raw_delta": int(
                        right_overall["duplicate_trial_count_at_gap_raw"] - left_overall["duplicate_trial_count_at_gap_raw"]
                    ),
                    "pooled_member_cosine_mean_delta": _round_or_none(
                        (
                            right_validity["pooled_member_cosine_mean"] - left_validity["pooled_member_cosine_mean"]
                            if right_validity["pooled_member_cosine_mean"] is not None
                            and left_validity["pooled_member_cosine_mean"] is not None
                            else None
                        ),
                        4,
                    ),
                    "shared_member_rate_delta": _round_or_none(
                        right_validity["shared_member_rate"] - left_validity["shared_member_rate"],
                        4,
                    ),
                    "tiny_cluster_rate_delta": _round_or_none(
                        right_validity["tiny_cluster_rate"] - left_validity["tiny_cluster_rate"],
                        4,
                    ),
                    "singleton_cluster_rate_delta": _round_or_none(
                        right_validity["singleton_cluster_rate"] - left_validity["singleton_cluster_rate"],
                        4,
                    ),
                }
            )

    return {
        "config_path": str(args.config),
        "out_dir": str(args.out_dir),
        "thresholds": [float(value) for value in args.thresholds],
        "run_metadata": {
            "cluster_repeats_override": args.cluster_repeats,
            "gap_ref_n_override": args.gap_ref_n,
            "gap_ref_restarts_override": args.gap_ref_restarts,
            "uniqueness_candidate_restarts_override": args.uniqueness_candidate_restarts,
            "clustering_config_base": base_clustering_cfg,
            "clustering_config_effective": effective_clustering_cfg,
        },
        "input": {
            "emg_parquet_path": cfg["input"]["emg_parquet_path"],
            "event_xlsm_path": cfg["input"]["event_xlsm_path"],
            "max_components_to_try": int(max_components_to_try),
        },
        "data_summary": {
            "merged_rows": int(len(merged_df)),
            "selected_trials": int(len(selected_trial_frame)),
            "trial_records": int(len(trial_records)),
            "subjects": sorted(selected_trial_frame["subject"].astype(str).unique().tolist()),
            "selected_step_trials": int(selected_trial_frame["analysis_is_step"].fillna(False).sum()),
            "selected_nonstep_trials": int(selected_trial_frame["analysis_is_nonstep"].fillna(False).sum()),
        },
        "overall_mode_summary": overall_rows,
        "cluster_summary": cluster_rows,
        "cluster_k_curve_summary": cluster_curve_rows,
        "cluster_validity_summary": cluster_validity_summary_rows,
        "cluster_validity_by_cluster": cluster_validity_by_cluster_rows,
        "threshold_transition_summary": transition_rows,
        "subject_strategy_summary": subject_rows,
        "threshold_component_summary": threshold_component_rows,
    }


def _write_summary(out_dir: Path, payload: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8-sig") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)
    return summary_path


def _write_threshold_summaries(out_dir: Path, payload: dict[str, Any]) -> list[Path]:
    written_paths: list[Path] = []
    for threshold in payload["thresholds"]:
        threshold_value = float(threshold)
        threshold_label = _format_threshold(threshold_value)
        threshold_slug = f"vaf_{int(round(threshold_value * 100)):02d}"
        threshold_dir = out_dir / "by_threshold" / threshold_slug
        threshold_dir.mkdir(parents=True, exist_ok=True)
        threshold_payload = {
            "config_path": payload["config_path"],
            "out_dir": str(threshold_dir),
            "threshold": threshold_value,
            "threshold_label": threshold_label,
            "run_metadata": payload["run_metadata"],
            "input": payload["input"],
            "data_summary": payload["data_summary"],
            "overall_mode_summary": [
                row for row in payload["overall_mode_summary"] if row["threshold_label"] == threshold_label
            ],
            "cluster_summary": [
                row for row in payload["cluster_summary"] if row["threshold_label"] == threshold_label
            ],
            "cluster_k_curve_summary": [
                row for row in payload["cluster_k_curve_summary"] if row["threshold_label"] == threshold_label
            ],
            "cluster_validity_summary": [
                row for row in payload["cluster_validity_summary"] if row["threshold_label"] == threshold_label
            ],
            "cluster_validity_by_cluster": [
                row for row in payload["cluster_validity_by_cluster"] if row["threshold_label"] == threshold_label
            ],
            "threshold_transition_context": [
                row
                for row in payload["threshold_transition_summary"]
                if row["from_threshold_label"] == threshold_label or row["to_threshold_label"] == threshold_label
            ],
            "subject_strategy_summary": [
                row for row in payload["subject_strategy_summary"] if row["threshold_label"] == threshold_label
            ],
            "threshold_component_summary": [
                row for row in payload["threshold_component_summary"] if row["threshold_label"] == threshold_label
            ],
        }
        threshold_path = threshold_dir / "summary.json"
        with threshold_path.open("w", encoding="utf-8-sig") as handle:
            json.dump(threshold_payload, handle, ensure_ascii=False, indent=2, default=_json_default)
        written_paths.append(threshold_path)
    return written_paths


def _write_checksums(out_dir: Path, paths: list[Path]) -> Path:
    checksum_path = out_dir / "checksums.md5"
    checksum_path.write_text("\n".join(_checksum_lines(out_dir, paths)) + "\n", encoding="utf-8")
    return checksum_path


def _print_payload_summary(payload: dict[str, Any]) -> None:
    _print_section("Data Summary")
    data_summary = payload["data_summary"]
    for key, value in data_summary.items():
        print(f"{key}: {value}")

    _print_section("Cluster K Summary")
    print(
        _render_table(
            payload["cluster_summary"],
            [
                "mode",
                "threshold_label",
                "analysis_unit_count",
                "component_count_total",
                "k_lb",
                "k_gap_raw",
                "k_selected",
                "k_selected_minus_gap_raw",
                "duplicate_trial_count_at_gap_raw",
                "k_min_unique",
                "selection_status",
            ],
        )
    )

    _print_section("Threshold Component Summary")
    print(
        _render_table(
            payload["threshold_component_summary"],
            [
                "mode",
                "threshold_label",
                "subject_count_total",
                "step_subject_count",
                "step_component_mean_sd",
                "step_component_range",
                "step_ceiling_hit_rate",
                "nonstep_subject_count",
                "nonstep_component_mean_sd",
                "nonstep_component_range",
                "nonstep_ceiling_hit_rate",
            ],
        )
    )

    _print_section("Cluster Validity Summary")
    print(
        _render_table(
            payload["cluster_validity_summary"],
            [
                "mode",
                "threshold_label",
                "cluster_count_total",
                "shared_cluster_rate",
                "shared_member_rate",
                "pooled_member_cosine_mean",
                "shared_subcentroid_cosine_weighted_mean",
                "tiny_cluster_rate",
                "singleton_cluster_rate",
            ],
        )
    )

    _print_section("Adjacent Threshold Transitions")
    print(
        _render_table(
            payload["threshold_transition_summary"],
            [
                "mode",
                "threshold_transition",
                "component_mean_delta",
                "vaf_mean_delta",
                "vaf_gain_per_component",
                "k_selected_delta",
                "duplicate_trial_count_at_gap_raw_delta",
                "pooled_member_cosine_mean_delta",
                "tiny_cluster_rate_delta",
            ],
        )
    )

    subject_rows = payload["subject_strategy_summary"]
    threshold_labels = [_format_threshold(float(value)) for value in payload["thresholds"]]
    for mode in MODE_ORDER:
        for step_class in STEP_CLASS_ORDER:
            _print_section(f"Subject Summary: {mode} / {step_class}")
            print(
                _render_table(
                    _subject_strategy_matrix(
                        subject_rows,
                        mode=mode,
                        step_class=step_class,
                        threshold_labels=threshold_labels,
                    ),
                    ["subject", "analysis_unit_count", "velocity_count", *threshold_labels],
                )
            )


def main() -> None:
    args = parse_args()
    cfg = load_pipeline_config(args.config)
    merged_df, trial_records = _load_trial_records(cfg)
    selected_trial_frame = merged_df.drop_duplicates(subset=["subject", "velocity", "trial_num"]).copy()
    if "analysis_selected_group" in selected_trial_frame.columns:
        selected_trial_frame = selected_trial_frame.loc[selected_trial_frame["analysis_selected_group"].fillna(False)].copy()
    muscle_names = [name for name in cfg["muscles"]["names"] if name in merged_df.columns]

    print("=" * 72)
    print("VAF Threshold Sensitivity")
    print("=" * 72)
    print(f"Config: {args.config}")
    print(f"Selected trials: {len(selected_trial_frame)}")
    print(f"Subjects: {sorted(selected_trial_frame['subject'].astype(str).unique().tolist())}")
    print(f"Thresholds: {[ _format_threshold(value) for value in args.thresholds ]}")
    if any(
        value is not None
        for value in (
            args.cluster_repeats,
            args.gap_ref_n,
            args.gap_ref_restarts,
            args.uniqueness_candidate_restarts,
        )
    ):
        print(
            "Clustering overrides: "
            f"repeats={args.cluster_repeats}, "
            f"gap_ref_n={args.gap_ref_n}, "
            f"gap_ref_restarts={args.gap_ref_restarts}, "
            f"uniqueness_candidate_restarts={args.uniqueness_candidate_restarts}"
        )

    if args.dry_run:
        print("\nDry run complete. Input loading and trial extraction succeeded.")
        return

    _print_section("Preparing cached NMF candidates")
    prepared_trialwise_units = _prepare_trialwise_units(trial_records, cfg, muscle_names)
    prepared_concatenated_units = _prepare_concatenated_units(trial_records, muscle_names, cfg)
    print(f"trialwise cached units: {len(prepared_trialwise_units)}")
    print(f"concatenated cached units: {len(prepared_concatenated_units)}")

    threshold_results: dict[str, list[ThresholdModeResult]] = {mode: [] for mode in MODE_ORDER}
    for threshold in args.thresholds:
        _print_section(f"Running threshold {_format_threshold(threshold)}")
        run_results = _run_threshold_analysis(
            prepared_trialwise_units,
            prepared_concatenated_units,
            cfg,
            float(threshold),
            args,
        )
        for mode in MODE_ORDER:
            threshold_results[mode].append(run_results[mode])
            cluster_result = run_results[mode].cluster_result
            print(
                f"{mode}: units={len(run_results[mode].feature_rows)}, "
                f"components={cluster_result.get('n_components')}, "
                f"K={cluster_result.get('k_selected')} "
                f"(gap_raw={cluster_result.get('k_gap_raw')}, status={cluster_result.get('selection_status')})"
            )

    payload = _build_report_payload(args, cfg, merged_df, trial_records, threshold_results)
    summary_path = _write_summary(args.out_dir, payload)
    threshold_summary_paths = _write_threshold_summaries(args.out_dir, payload)
    checksum_path = _write_checksums(args.out_dir, [summary_path, *threshold_summary_paths])
    _print_payload_summary(payload)

    print("\nArtifacts")
    print("---------")
    print(f"summary.json: {summary_path}")
    for threshold_path in threshold_summary_paths:
        print(f"threshold summary: {threshold_path}")
    print(f"checksums.md5: {checksum_path}")


if __name__ == "__main__":
    main()
