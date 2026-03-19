"""Run local-VAF and reconstruction validity checks for VAF thresholds.

This analysis extends the existing threshold sweep with local VAF,
source-trial-safe null models, hold-out reconstruction, and
cross-condition reconstruction inside analysis/vaf_threshold_sensitivity/.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yaml

from src.emg_pipeline import (
    build_trial_records,
    load_emg_table,
    load_event_metadata,
    load_pipeline_config,
    merge_event_metadata,
)
from src.synergy_stats.nmf import _compute_vaf, _fit_rank, _normalize_components

from analysis.vaf_threshold_sensitivity.validation_helpers import (
    compute_local_vaf,
    generate_null_trial,
    reconstruct_with_fixed_w,
    split_concatenated_trial_matrix,
    summarize_source_trial_split_local_vaf,
    summarize_subject_muscle_channel_local_vaf,
)


DEFAULT_VALIDATION_CONFIG = SCRIPT_DIR / "config_validation.yaml"
DEFAULT_OUT_DIR = SCRIPT_DIR / "artifacts" / "validity_default_run"
STEP_CLASS_ORDER = ("step", "nonstep")
DEFAULT_NULL_PROGRESS_EVERY = 5
DEFAULT_HOLDOUT_PROGRESS_EVERY = 10


@dataclass
class RankCandidate:
    """Cached NMF result for one rank candidate."""

    rank: int
    W_muscle: np.ndarray
    H_time: np.ndarray
    vaf: float
    extractor_backend: str
    extractor_torch_device: str
    extractor_torch_dtype: str


@dataclass
class SourceTrial:
    """One source trial used inside trialwise or concatenated analyses."""

    subject: str
    velocity: Any
    trial_num: Any
    step_class: str
    matrix: np.ndarray
    metadata: dict[str, Any]


@dataclass
class AnalysisUnit:
    """Prepared analysis unit with cached rank candidates and raw data."""

    mode: str
    subject: str
    velocity: Any
    trial_num: Any
    step_class: str
    analysis_unit_id: str
    x_matrix: np.ndarray
    source_trials: list[SourceTrial]
    candidates: list[RankCandidate]
    elapsed_sec: float


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for validity analysis runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "global_config.yaml",
        help="Merged pipeline entry config.",
    )
    parser.add_argument(
        "--validation-config",
        type=Path,
        default=DEFAULT_VALIDATION_CONFIG,
        help="YAML config for the validation layer.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Optional override for the validation artifact directory.",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=None,
        help="Optional threshold override.",
    )
    parser.add_argument(
        "--null-method",
        nargs="+",
        default=None,
        help="Optional null-method override (circular_shift and/or time_shuffle).",
    )
    parser.add_argument(
        "--null-repeats",
        type=int,
        default=None,
        help="Optional null-repeat override.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed override for deterministic reruns.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate inputs and eligibility counts.",
    )
    return parser.parse_args()


def _print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def _format_threshold(threshold: float) -> str:
    return f"{int(round(float(threshold) * 100)):d}%"


def _format_id_part(value: Any) -> str:
    return str(value).strip().replace("/", "-").replace("\\", "-").replace(" ", "_")


def _sort_key(value: Any) -> tuple[int, Any]:
    if isinstance(value, (int, np.integer)):
        return (0, int(value))
    if isinstance(value, float) and float(value).is_integer():
        return (0, int(value))
    return (1, str(value))


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


def _opposite_step_class(step_class: str) -> str:
    if step_class == "step":
        return "nonstep"
    if step_class == "nonstep":
        return "step"
    raise ValueError(f"Unsupported step class: {step_class}")


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def _sd(values: list[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    return float(statistics.stdev(values))


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator / denominator)


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    if not np.isfinite(value):
        return None
    return round(float(value), digits)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping at {path}")
    return payload


def _load_validation_config(path: Path) -> dict[str, Any]:
    payload = _load_yaml(path)
    payload.setdefault("thresholds", [0.89, 0.90, 0.91])
    payload.setdefault("local_vaf_floor", 0.75)
    payload.setdefault("variance_epsilon", 1e-8)
    payload.setdefault("null_methods", ["circular_shift"])
    payload.setdefault("null_repeats_screening", 100)
    payload.setdefault("null_repeats_exact", 500)
    payload.setdefault("holdout_min_trials", 2)
    payload.setdefault("seed", 42)
    payload.setdefault("out_dir", str(DEFAULT_OUT_DIR))
    payload.setdefault("null_progress_every", DEFAULT_NULL_PROGRESS_EVERY)
    payload.setdefault("holdout_progress_every", DEFAULT_HOLDOUT_PROGRESS_EVERY)
    return payload


def _resolve_validation_settings(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    settings = deepcopy(payload)
    settings["thresholds"] = [float(value) for value in (args.thresholds if args.thresholds is not None else payload["thresholds"])]
    settings["null_methods"] = [
        str(value).strip().lower()
        for value in (args.null_method if args.null_method is not None else payload["null_methods"])
    ]
    settings["null_repeats"] = int(
        args.null_repeats
        if args.null_repeats is not None
        else payload.get("null_repeats_screening", payload.get("null_repeats_exact", 100))
    )
    settings["seed"] = int(args.seed if args.seed is not None else payload["seed"])
    settings["out_dir"] = str(args.out_dir if args.out_dir is not None else payload["out_dir"])
    settings["local_vaf_floor"] = float(payload["local_vaf_floor"])
    settings["variance_epsilon"] = float(payload["variance_epsilon"])
    settings["holdout_min_trials"] = int(payload["holdout_min_trials"])
    settings["null_progress_every"] = int(payload["null_progress_every"])
    settings["holdout_progress_every"] = int(payload["holdout_progress_every"])
    return settings


def _threshold_items(thresholds: list[float]) -> list[tuple[float, str]]:
    return [(float(value), _format_threshold(float(value))) for value in thresholds]


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


def _select_candidate_for_threshold(candidates: list[RankCandidate], threshold: float) -> RankCandidate:
    for candidate in candidates:
        if float(candidate.vaf) >= float(threshold):
            return candidate
    return max(candidates, key=lambda item: item.vaf)


def _load_trial_records(cfg: dict[str, Any]) -> tuple[pd.DataFrame, list[Any]]:
    emg_df = load_emg_table(cfg["input"]["emg_parquet_path"])
    event_df = load_event_metadata(cfg["input"]["event_xlsm_path"], cfg)
    merged_df = merge_event_metadata(emg_df, event_df)
    trial_records = build_trial_records(merged_df, cfg)
    return merged_df, trial_records


def _prepare_trialwise_units(
    trial_records: list[Any],
    cfg: dict[str, Any],
    muscle_names: list[str],
) -> list[AnalysisUnit]:
    prepared_units: list[AnalysisUnit] = []
    for trial in trial_records:
        step_class = str(trial.metadata.get("analysis_step_class", "")).strip().lower()
        if step_class not in STEP_CLASS_ORDER:
            continue
        x_trial = trial.frame[muscle_names].to_numpy(dtype=np.float32, copy=True)
        candidates, elapsed_sec = _fit_rank_candidates(x_trial, cfg)
        source_trial = SourceTrial(
            subject=str(trial.key[0]),
            velocity=trial.key[1],
            trial_num=trial.key[2],
            step_class=step_class,
            matrix=x_trial,
            metadata=_source_trial_detail(trial, source_trial_order=1, step_class=step_class),
        )
        prepared_units.append(
            AnalysisUnit(
                mode="trialwise",
                subject=str(trial.key[0]),
                velocity=trial.key[1],
                trial_num=trial.key[2],
                step_class=step_class,
                analysis_unit_id=f"{_format_id_part(trial.key[0])}_v{_format_id_part(trial.key[1])}_T{_format_id_part(trial.key[2])}",
                x_matrix=x_trial,
                source_trials=[source_trial],
                candidates=candidates,
                elapsed_sec=elapsed_sec,
            )
        )
    return prepared_units


def _prepare_concatenated_units(
    trial_records: list[Any],
    cfg: dict[str, Any],
    muscle_names: list[str],
) -> list[AnalysisUnit]:
    grouped: dict[tuple[str, Any, str], list[Any]] = defaultdict(list)
    for trial in trial_records:
        if not _meta_flag(trial.metadata.get("analysis_selected_group", True)):
            continue
        step_class = str(trial.metadata.get("analysis_step_class", "")).strip().lower()
        if step_class not in STEP_CLASS_ORDER:
            continue
        grouped[(str(trial.key[0]), trial.key[1], step_class)].append(trial)

    prepared_units: list[AnalysisUnit] = []
    for (subject, velocity, step_class), trials in sorted(
        grouped.items(),
        key=lambda item: (_sort_key(item[0][0]), _sort_key(item[0][1]), item[0][2]),
    ):
        ordered_trials = sorted(trials, key=lambda trial: _sort_key(trial.key[2]))
        source_trials = [
            SourceTrial(
                subject=subject,
                velocity=velocity,
                trial_num=trial.key[2],
                step_class=step_class,
                matrix=trial.frame[muscle_names].to_numpy(dtype=np.float32, copy=True),
                metadata=_source_trial_detail(trial, source_trial_order=index + 1, step_class=step_class),
            )
            for index, trial in enumerate(ordered_trials)
        ]
        concatenated_matrix = np.concatenate([source_trial.matrix for source_trial in source_trials], axis=0)
        candidates, elapsed_sec = _fit_rank_candidates(concatenated_matrix, cfg)
        prepared_units.append(
            AnalysisUnit(
                mode="concatenated",
                subject=subject,
                velocity=velocity,
                trial_num=f"concat_{step_class}",
                step_class=step_class,
                analysis_unit_id=f"{_format_id_part(subject)}_v{_format_id_part(velocity)}_{step_class}_concat",
                x_matrix=concatenated_matrix,
                source_trials=source_trials,
                candidates=candidates,
                elapsed_sec=elapsed_sec,
            )
        )
    return prepared_units


def _count_holdout_eligible_groups(
    trial_records: list[Any],
    *,
    holdout_min_trials: int,
) -> int:
    grouped_counts: dict[tuple[str, Any, str], int] = defaultdict(int)
    for trial in trial_records:
        if not _meta_flag(trial.metadata.get("analysis_selected_group", True)):
            continue
        step_class = str(trial.metadata.get("analysis_step_class", "")).strip().lower()
        if step_class not in STEP_CLASS_ORDER:
            continue
        grouped_counts[(str(trial.key[0]), trial.key[1], step_class)] += 1
    return int(sum(count >= int(holdout_min_trials) for count in grouped_counts.values()))


def _local_vaf_unit_rows(
    unit: AnalysisUnit,
    candidate: RankCandidate,
    *,
    threshold: float,
    muscle_names: list[str],
    local_vaf_floor: float,
    variance_epsilon: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    threshold_label = _format_threshold(threshold)
    x_hat = np.asarray(candidate.H_time @ candidate.W_muscle.T, dtype=np.float32)
    local_summary = compute_local_vaf(
        unit.x_matrix,
        x_hat,
        variance_epsilon,
        channel_names=muscle_names,
        local_vaf_floor=local_vaf_floor,
    )
    unit_row = {
        "mode": unit.mode,
        "threshold": float(threshold),
        "threshold_label": threshold_label,
        "subject": unit.subject,
        "velocity": unit.velocity,
        "step_class": unit.step_class,
        "trial_num": unit.trial_num,
        "unit_id": unit.analysis_unit_id,
        "analysis_source_trial_count": int(len(unit.source_trials)),
        "selected_rank": int(candidate.rank),
        "global_vaf": float(candidate.vaf),
        "muscle_pass_rate_75": local_summary["muscle_pass_rate"],
        "all_muscles_pass_75": local_summary["all_muscles_pass"],
        "min_local_vaf": local_summary["min_local_vaf"],
        "median_local_vaf": local_summary["median_local_vaf"],
        "applicable_channel_count": int(local_summary["n_applicable_channels"]),
        "not_applicable_channel_count": int(local_summary["n_not_applicable_channels"]),
    }
    channel_rows = []
    for row in local_summary["channel_rows"]:
        channel_row = dict(unit_row)
        channel_row.update(
            {
                "muscle": row["muscle"],
                "channel_index": int(row["channel_index"]),
                "local_vaf": row["local_vaf"],
                "status": row["status"],
                "pass_floor_75": row["pass_floor"],
                "is_worst_muscle": bool(row["is_worst_muscle"]),
            }
        )
        channel_rows.append(channel_row)
    return unit_row, channel_rows, {"x_hat": x_hat, "local_summary": local_summary}


def _source_trial_split_rows(
    unit: AnalysisUnit,
    unit_row: dict[str, Any],
    x_hat: np.ndarray,
    *,
    threshold: float,
    muscle_names: list[str],
    local_vaf_floor: float,
    variance_epsilon: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed_segments = split_concatenated_trial_matrix(
        unit.x_matrix,
        [source_trial.matrix.shape[0] for source_trial in unit.source_trials],
    )
    reconstructed_segments = split_concatenated_trial_matrix(
        x_hat,
        [source_trial.matrix.shape[0] for source_trial in unit.source_trials],
    )

    split_unit_rows: list[dict[str, Any]] = []
    split_channel_rows: list[dict[str, Any]] = []
    threshold_label = _format_threshold(threshold)
    for source_trial, observed_segment, reconstructed_segment in zip(
        unit.source_trials,
        observed_segments,
        reconstructed_segments,
    ):
        local_summary = compute_local_vaf(
            observed_segment,
            reconstructed_segment,
            variance_epsilon,
            channel_names=muscle_names,
            local_vaf_floor=local_vaf_floor,
        )
        source_unit_id = f"{unit.analysis_unit_id}::source::{_format_id_part(source_trial.trial_num)}"
        split_unit_row = {
            "mode": unit.mode,
            "threshold": float(threshold),
            "threshold_label": threshold_label,
            "subject": unit.subject,
            "velocity": unit.velocity,
            "step_class": unit.step_class,
            "trial_num": unit.trial_num,
            "unit_id": source_unit_id,
            "parent_unit_id": unit.analysis_unit_id,
            "source_trial_num": source_trial.trial_num,
            "selected_rank": int(unit_row["selected_rank"]),
            "global_vaf": unit_row["global_vaf"],
            "muscle_pass_rate_75": local_summary["muscle_pass_rate"],
            "all_muscles_pass_75": local_summary["all_muscles_pass"],
            "min_local_vaf": local_summary["min_local_vaf"],
            "median_local_vaf": local_summary["median_local_vaf"],
            "applicable_channel_count": int(local_summary["n_applicable_channels"]),
            "not_applicable_channel_count": int(local_summary["n_not_applicable_channels"]),
        }
        split_unit_rows.append(split_unit_row)
        for row in local_summary["channel_rows"]:
            split_channel_row = dict(split_unit_row)
            split_channel_row.update(
                {
                    "muscle": row["muscle"],
                    "channel_index": int(row["channel_index"]),
                    "local_vaf": row["local_vaf"],
                    "status": row["status"],
                    "pass_floor_75": row["pass_floor"],
                    "is_worst_muscle": bool(row["is_worst_muscle"]),
                }
            )
            split_channel_rows.append(split_channel_row)
    return split_unit_rows, split_channel_rows


def evaluate_local_vaf(
    trialwise_units: list[AnalysisUnit],
    concatenated_units: list[AnalysisUnit],
    *,
    thresholds: list[float],
    muscle_names: list[str],
    local_vaf_floor: float,
    variance_epsilon: float,
) -> dict[str, Any]:
    """Compute observed local VAF summaries for trialwise and concatenated modes."""
    trialwise_unit_rows: list[dict[str, Any]] = []
    trialwise_channel_rows: list[dict[str, Any]] = []
    trialwise_summary_rows: list[dict[str, Any]] = []
    concat_primary_unit_rows: list[dict[str, Any]] = []
    concat_primary_channel_rows: list[dict[str, Any]] = []
    concat_primary_summary_rows: list[dict[str, Any]] = []
    concat_secondary_unit_rows: list[dict[str, Any]] = []
    concat_secondary_channel_rows: list[dict[str, Any]] = []
    concat_secondary_summary_rows: list[dict[str, Any]] = []

    for threshold in thresholds:
        threshold_label = _format_threshold(threshold)

        threshold_trialwise_units: list[dict[str, Any]] = []
        threshold_trialwise_channels: list[dict[str, Any]] = []
        for unit in trialwise_units:
            candidate = _select_candidate_for_threshold(unit.candidates, threshold)
            unit_row, channel_rows, _ = _local_vaf_unit_rows(
                unit,
                candidate,
                threshold=threshold,
                muscle_names=muscle_names,
                local_vaf_floor=local_vaf_floor,
                variance_epsilon=variance_epsilon,
            )
            threshold_trialwise_units.append(unit_row)
            threshold_trialwise_channels.extend(channel_rows)
        trialwise_unit_rows.extend(threshold_trialwise_units)
        trialwise_channel_rows.extend(threshold_trialwise_channels)
        trialwise_summary = summarize_subject_muscle_channel_local_vaf(
            threshold_trialwise_channels,
            local_vaf_floor=local_vaf_floor,
        )
        trialwise_summary_rows.append(
            {
                "mode": "trialwise",
                "threshold": float(threshold),
                "threshold_label": threshold_label,
                "summary_layer": "trial_channel",
                "selected_rank_mean": _round_or_none(
                    _mean([float(row["selected_rank"]) for row in threshold_trialwise_units]),
                    4,
                ),
                "global_vaf_mean": _round_or_none(
                    _mean([float(row["global_vaf"]) for row in threshold_trialwise_units]),
                    6,
                ),
                **trialwise_summary,
            }
        )

        threshold_concat_primary_units: list[dict[str, Any]] = []
        threshold_concat_primary_channels: list[dict[str, Any]] = []
        threshold_concat_secondary_units: list[dict[str, Any]] = []
        threshold_concat_secondary_channels: list[dict[str, Any]] = []
        for unit in concatenated_units:
            candidate = _select_candidate_for_threshold(unit.candidates, threshold)
            unit_row, channel_rows, extras = _local_vaf_unit_rows(
                unit,
                candidate,
                threshold=threshold,
                muscle_names=muscle_names,
                local_vaf_floor=local_vaf_floor,
                variance_epsilon=variance_epsilon,
            )
            split_unit_rows, split_channel_rows = _source_trial_split_rows(
                unit,
                unit_row,
                extras["x_hat"],
                threshold=threshold,
                muscle_names=muscle_names,
                local_vaf_floor=local_vaf_floor,
                variance_epsilon=variance_epsilon,
            )
            threshold_concat_primary_units.append(unit_row)
            threshold_concat_primary_channels.extend(channel_rows)
            threshold_concat_secondary_units.extend(split_unit_rows)
            threshold_concat_secondary_channels.extend(split_channel_rows)

        concat_primary_unit_rows.extend(threshold_concat_primary_units)
        concat_primary_channel_rows.extend(threshold_concat_primary_channels)
        concat_secondary_unit_rows.extend(threshold_concat_secondary_units)
        concat_secondary_channel_rows.extend(threshold_concat_secondary_channels)

        primary_summary = summarize_subject_muscle_channel_local_vaf(
            threshold_concat_primary_channels,
            local_vaf_floor=local_vaf_floor,
        )
        concat_primary_summary_rows.append(
            {
                "mode": "concatenated",
                "threshold": float(threshold),
                "threshold_label": threshold_label,
                "summary_layer": "subject_muscle_channel",
                "selected_rank_mean": _round_or_none(
                    _mean([float(row["selected_rank"]) for row in threshold_concat_primary_units]),
                    4,
                ),
                "global_vaf_mean": _round_or_none(
                    _mean([float(row["global_vaf"]) for row in threshold_concat_primary_units]),
                    6,
                ),
                **primary_summary,
            }
        )

        secondary_summary = summarize_source_trial_split_local_vaf(
            threshold_concat_secondary_channels,
            local_vaf_floor=local_vaf_floor,
        )
        concat_secondary_summary_rows.append(
            {
                "mode": "concatenated",
                "threshold": float(threshold),
                "threshold_label": threshold_label,
                "summary_layer": "source_trial_split",
                "selected_rank_mean": _round_or_none(
                    _mean([float(row["selected_rank"]) for row in threshold_concat_secondary_units]),
                    4,
                ),
                "global_vaf_mean": _round_or_none(
                    _mean([float(row["global_vaf"]) for row in threshold_concat_secondary_units]),
                    6,
                ),
                **secondary_summary,
            }
        )

    return {
        "trialwise_summary": trialwise_summary_rows,
        "trialwise_unit_rows": trialwise_unit_rows,
        "trialwise_channel_rows": trialwise_channel_rows,
        "concatenated": {
            "subject_muscle_channel_summary": concat_primary_summary_rows,
            "subject_muscle_channel_unit_rows": concat_primary_unit_rows,
            "subject_muscle_channel_rows": concat_primary_channel_rows,
            "source_trial_split_summary": concat_secondary_summary_rows,
            "source_trial_split_unit_rows": concat_secondary_unit_rows,
            "source_trial_split_rows": concat_secondary_channel_rows,
        },
    }


def evaluate_null_model(
    mode_units: dict[str, list[AnalysisUnit]],
    observed_local_vaf: dict[str, Any],
    *,
    thresholds: list[float],
    muscle_names: list[str],
    local_vaf_floor: float,
    variance_epsilon: float,
    null_methods: list[str],
    null_repeats: int,
    base_cfg: dict[str, Any],
    seed: int,
    progress_every: int,
) -> dict[str, Any]:
    """Run source-trial-safe null-model reruns and compare with observed data."""
    unit_rows: list[dict[str, Any]] = []
    subject_repeat_rows: list[dict[str, Any]] = []
    subject_summary_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    threshold_items = _threshold_items(thresholds)

    observed_unit_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in observed_local_vaf["trialwise_unit_rows"]:
        observed_unit_lookup[("trialwise", row["threshold_label"], row["unit_id"])] = row
    for row in observed_local_vaf["concatenated"]["subject_muscle_channel_unit_rows"]:
        observed_unit_lookup[("concatenated", row["threshold_label"], row["unit_id"])] = row

    for mode_index, mode in enumerate(("trialwise", "concatenated")):
        units = mode_units[mode]
        for method_index, null_method in enumerate(null_methods):
            rng = np.random.default_rng(
                int(seed) + (mode_index * 10_000) + (method_index * 1_000)
            )
            current_subject_repeat_rows_by_threshold: dict[str, list[dict[str, Any]]] = {
                threshold_label: []
                for _, threshold_label in threshold_items
            }
            repeat_start = time.perf_counter()
            for repeat_index in range(int(null_repeats)):
                repeat_rows_by_threshold: dict[str, list[dict[str, Any]]] = {
                    threshold_label: []
                    for _, threshold_label in threshold_items
                }
                for unit in units:
                    null_sources = [
                        generate_null_trial(source_trial.matrix, null_method, rng)
                        for source_trial in unit.source_trials
                    ]
                    x_null = (
                        null_sources[0]
                        if len(null_sources) == 1
                        else np.concatenate(null_sources, axis=0)
                    )
                    null_candidates, elapsed_sec = _fit_rank_candidates(x_null, base_cfg)
                    for threshold, threshold_label in threshold_items:
                        selected = _select_candidate_for_threshold(null_candidates, threshold)
                        x_hat = np.asarray(selected.H_time @ selected.W_muscle.T, dtype=np.float32)
                        local_summary = compute_local_vaf(
                            x_null,
                            x_hat,
                            variance_epsilon,
                            channel_names=muscle_names,
                            local_vaf_floor=local_vaf_floor,
                        )
                        observed_unit = observed_unit_lookup[(mode, threshold_label, unit.analysis_unit_id)]
                        row = {
                            "mode": mode,
                            "threshold": float(threshold),
                            "threshold_label": threshold_label,
                            "null_method": null_method,
                            "repeat_index": int(repeat_index),
                            "subject": unit.subject,
                            "velocity": unit.velocity,
                            "step_class": unit.step_class,
                            "unit_id": unit.analysis_unit_id,
                            "selected_rank": int(selected.rank),
                            "global_vaf": float(selected.vaf),
                            "muscle_pass_rate_75": local_summary["muscle_pass_rate"],
                            "min_local_vaf": local_summary["min_local_vaf"],
                            "median_local_vaf": local_summary["median_local_vaf"],
                            "all_muscles_pass_75": local_summary["all_muscles_pass"],
                            "elapsed_sec": float(elapsed_sec),
                            "observed_selected_rank": float(observed_unit["selected_rank"]),
                            "observed_muscle_pass_rate_75": observed_unit["muscle_pass_rate_75"],
                        }
                        repeat_rows_by_threshold[threshold_label].append(row)
                        unit_rows.append(row)

                for threshold, threshold_label in threshold_items:
                    rows_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
                    for row in repeat_rows_by_threshold[threshold_label]:
                        rows_by_subject[str(row["subject"])].append(row)
                    for subject, rows in sorted(rows_by_subject.items()):
                        observed_rows = [
                            observed_unit_lookup[(mode, threshold_label, row["unit_id"])]
                            for row in rows
                        ]
                        current_subject_repeat_rows_by_threshold[threshold_label].append(
                            {
                                "mode": mode,
                                "threshold": float(threshold),
                                "threshold_label": threshold_label,
                                "null_method": null_method,
                                "repeat_index": int(repeat_index),
                                "subject": subject,
                                "unit_count": int(len(rows)),
                                "observed_selected_rank_mean": _mean(
                                    [float(item["selected_rank"]) for item in observed_rows]
                                ),
                                "observed_muscle_pass_rate_75_mean": _mean(
                                    [
                                        float(item["muscle_pass_rate_75"])
                                        for item in observed_rows
                                        if item["muscle_pass_rate_75"] is not None
                                    ]
                                ),
                                "null_selected_rank_mean": _mean([float(item["selected_rank"]) for item in rows]),
                                "null_muscle_pass_rate_75_mean": _mean(
                                    [
                                        float(item["muscle_pass_rate_75"])
                                        for item in rows
                                        if item["muscle_pass_rate_75"] is not None
                                    ]
                                ),
                            }
                        )

                if progress_every > 0 and (
                    repeat_index == 0
                    or (repeat_index + 1) % int(progress_every) == 0
                    or (repeat_index + 1) == int(null_repeats)
                ):
                    elapsed = time.perf_counter() - repeat_start
                    repeats_done = repeat_index + 1
                    repeats_left = int(null_repeats) - repeats_done
                    avg_sec_per_repeat = elapsed / repeats_done
                    eta_sec = avg_sec_per_repeat * repeats_left
                    print(
                        f"[null] mode={mode} method={null_method} "
                        f"repeat={repeats_done}/{int(null_repeats)} "
                        f"elapsed={elapsed:.1f}s eta={eta_sec:.1f}s"
                    )

            for threshold, threshold_label in threshold_items:
                current_subject_repeat_rows = current_subject_repeat_rows_by_threshold[threshold_label]
                subject_repeat_rows.extend(current_subject_repeat_rows)
                rows_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for row in current_subject_repeat_rows:
                    rows_by_subject[str(row["subject"])].append(row)
                current_subject_summary_rows: list[dict[str, Any]] = []
                for subject, rows in sorted(rows_by_subject.items()):
                    null_rank_values = [
                        float(row["null_selected_rank_mean"])
                        for row in rows
                        if row["null_selected_rank_mean"] is not None
                    ]
                    null_pass_values = [
                        float(row["null_muscle_pass_rate_75_mean"])
                        for row in rows
                        if row["null_muscle_pass_rate_75_mean"] is not None
                    ]
                    observed_rank = rows[0]["observed_selected_rank_mean"]
                    observed_pass = rows[0]["observed_muscle_pass_rate_75_mean"]
                    current_subject_summary_rows.append(
                        {
                            "mode": mode,
                            "threshold": float(threshold),
                            "threshold_label": threshold_label,
                            "null_method": null_method,
                            "subject": subject,
                            "unit_count": int(rows[0]["unit_count"]),
                            "observed_selected_rank_mean": _round_or_none(observed_rank, 4),
                            "null_selected_rank_median": _round_or_none(_median(null_rank_values), 4),
                            "compression_advantage": _round_or_none(
                                (_median(null_rank_values) - observed_rank)
                                if observed_rank is not None and null_rank_values
                                else None,
                                4,
                            ),
                            "observed_muscle_pass_rate_75_mean": _round_or_none(observed_pass, 4),
                            "null_muscle_pass_rate_75_median": _round_or_none(_median(null_pass_values), 4),
                            "local_advantage": _round_or_none(
                                (observed_pass - _median(null_pass_values))
                                if observed_pass is not None and null_pass_values
                                else None,
                                4,
                            ),
                        }
                    )

                subject_summary_rows.extend(current_subject_summary_rows)
                summary_rows.append(
                    {
                        "mode": mode,
                        "threshold": float(threshold),
                        "threshold_label": threshold_label,
                        "null_method": null_method,
                        "subject_count": int(len(current_subject_summary_rows)),
                        "repeat_count": int(null_repeats),
                        "unit_count": int(len(units)),
                        "compression_advantage_median": _round_or_none(
                            _median(
                                [
                                    float(row["compression_advantage"])
                                    for row in current_subject_summary_rows
                                    if row["compression_advantage"] is not None
                                ]
                            ),
                            4,
                        ),
                        "local_advantage_median": _round_or_none(
                            _median(
                                [
                                    float(row["local_advantage"])
                                    for row in current_subject_summary_rows
                                    if row["local_advantage"] is not None
                                ]
                            ),
                            4,
                        ),
                        "observed_selected_rank_mean": _round_or_none(
                            _mean(
                                [
                                    float(row["observed_selected_rank_mean"])
                                    for row in current_subject_summary_rows
                                    if row["observed_selected_rank_mean"] is not None
                                ]
                            ),
                            4,
                        ),
                        "null_selected_rank_median_mean": _round_or_none(
                            _mean(
                                [
                                    float(row["null_selected_rank_median"])
                                    for row in current_subject_summary_rows
                                    if row["null_selected_rank_median"] is not None
                                ]
                            ),
                            4,
                        ),
                        "observed_muscle_pass_rate_75_mean": _round_or_none(
                            _mean(
                                [
                                    float(row["observed_muscle_pass_rate_75_mean"])
                                    for row in current_subject_summary_rows
                                    if row["observed_muscle_pass_rate_75_mean"] is not None
                                ]
                            ),
                            4,
                        ),
                        "null_muscle_pass_rate_75_median_mean": _round_or_none(
                            _mean(
                                [
                                    float(row["null_muscle_pass_rate_75_median"])
                                    for row in current_subject_summary_rows
                                    if row["null_muscle_pass_rate_75_median"] is not None
                                ]
                            ),
                            4,
                        ),
                    }
                )
    return {
        "summary_rows": summary_rows,
        "subject_rows": subject_summary_rows,
        "subject_repeat_rows": subject_repeat_rows,
        "unit_rows": unit_rows,
    }


def evaluate_holdout_and_cross_condition(
    concatenated_units: list[AnalysisUnit],
    *,
    thresholds: list[float],
    base_cfg: dict[str, Any],
    muscle_names: list[str],
    local_vaf_floor: float,
    variance_epsilon: float,
    holdout_min_trials: int,
    progress_every: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run within-condition hold-out and opposite-condition cross reconstruction."""
    group_map = {
        (unit.subject, unit.velocity, unit.step_class): unit
        for unit in concatenated_units
    }
    threshold_items = _threshold_items(thresholds)
    eligible_group_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    holdout_summary_rows: list[dict[str, Any]] = []
    cross_pair_rows: list[dict[str, Any]] = []
    cross_summary_rows: list[dict[str, Any]] = []

    base_group_rows: list[dict[str, Any]] = []
    for key, unit in sorted(group_map.items(), key=lambda item: (_sort_key(item[0][0]), _sort_key(item[0][1]), item[0][2])):
        base_group_rows.append(
            {
                "subject": unit.subject,
                "velocity": unit.velocity,
                "step_class": unit.step_class,
                "source_trial_count": int(len(unit.source_trials)),
                "eligible_for_holdout": bool(len(unit.source_trials) >= int(holdout_min_trials)),
            }
        )

    threshold_eligible_rows_by_label: dict[str, list[dict[str, Any]]] = {
        threshold_label: []
        for _, threshold_label in threshold_items
    }
    threshold_fold_rows_by_label: dict[str, list[dict[str, Any]]] = {
        threshold_label: []
        for _, threshold_label in threshold_items
    }
    threshold_cross_rows_by_label: dict[str, list[dict[str, Any]]] = {
        threshold_label: []
        for _, threshold_label in threshold_items
    }
    for threshold, threshold_label in threshold_items:
        for group_row in base_group_rows:
            eligible_row = dict(group_row)
            eligible_row.update(
                {
                    "threshold": float(threshold),
                    "threshold_label": threshold_label,
                }
            )
            threshold_eligible_rows_by_label[threshold_label].append(eligible_row)

    eligible_units = [
        item
        for item in sorted(
            group_map.items(),
            key=lambda item: (_sort_key(item[0][0]), _sort_key(item[0][1]), item[0][2]),
        )
        if len(item[1].source_trials) >= int(holdout_min_trials)
    ]
    total_folds = int(sum(len(unit.source_trials) for _, unit in eligible_units))
    processed_folds = 0
    fold_start = time.perf_counter()

    for (subject, velocity, step_class), unit in eligible_units:
        source_trials = unit.source_trials
        opposite_trials = group_map.get((subject, velocity, _opposite_step_class(step_class)))
        for held_out_index, held_out_trial in enumerate(source_trials):
            processed_folds += 1
            train_trials = [trial for index, trial in enumerate(source_trials) if index != held_out_index]
            train_matrix = np.concatenate([trial.matrix for trial in train_trials], axis=0)
            train_candidates, elapsed_sec = _fit_rank_candidates(train_matrix, base_cfg)
            for threshold, threshold_label in threshold_items:
                selected = _select_candidate_for_threshold(train_candidates, threshold)
                within_h, within_x_hat = reconstruct_with_fixed_w(held_out_trial.matrix, selected.W_muscle)
                within_local = compute_local_vaf(
                    held_out_trial.matrix,
                    within_x_hat,
                    variance_epsilon,
                    channel_names=muscle_names,
                    local_vaf_floor=local_vaf_floor,
                )
                fold_row = {
                    "threshold": float(threshold),
                    "threshold_label": threshold_label,
                    "subject": subject,
                    "velocity": velocity,
                    "step_class": step_class,
                    "held_out_trial_num": held_out_trial.trial_num,
                    "train_source_trial_count": int(len(train_trials)),
                    "selected_rank": int(selected.rank),
                    "fit_elapsed_sec": float(elapsed_sec),
                    "within_test_global_vaf": float(_compute_vaf(held_out_trial.matrix, selected.W_muscle, within_h)),
                    "within_test_local_pass_rate_75": within_local["muscle_pass_rate"],
                    "within_test_min_local_vaf": within_local["min_local_vaf"],
                    "within_test_median_local_vaf": within_local["median_local_vaf"],
                }
                threshold_fold_rows_by_label[threshold_label].append(fold_row)

                if opposite_trials is None:
                    continue
                direction = f"{step_class}->{opposite_trials.step_class}"
                for opposite_trial in opposite_trials.source_trials:
                    cross_h, cross_x_hat = reconstruct_with_fixed_w(opposite_trial.matrix, selected.W_muscle)
                    cross_local = compute_local_vaf(
                        opposite_trial.matrix,
                        cross_x_hat,
                        variance_epsilon,
                        channel_names=muscle_names,
                        local_vaf_floor=local_vaf_floor,
                    )
                    cross_global = float(
                        _compute_vaf(
                            opposite_trial.matrix,
                            selected.W_muscle,
                            cross_h,
                        )
                    )
                    threshold_cross_rows_by_label[threshold_label].append(
                        {
                            "threshold": float(threshold),
                            "threshold_label": threshold_label,
                            "subject": subject,
                            "velocity": velocity,
                            "direction": direction,
                            "train_step_class": step_class,
                            "within_test_trial_num": held_out_trial.trial_num,
                            "cross_test_trial_num": opposite_trial.trial_num,
                            "selected_rank": int(selected.rank),
                            "within_test_global_vaf": fold_row["within_test_global_vaf"],
                            "cross_test_global_vaf": cross_global,
                            "within_test_local_pass_rate_75": fold_row["within_test_local_pass_rate_75"],
                            "cross_test_local_pass_rate_75": cross_local["muscle_pass_rate"],
                            "cross_within_delta": _round_or_none(
                                cross_global - float(fold_row["within_test_global_vaf"]),
                                4,
                            ),
                            "cross_within_ratio": _round_or_none(
                                _safe_ratio(cross_global, float(fold_row["within_test_global_vaf"])),
                                4,
                            ),
                            "cross_within_local_delta": _round_or_none(
                                (
                                    cross_local["muscle_pass_rate"] - fold_row["within_test_local_pass_rate_75"]
                                    if cross_local["muscle_pass_rate"] is not None
                                    and fold_row["within_test_local_pass_rate_75"] is not None
                                    else None
                                ),
                                4,
                            ),
                            "cross_within_local_ratio": _round_or_none(
                                _safe_ratio(
                                    cross_local["muscle_pass_rate"],
                                    fold_row["within_test_local_pass_rate_75"],
                                ),
                                4,
                            ),
                        }
                    )

            if progress_every > 0 and (
                processed_folds == 1
                or processed_folds % int(progress_every) == 0
                or processed_folds == total_folds
            ):
                elapsed = time.perf_counter() - fold_start
                folds_left = total_folds - processed_folds
                avg_sec_per_fold = elapsed / processed_folds
                eta_sec = avg_sec_per_fold * folds_left
                print(
                    f"[holdout] fold={processed_folds}/{total_folds} "
                    f"elapsed={elapsed:.1f}s eta={eta_sec:.1f}s"
                )

    for threshold, threshold_label in threshold_items:
        threshold_eligible_rows = threshold_eligible_rows_by_label[threshold_label]
        threshold_fold_rows = threshold_fold_rows_by_label[threshold_label]
        threshold_cross_rows = threshold_cross_rows_by_label[threshold_label]
        eligible_group_rows.extend(threshold_eligible_rows)
        fold_rows.extend(threshold_fold_rows)
        cross_pair_rows.extend(threshold_cross_rows)

        eligible_subjects = {
            str(row["subject"])
            for row in threshold_eligible_rows
            if bool(row["eligible_for_holdout"])
        }
        skipped_subjects = {
            str(row["subject"])
            for row in threshold_eligible_rows
            if not bool(row["eligible_for_holdout"])
        }
        holdout_summary_rows.append(
            {
                "threshold": float(threshold),
                "threshold_label": threshold_label,
                "eligible_group_count": int(sum(bool(row["eligible_for_holdout"]) for row in threshold_eligible_rows)),
                "skipped_group_count": int(sum(not bool(row["eligible_for_holdout"]) for row in threshold_eligible_rows)),
                "eligible_subject_count": int(len(eligible_subjects)),
                "skipped_subject_count": int(len(skipped_subjects)),
                "fold_count": int(len(threshold_fold_rows)),
                "selected_rank_mean": _round_or_none(
                    _mean([float(row["selected_rank"]) for row in threshold_fold_rows]),
                    4,
                ),
                "within_test_global_vaf_mean": _round_or_none(
                    _mean([float(row["within_test_global_vaf"]) for row in threshold_fold_rows]),
                    4,
                ),
                "within_test_local_pass_rate_75_mean": _round_or_none(
                    _mean(
                        [
                            float(row["within_test_local_pass_rate_75"])
                            for row in threshold_fold_rows
                            if row["within_test_local_pass_rate_75"] is not None
                        ]
                    ),
                    4,
                ),
            }
        )

        for direction in [f"{left}->{right}" for left in STEP_CLASS_ORDER for right in STEP_CLASS_ORDER if left != right]:
            direction_rows = [row for row in threshold_cross_rows if row["direction"] == direction]
            cross_summary_rows.append(
                {
                    "threshold": float(threshold),
                    "threshold_label": threshold_label,
                    "direction": direction,
                    "pair_count": int(len(direction_rows)),
                    "subject_count": int(len({str(row["subject"]) for row in direction_rows})),
                    "selected_rank_mean": _round_or_none(
                        _mean([float(row["selected_rank"]) for row in direction_rows]),
                        4,
                    ),
                    "within_test_global_vaf_mean": _round_or_none(
                        _mean([float(row["within_test_global_vaf"]) for row in direction_rows]),
                        4,
                    ),
                    "cross_test_global_vaf_mean": _round_or_none(
                        _mean([float(row["cross_test_global_vaf"]) for row in direction_rows]),
                        4,
                    ),
                    "within_test_local_pass_rate_75_mean": _round_or_none(
                        _mean(
                            [
                                float(row["within_test_local_pass_rate_75"])
                                for row in direction_rows
                                if row["within_test_local_pass_rate_75"] is not None
                            ]
                        ),
                        4,
                    ),
                    "cross_test_local_pass_rate_75_mean": _round_or_none(
                        _mean(
                            [
                                float(row["cross_test_local_pass_rate_75"])
                                for row in direction_rows
                                if row["cross_test_local_pass_rate_75"] is not None
                            ]
                        ),
                        4,
                    ),
                    "cross_within_delta_mean": _round_or_none(
                        _mean(
                            [
                                float(row["cross_within_delta"])
                                for row in direction_rows
                                if row["cross_within_delta"] is not None
                            ]
                        ),
                        4,
                    ),
                    "cross_within_ratio_mean": _round_or_none(
                        _mean(
                            [
                                float(row["cross_within_ratio"])
                                for row in direction_rows
                                if row["cross_within_ratio"] is not None
                            ]
                        ),
                        4,
                    ),
                    "cross_within_local_delta_mean": _round_or_none(
                        _mean(
                            [
                                float(row["cross_within_local_delta"])
                                for row in direction_rows
                                if row["cross_within_local_delta"] is not None
                            ]
                        ),
                        4,
                    ),
                    "cross_within_local_ratio_mean": _round_or_none(
                        _mean(
                            [
                                float(row["cross_within_local_ratio"])
                                for row in direction_rows
                                if row["cross_within_local_ratio"] is not None
                            ]
                        ),
                        4,
                    ),
                }
            )

    return (
        {
            "summary_rows": holdout_summary_rows,
            "eligible_group_rows": eligible_group_rows,
            "fold_rows": fold_rows,
        },
        {
            "summary_rows": cross_summary_rows,
            "pair_rows": cross_pair_rows,
        },
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        scalar = float(value)
        return scalar if np.isfinite(scalar) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _checksum_lines(base_dir: Path, paths: list[Path]) -> list[str]:
    lines = []
    for path in sorted(paths):
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        try:
            display_path = path.relative_to(base_dir)
        except ValueError:
            display_path = path.name
        lines.append(f"{digest}  {display_path}")
    return lines


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)
    return path


def _filter_rows_by_threshold(rows: list[dict[str, Any]], threshold_label: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("threshold_label") == threshold_label]


def _build_threshold_payload(payload: dict[str, Any], threshold: float) -> dict[str, Any]:
    threshold_label = _format_threshold(threshold)
    return {
        "config_path": payload["config_path"],
        "validation_config_path": payload["validation_config_path"],
        "out_dir": str(Path(payload["out_dir"]) / "by_threshold" / f"vaf_{int(round(threshold * 100)):02d}"),
        "threshold": float(threshold),
        "threshold_label": threshold_label,
        "validation_settings": payload["validation_settings"],
        "input": payload["input"],
        "data_summary": payload["data_summary"],
        "local_vaf": {
            "trialwise_summary": _filter_rows_by_threshold(payload["local_vaf"]["trialwise_summary"], threshold_label),
            "trialwise_unit_rows": _filter_rows_by_threshold(payload["local_vaf"]["trialwise_unit_rows"], threshold_label),
            "trialwise_channel_rows": _filter_rows_by_threshold(payload["local_vaf"]["trialwise_channel_rows"], threshold_label),
            "concatenated": {
                "subject_muscle_channel_summary": _filter_rows_by_threshold(
                    payload["local_vaf"]["concatenated"]["subject_muscle_channel_summary"],
                    threshold_label,
                ),
                "subject_muscle_channel_unit_rows": _filter_rows_by_threshold(
                    payload["local_vaf"]["concatenated"]["subject_muscle_channel_unit_rows"],
                    threshold_label,
                ),
                "subject_muscle_channel_rows": _filter_rows_by_threshold(
                    payload["local_vaf"]["concatenated"]["subject_muscle_channel_rows"],
                    threshold_label,
                ),
                "source_trial_split_summary": _filter_rows_by_threshold(
                    payload["local_vaf"]["concatenated"]["source_trial_split_summary"],
                    threshold_label,
                ),
                "source_trial_split_unit_rows": _filter_rows_by_threshold(
                    payload["local_vaf"]["concatenated"]["source_trial_split_unit_rows"],
                    threshold_label,
                ),
                "source_trial_split_rows": _filter_rows_by_threshold(
                    payload["local_vaf"]["concatenated"]["source_trial_split_rows"],
                    threshold_label,
                ),
            },
        },
        "null_model": {
            "summary_rows": _filter_rows_by_threshold(payload["null_model"]["summary_rows"], threshold_label),
            "subject_rows": _filter_rows_by_threshold(payload["null_model"]["subject_rows"], threshold_label),
            "subject_repeat_rows": _filter_rows_by_threshold(payload["null_model"]["subject_repeat_rows"], threshold_label),
            "unit_rows": _filter_rows_by_threshold(payload["null_model"]["unit_rows"], threshold_label),
        },
        "holdout": {
            "summary_rows": _filter_rows_by_threshold(payload["holdout"]["summary_rows"], threshold_label),
            "eligible_group_rows": _filter_rows_by_threshold(payload["holdout"]["eligible_group_rows"], threshold_label),
            "fold_rows": _filter_rows_by_threshold(payload["holdout"]["fold_rows"], threshold_label),
        },
        "cross_condition": {
            "summary_rows": _filter_rows_by_threshold(payload["cross_condition"]["summary_rows"], threshold_label),
            "pair_rows": _filter_rows_by_threshold(payload["cross_condition"]["pair_rows"], threshold_label),
        },
    }


def build_validation_payload(
    *,
    args: argparse.Namespace,
    validation_settings: dict[str, Any],
    validation_config_path: Path,
    cfg: dict[str, Any],
    merged_df: pd.DataFrame,
    trialwise_units: list[AnalysisUnit],
    concatenated_units: list[AnalysisUnit],
    local_vaf: dict[str, Any],
    null_model: dict[str, Any],
    holdout: dict[str, Any],
    cross_condition: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the top-level JSON payload for one validity run."""
    selected_trial_frame = merged_df.drop_duplicates(subset=["subject", "velocity", "trial_num"]).copy()
    if "analysis_selected_group" in selected_trial_frame.columns:
        selected_trial_frame = selected_trial_frame.loc[selected_trial_frame["analysis_selected_group"].fillna(False)].copy()

    eligible_holdout_rows = [
        row for row in holdout["eligible_group_rows"] if bool(row["eligible_for_holdout"])
    ]
    eligible_holdout_group_keys = {
        (str(row["subject"]), str(row["velocity"]), str(row["step_class"]))
        for row in eligible_holdout_rows
    }
    return {
        "config_path": str(args.config),
        "validation_config_path": str(validation_config_path),
        "out_dir": str(validation_settings["out_dir"]),
        "thresholds": [float(value) for value in validation_settings["thresholds"]],
        "validation_settings": {
            "local_vaf_floor": float(validation_settings["local_vaf_floor"]),
            "variance_epsilon": float(validation_settings["variance_epsilon"]),
            "null_methods": [str(value) for value in validation_settings["null_methods"]],
            "null_repeats": int(validation_settings["null_repeats"]),
            "holdout_min_trials": int(validation_settings["holdout_min_trials"]),
            "null_progress_every": int(validation_settings["null_progress_every"]),
            "holdout_progress_every": int(validation_settings["holdout_progress_every"]),
            "seed": int(validation_settings["seed"]),
        },
        "input": {
            "emg_parquet_path": cfg["input"]["emg_parquet_path"],
            "event_xlsm_path": cfg["input"]["event_xlsm_path"],
            "max_components_to_try": int(
                cfg.get("feature_extractor", {}).get("nmf", {}).get("max_components_to_try", 0) or 0
            ),
        },
        "data_summary": {
            "merged_rows": int(len(merged_df)),
            "selected_trial_count": int(len(selected_trial_frame)),
            "selected_subject_count": int(selected_trial_frame["subject"].astype(str).nunique()),
            "selected_step_trial_count": int(selected_trial_frame["analysis_is_step"].fillna(False).sum()),
            "selected_nonstep_trial_count": int(selected_trial_frame["analysis_is_nonstep"].fillna(False).sum()),
            "trialwise_unit_count": int(len(trialwise_units)),
            "concatenated_unit_count": int(len(concatenated_units)),
            "holdout_eligible_group_count": int(len(eligible_holdout_group_keys)),
            "holdout_eligible_subject_count": int(len({str(row["subject"]) for row in eligible_holdout_rows})),
        },
        "local_vaf": local_vaf,
        "null_model": null_model,
        "holdout": holdout,
        "cross_condition": cross_condition,
    }


def _write_summary(out_dir: Path, payload: dict[str, Any]) -> Path:
    return _write_json(out_dir / "summary.json", payload)


def _write_threshold_summaries(out_dir: Path, payload: dict[str, Any]) -> list[Path]:
    written_paths: list[Path] = []
    for threshold in payload["thresholds"]:
        threshold_payload = _build_threshold_payload(payload, float(threshold))
        threshold_slug = f"vaf_{int(round(float(threshold) * 100)):02d}"
        written_paths.append(_write_json(out_dir / "by_threshold" / threshold_slug / "summary.json", threshold_payload))
    return written_paths


def _write_checksums(out_dir: Path, paths: list[Path]) -> Path:
    checksum_path = out_dir / "checksums.md5"
    checksum_path.write_text("\n".join(_checksum_lines(out_dir, paths)) + "\n", encoding="utf-8")
    return checksum_path


def _render_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows_"
    frame = pd.DataFrame(rows)
    frame = frame.loc[:, columns].fillna("n/a")
    rendered_rows = [columns, ["---"] * len(columns)]
    for record in frame.to_dict(orient="records"):
        rendered_rows.append([str(record[column]) for column in columns])
    return "\n".join("| " + " | ".join(row) + " |" for row in rendered_rows)


def _print_payload_summary(payload: dict[str, Any]) -> None:
    _print_section("Data Summary")
    for key, value in payload["data_summary"].items():
        print(f"{key}: {value}")

    _print_section("Local VAF Summary")
    local_rows = payload["local_vaf"]["trialwise_summary"] + payload["local_vaf"]["concatenated"]["subject_muscle_channel_summary"] + payload["local_vaf"]["concatenated"]["source_trial_split_summary"]
    print(
        _render_table(
            local_rows,
            [
                "mode",
                "threshold_label",
                "summary_layer",
                "analysis_unit_count",
                "muscle_pass_rate_75",
                "all_muscles_pass_rate_75",
                "min_local_vaf",
                "median_local_vaf",
                "selected_rank_mean",
            ],
        )
    )

    _print_section("Null Summary")
    print(
        _render_table(
            payload["null_model"]["summary_rows"],
            [
                "mode",
                "threshold_label",
                "null_method",
                "subject_count",
                "repeat_count",
                "compression_advantage_median",
                "local_advantage_median",
            ],
        )
    )

    _print_section("Hold-out Summary")
    print(
        _render_table(
            payload["holdout"]["summary_rows"],
            [
                "threshold_label",
                "eligible_group_count",
                "skipped_group_count",
                "fold_count",
                "selected_rank_mean",
                "within_test_global_vaf_mean",
                "within_test_local_pass_rate_75_mean",
            ],
        )
    )

    _print_section("Cross-condition Summary")
    print(
        _render_table(
            payload["cross_condition"]["summary_rows"],
            [
                "threshold_label",
                "direction",
                "pair_count",
                "within_test_global_vaf_mean",
                "cross_test_global_vaf_mean",
                "cross_within_delta_mean",
                "cross_within_ratio_mean",
            ],
        )
    )


def main() -> None:
    args = parse_args()
    raw_validation_config = _load_validation_config(args.validation_config)
    validation_settings = _resolve_validation_settings(args, raw_validation_config)

    cfg = load_pipeline_config(args.config)
    cfg.setdefault("runtime", {})["seed"] = int(validation_settings["seed"])
    cfg.setdefault("feature_extractor", {}).setdefault("nmf", {})["random_state"] = int(validation_settings["seed"])
    merged_df, trial_records = _load_trial_records(cfg)
    muscle_names = [name for name in cfg["muscles"]["names"] if name in merged_df.columns]

    selected_trial_frame = merged_df.drop_duplicates(subset=["subject", "velocity", "trial_num"]).copy()
    if "analysis_selected_group" in selected_trial_frame.columns:
        selected_trial_frame = selected_trial_frame.loc[selected_trial_frame["analysis_selected_group"].fillna(False)].copy()
    holdout_eligible_group_count = _count_holdout_eligible_groups(
        trial_records,
        holdout_min_trials=int(validation_settings["holdout_min_trials"]),
    )

    print("=" * 72)
    print("VAF Threshold Validity")
    print("=" * 72)
    print(f"Config: {args.config}")
    print(f"Validation config: {args.validation_config}")
    print(f"Selected subjects: {int(selected_trial_frame['subject'].astype(str).nunique())}")
    print(f"Selected trials: {int(len(selected_trial_frame))}")
    print(f"Step trials: {int(selected_trial_frame['analysis_is_step'].fillna(False).sum())}")
    print(f"Nonstep trials: {int(selected_trial_frame['analysis_is_nonstep'].fillna(False).sum())}")
    print(f"Hold-out eligible groups: {holdout_eligible_group_count}")
    print(f"Thresholds: {[ _format_threshold(value) for value in validation_settings['thresholds'] ]}")
    print(f"Null methods: {validation_settings['null_methods']}")
    print(f"Null repeats: {validation_settings['null_repeats']}")
    print(f"Null progress every: {validation_settings['null_progress_every']}")
    print(f"Hold-out progress every: {validation_settings['holdout_progress_every']}")
    print(f"Seed: {validation_settings['seed']}")
    print(f"Artifact dir: {validation_settings['out_dir']}")

    if args.dry_run:
        print("\nDry run complete. Input loading and eligibility checks succeeded.")
        return

    trialwise_units = _prepare_trialwise_units(trial_records, cfg, muscle_names)
    concatenated_units = _prepare_concatenated_units(trial_records, cfg, muscle_names)

    _print_section("Observed local VAF")
    local_vaf = evaluate_local_vaf(
        trialwise_units,
        concatenated_units,
        thresholds=validation_settings["thresholds"],
        muscle_names=muscle_names,
        local_vaf_floor=validation_settings["local_vaf_floor"],
        variance_epsilon=validation_settings["variance_epsilon"],
    )

    _print_section("Null model")
    null_model = evaluate_null_model(
        {"trialwise": trialwise_units, "concatenated": concatenated_units},
        local_vaf,
        thresholds=validation_settings["thresholds"],
        muscle_names=muscle_names,
        local_vaf_floor=validation_settings["local_vaf_floor"],
        variance_epsilon=validation_settings["variance_epsilon"],
        null_methods=validation_settings["null_methods"],
        null_repeats=validation_settings["null_repeats"],
        base_cfg=cfg,
        seed=validation_settings["seed"],
        progress_every=validation_settings["null_progress_every"],
    )

    _print_section("Hold-out and cross-condition reconstruction")
    holdout, cross_condition = evaluate_holdout_and_cross_condition(
        concatenated_units,
        thresholds=validation_settings["thresholds"],
        base_cfg=cfg,
        muscle_names=muscle_names,
        local_vaf_floor=validation_settings["local_vaf_floor"],
        variance_epsilon=validation_settings["variance_epsilon"],
        holdout_min_trials=validation_settings["holdout_min_trials"],
        progress_every=validation_settings["holdout_progress_every"],
    )

    payload = build_validation_payload(
        args=args,
        validation_settings=validation_settings,
        validation_config_path=args.validation_config,
        cfg=cfg,
        merged_df=merged_df,
        trialwise_units=trialwise_units,
        concatenated_units=concatenated_units,
        local_vaf=local_vaf,
        null_model=null_model,
        holdout=holdout,
        cross_condition=cross_condition,
    )
    out_dir = Path(validation_settings["out_dir"])
    summary_path = _write_summary(out_dir, payload)
    threshold_paths = _write_threshold_summaries(out_dir, payload)
    checksum_path = _write_checksums(out_dir, [summary_path, *threshold_paths])

    _print_payload_summary(payload)

    print("\nArtifacts")
    print("---------")
    print(f"summary.json: {summary_path}")
    for threshold_path in threshold_paths:
        print(f"threshold summary: {threshold_path}")
    print(f"checksums.md5: {checksum_path}")


if __name__ == "__main__":
    main()
