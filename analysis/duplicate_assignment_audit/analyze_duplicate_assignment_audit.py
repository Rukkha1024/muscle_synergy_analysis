"""Audit trial-level duplicate cluster assignments.

This script reconstructs paper-like and production clustering states,
measures duplicate assignment frequency and reassignment cost, and
writes reproducible outputs under `results/duplicate_assignment_audit/`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.emg_pipeline import build_trial_records, load_emg_table, load_event_metadata, load_pipeline_config, merge_event_metadata
from src.synergy_stats.clustering import (
    SubjectFeatureResult,
    _cluster_centroids,
    _duplicate_trials,
    _enforce_unique_trial_labels,
    _fit_kmeans,
    _inertia_from_labels,
    _stack_weight_vectors,
    _subject_hmax,
)
from src.synergy_stats.nmf import extract_trial_features


CHECKED_IN_PAPER_KMEANS_RESTARTS = 10
CHECKED_IN_PAPER_GAP_REF_N = 5
CHECKED_IN_PAPER_GAP_REF_RESTARTS = 3

PAPER_STATE = "state1_paper_like_unconstrained"
PROD_PRE_STATE = "state2_production_pre_forced"
PROD_POST_STATE = "state3_production_post_forced"
RAW_LABEL_SPACE = "raw_group_label"
CANONICAL_LABEL_SPACE = "canonical_label"


@dataclass
class SelectedStateRows:
    """Component-level rows for one selected pipeline state."""

    component_rows: list[dict[str, Any]]
    per_unit_rows: list[dict[str, Any]]
    pair_rows: list[dict[str, Any]]
    cluster_rows: list[dict[str, Any]]
    overall_rows: list[dict[str, Any]]


@dataclass
class ProductionKResult:
    """Per-K production clustering audit payload."""

    group_id: str
    k: int
    algorithm_used: str
    sample_map: list[dict[str, Any]]
    vectors: np.ndarray
    raw_labels: np.ndarray
    post_labels: np.ndarray
    raw_centroids: np.ndarray
    post_centroids: np.ndarray
    raw_model_inertia: float
    raw_inertia: float
    post_inertia: float
    raw_point_sq_sum: float
    post_point_sq_sum_raw_centroids: float
    raw_point_sum: float
    post_point_sum_raw_centroids: float
    raw_duplicates: list[tuple[Any, Any, Any]]
    post_duplicates: list[tuple[Any, Any, Any]]
    raw_duplicate_count: int
    post_duplicate_count: int
    reassigned_count: int
    reassignment_rows: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the audit entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "configs" / "global_config.yaml")
    parser.add_argument("--run-dir", type=Path, default=REPO_ROOT / "outputs" / "runs" / "default_run")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=REPO_ROOT / "results" / "duplicate_assignment_audit",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--paper-kmeans-restarts",
        type=int,
        default=CHECKED_IN_PAPER_KMEANS_RESTARTS,
        help="Gap-statistic observed-data repeats. Defaults match the checked-in compare_Cheung report.",
    )
    parser.add_argument(
        "--paper-gap-ref-n",
        type=int,
        default=CHECKED_IN_PAPER_GAP_REF_N,
        help="Number of reference datasets for the paper-like audit. Defaults match the checked-in compare_Cheung report.",
    )
    parser.add_argument(
        "--paper-gap-ref-restarts",
        type=int,
        default=CHECKED_IN_PAPER_GAP_REF_RESTARTS,
        help="K-means repeats per reference dataset. Defaults match the checked-in compare_Cheung report.",
    )
    return parser.parse_args()


def _json_text(value: Any) -> str:
    """Return a stable JSON string for CSV/Markdown exports."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _fmt_num(value: Any, digits: int = 3) -> str:
    """Format floats with fixed precision for the Markdown summary."""
    if value is None:
        return "n/a"
    try:
        if isinstance(value, float) and np.isnan(value):
            return "n/a"
    except Exception:
        pass
    return f"{float(value):.{digits}f}"


def _fmt_fraction(numerator: int, denominator: int) -> str:
    """Format a count fraction plus decimal rate."""
    rate = 0.0 if denominator == 0 else numerator / denominator
    return f"{numerator}/{denominator} = {rate:.3f}"


def _write_csv(frame: pl.DataFrame, path: Path) -> None:
    """Write a Polars frame with UTF-8 BOM for spreadsheet-friendly review."""
    path.parent.mkdir(parents=True, exist_ok=True)
    csv_text = frame.write_csv()
    path.write_text(csv_text, encoding="utf-8-sig")


def _write_text(path: Path, text: str) -> None:
    """Write UTF-8 BOM text outputs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def _load_compare_module() -> Any:
    """Load the compare_Cheung analysis script via importlib."""
    module_path = REPO_ROOT / "analysis" / "compare_Cheung,2021" / "analyze_compare_cheung_synergy_analysis.py"
    module_name = "compare_cheung_audit_module"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load compare_Cheung module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_paper_args(args: argparse.Namespace) -> argparse.Namespace:
    """Build the subset of compare_Cheung CLI args needed for its config helper."""
    return argparse.Namespace(
        config=args.config,
        run_dir=args.run_dir,
        report_path=REPO_ROOT / "analysis" / "compare_Cheung,2021" / "report.md",
        figure_dir=REPO_ROOT / "analysis" / "compare_Cheung,2021" / "figures",
        seed=int(args.seed),
        dry_run=False,
        nmf_restarts=20,
        nmf_max_rank=16,
        nmf_max_iter=500,
        r2_threshold=0.80,
        cluster_k_max=20,
        kmeans_restarts=int(args.paper_kmeans_restarts),
        gap_ref_n=int(args.paper_gap_ref_n),
        gap_ref_restarts=int(args.paper_gap_ref_restarts),
    )


def _load_trial_inputs(
    cfg: dict[str, Any],
    compare_mod: Any,
    paper_cfg: Any,
    run_dir: Path,
) -> tuple[dict[str, Any], dict[tuple[str, float, int], dict[str, Any]], dict[tuple[str, float, int], Any]]:
    """Load baseline manifest, merged input, and validated selected trial slices."""
    baseline = compare_mod.load_baseline_inputs(run_dir, cfg)
    manifest_lookup = compare_mod.select_trials_from_manifest(baseline["manifest_df"], paper_cfg)
    compare_mod._PIPELINE_CFG = cfg
    emg_df = load_emg_table(str(cfg["input"]["emg_parquet_path"]))
    compare_mod.validate_final_parquet_schema(emg_df, paper_cfg)
    event_df = load_event_metadata(str(cfg["input"]["event_xlsm_path"]), cfg)
    merged = merge_event_metadata(emg_df, event_df)
    trial_lookup = compare_mod.build_trial_matrix_dict(merged, baseline["manifest_df"], paper_cfg)
    return baseline, manifest_lookup, trial_lookup


def _build_production_feature_rows(
    trial_lookup: dict[tuple[str, float, int], Any],
    manifest_lookup: dict[tuple[str, float, int], dict[str, Any]],
    cfg: dict[str, Any],
) -> list[SubjectFeatureResult]:
    """Recreate production trial-level feature rows without touching pipeline outputs."""
    muscle_names = list(cfg["muscles"]["names"])
    feature_rows: list[SubjectFeatureResult] = []
    for key in sorted(trial_lookup):
        trial = trial_lookup[key]
        bundle = extract_trial_features(trial.frame[muscle_names].to_numpy(dtype="float32"), cfg)
        bundle.meta.update(
            {
                "subject": key[0],
                "velocity": key[1],
                "trial_num": key[2],
                **trial.metadata,
                "group_id": manifest_lookup[key]["group_id"],
                "trial_id": manifest_lookup[key]["trial_id"],
            }
        )
        feature_rows.append(
            SubjectFeatureResult(
                subject=key[0],
                velocity=key[1],
                trial_num=key[2],
                bundle=bundle,
            )
        )
    return feature_rows


def _group_feature_rows(
    feature_rows: list[SubjectFeatureResult],
) -> dict[str, list[SubjectFeatureResult]]:
    """Split production feature rows into global step and nonstep groups."""
    grouped = {"global_step": [], "global_nonstep": []}
    for item in feature_rows:
        is_step = bool(item.bundle.meta.get("analysis_is_step", False))
        is_nonstep = bool(item.bundle.meta.get("analysis_is_nonstep", False))
        if is_step == is_nonstep:
            raise ValueError(
                "Selected production feature rows must belong to exactly one of step or nonstep."
            )
        grouped["global_step" if is_step else "global_nonstep"].append(item)
    return grouped


def _make_unit_id(subject: str, velocity: Any, trial_num: Any, trial_id: str) -> str:
    """Build a stable unit identifier."""
    return f"{subject}|{velocity}|{trial_num}|{trial_id}"


def _pairwise_cosine(left: np.ndarray, right: np.ndarray) -> float:
    """Compute cosine similarity safely."""
    left = np.asarray(left, dtype=np.float64).reshape(-1)
    right = np.asarray(right, dtype=np.float64).reshape(-1)
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= 0:
        return 0.0
    return float(np.dot(left, right) / denom)


def _build_component_rows(
    *,
    pipeline_name: str,
    state_name: str,
    label_space: str,
    group_id: str,
    k: int,
    sample_map: list[dict[str, Any]],
    labels: np.ndarray,
    vectors: np.ndarray,
    centroids: np.ndarray,
    canonical_map: dict[int, str] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Create component-level rows for one clustering state."""
    rows: list[dict[str, Any]] = []
    extra_fields = extra_fields or {}
    dist_sq = ((vectors[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2, dtype=np.float64)
    for index, sample in enumerate(sample_map):
        raw_cluster_id = int(labels[index])
        cluster_label = canonical_map.get(raw_cluster_id, f"{raw_cluster_id}") if canonical_map else f"{raw_cluster_id}"
        rows.append(
            {
                "pipeline_name": pipeline_name,
                "state_name": state_name,
                "label_space": label_space,
                "group_id": group_id,
                "subject": str(sample["subject"]),
                "velocity": float(sample["velocity"]),
                "trial_num": int(sample["trial_num"]),
                "trial_id": str(sample["trial_id"]),
                "unit_id": _make_unit_id(sample["subject"], sample["velocity"], sample["trial_num"], sample["trial_id"]),
                "component_index": int(sample["component_index"]),
                "cluster_id": raw_cluster_id,
                "cluster_label": str(cluster_label),
                "k": int(k),
                "vector": np.asarray(vectors[index], dtype=np.float64),
                "distance_sq_to_assigned_centroid": float(dist_sq[index, raw_cluster_id]),
                "distance_to_assigned_centroid": float(math.sqrt(max(0.0, dist_sq[index, raw_cluster_id]))),
                **extra_fields,
            }
        )
    return rows


def _summarize_component_rows(component_rows: list[dict[str, Any]]) -> SelectedStateRows:
    """Compute per-unit, per-cluster, pair, and overall duplicate metrics."""
    by_unit: dict[tuple[str, str, str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in component_rows:
        by_unit[
            (
                row["pipeline_name"],
                row["state_name"],
                row["label_space"],
                row["group_id"],
                int(row["k"]),
                row["unit_id"],
            )
        ].append(row)

    per_unit_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    cluster_dupe_counts: Counter[tuple[str, str, str, str, int, str]] = Counter()
    unit_counts: Counter[tuple[str, str, str, str, int]] = Counter()
    units_with_cluster_present: Counter[tuple[str, str, str, str, int, str]] = Counter()

    for unit_key, rows in by_unit.items():
        rows = sorted(rows, key=lambda item: item["component_index"])
        pipeline_name, state_name, label_space, group_id, k_value, unit_id = unit_key
        unit_counts[(pipeline_name, state_name, label_space, group_id, k_value)] += 1
        label_counts = Counter(row["cluster_label"] for row in rows)
        for cluster_label, count in label_counts.items():
            if count >= 1:
                units_with_cluster_present[(pipeline_name, state_name, label_space, group_id, k_value, cluster_label)] += 1
            if count >= 2:
                cluster_dupe_counts[(pipeline_name, state_name, label_space, group_id, k_value, cluster_label)] += 1

        duplicate_pairs = 0
        duplicate_pair_similarity: list[float] = []
        duplicate_pair_scalars: list[float] = []
        nonduplicate_pair_similarity: list[float] = []
        nonduplicate_pair_scalars: list[float] = []
        duplicate_pair_descriptions: list[dict[str, Any]] = []
        within_pairs = math.comb(len(rows), 2) if len(rows) >= 2 else 0

        for left_index in range(len(rows)):
            for right_index in range(left_index + 1, len(rows)):
                left_row = rows[left_index]
                right_row = rows[right_index]
                scalar_product = float(
                    np.dot(left_row["vector"].astype(np.float64), right_row["vector"].astype(np.float64))
                )
                cosine_similarity = _pairwise_cosine(left_row["vector"], right_row["vector"])
                pair_type = "duplicate" if left_row["cluster_label"] == right_row["cluster_label"] else "non_duplicate"
                if pair_type == "duplicate":
                    duplicate_pairs += 1
                    duplicate_pair_similarity.append(cosine_similarity)
                    duplicate_pair_scalars.append(scalar_product)
                    duplicate_pair_descriptions.append(
                        {
                            "components": [int(left_row["component_index"]), int(right_row["component_index"])],
                            "cluster_label": left_row["cluster_label"],
                            "cosine_similarity": round(cosine_similarity, 6),
                            "scalar_product": round(scalar_product, 6),
                        }
                    )
                else:
                    nonduplicate_pair_similarity.append(cosine_similarity)
                    nonduplicate_pair_scalars.append(scalar_product)
                pair_rows.append(
                    {
                        "pipeline_name": pipeline_name,
                        "state_name": state_name,
                        "label_space": label_space,
                        "group_id": group_id,
                        "k": int(k_value),
                        "subject": rows[0]["subject"],
                        "velocity": rows[0]["velocity"],
                        "trial_num": rows[0]["trial_num"],
                        "trial_id": rows[0]["trial_id"],
                        "unit_id": unit_id,
                        "component_index_i": int(left_row["component_index"]),
                        "component_index_j": int(right_row["component_index"]),
                        "cluster_label_i": left_row["cluster_label"],
                        "cluster_label_j": right_row["cluster_label"],
                        "pair_type": pair_type,
                        "cosine_similarity": float(cosine_similarity),
                        "scalar_product": float(scalar_product),
                        "distance_i": float(left_row["distance_to_assigned_centroid"]),
                        "distance_j": float(right_row["distance_to_assigned_centroid"]),
                    }
                )

        excess_duplicate_count = int(sum(max(count - 1, 0) for count in label_counts.values()))
        per_unit_rows.append(
            {
                "pipeline_name": pipeline_name,
                "state_name": state_name,
                "label_space": label_space,
                "group_id": group_id,
                "k": int(k_value),
                "subject": rows[0]["subject"],
                "velocity": rows[0]["velocity"],
                "trial_num": rows[0]["trial_num"],
                "trial_id": rows[0]["trial_id"],
                "unit_id": unit_id,
                "nsyn": int(len(rows)),
                "has_duplicate": bool(excess_duplicate_count > 0),
                "excess_duplicate_count": int(excess_duplicate_count),
                "duplicate_pair_count": int(duplicate_pairs),
                "within_unit_pair_count": int(within_pairs),
                "nsyn_gt_k": bool(len(rows) > k_value),
                "cluster_counts_json": _json_text(dict(sorted(label_counts.items()))),
                "component_indices_json": _json_text([int(row["component_index"]) for row in rows]),
                "cluster_labels_json": _json_text([row["cluster_label"] for row in rows]),
                "centroid_distances_json": _json_text(
                    {
                        int(row["component_index"]): round(float(row["distance_to_assigned_centroid"]), 6)
                        for row in rows
                    }
                ),
                "duplicate_pairs_json": _json_text(duplicate_pair_descriptions),
                "duplicate_pair_mean_cosine": float(np.mean(duplicate_pair_similarity)) if duplicate_pair_similarity else np.nan,
                "duplicate_pair_mean_scalar": float(np.mean(duplicate_pair_scalars)) if duplicate_pair_scalars else np.nan,
                "nonduplicate_pair_mean_cosine": float(np.mean(nonduplicate_pair_similarity)) if nonduplicate_pair_similarity else np.nan,
                "nonduplicate_pair_mean_scalar": float(np.mean(nonduplicate_pair_scalars)) if nonduplicate_pair_scalars else np.nan,
            }
        )

    cluster_rows: list[dict[str, Any]] = []
    cluster_keys = set(units_with_cluster_present.keys()) | set(cluster_dupe_counts.keys())
    for cluster_key in sorted(cluster_keys):
        duplicate_units = cluster_dupe_counts.get(cluster_key, 0)
        pipeline_name, state_name, label_space, group_id, k_value, cluster_label = cluster_key
        units_total = unit_counts[(pipeline_name, state_name, label_space, group_id, k_value)]
        present_units = units_with_cluster_present[cluster_key]
        cluster_rows.append(
            {
                "pipeline_name": pipeline_name,
                "state_name": state_name,
                "label_space": label_space,
                "group_id": group_id,
                "k": int(k_value),
                "cluster_label": cluster_label,
                "duplicate_incident_units": int(duplicate_units),
                "units_total": int(units_total),
                "units_with_cluster_present": int(present_units),
                "cluster_wise_duplicate_incidence": float(duplicate_units / units_total) if units_total else np.nan,
            }
        )

    overall_rows: list[dict[str, Any]] = []
    per_unit_frame = pl.DataFrame(per_unit_rows) if per_unit_rows else pl.DataFrame()
    pair_frame = pl.DataFrame(pair_rows) if pair_rows else pl.DataFrame()
    if not per_unit_frame.is_empty():
        group_keys = ["pipeline_name", "state_name", "label_space", "group_id", "k"]
        group_summary = (
            per_unit_frame.group_by(group_keys)
            .agg(
                pl.len().alias("units_total"),
                pl.col("has_duplicate").cast(pl.Int64).sum().alias("duplicate_units"),
                pl.col("excess_duplicate_count").sum().alias("excess_duplicates_total"),
                pl.col("nsyn").sum().alias("synergies_total"),
                pl.col("nsyn_gt_k").cast(pl.Int64).sum().alias("units_nsyn_gt_k"),
                pl.col("duplicate_pair_count").sum().alias("duplicate_pairs_total"),
                pl.col("within_unit_pair_count").sum().alias("within_unit_pairs_total"),
            )
            .sort(group_keys)
        )
        for row in group_summary.to_dicts():
            row["scope"] = "group"
            row["duplicate_unit_rate"] = float(row["duplicate_units"] / row["units_total"]) if row["units_total"] else np.nan
            row["excess_duplicate_ratio"] = float(row["excess_duplicates_total"] / row["synergies_total"]) if row["synergies_total"] else np.nan
            row["duplicate_pair_rate"] = float(row["duplicate_pairs_total"] / row["within_unit_pairs_total"]) if row["within_unit_pairs_total"] else np.nan
            row["units_nsyn_gt_k_rate"] = float(row["units_nsyn_gt_k"] / row["units_total"]) if row["units_total"] else np.nan
            overall_rows.append(row)

        overall_summary = (
            per_unit_frame.group_by(["pipeline_name", "state_name", "label_space"])
            .agg(
                pl.len().alias("units_total"),
                pl.col("has_duplicate").cast(pl.Int64).sum().alias("duplicate_units"),
                pl.col("excess_duplicate_count").sum().alias("excess_duplicates_total"),
                pl.col("nsyn").sum().alias("synergies_total"),
                pl.col("nsyn_gt_k").cast(pl.Int64).sum().alias("units_nsyn_gt_k"),
                pl.col("duplicate_pair_count").sum().alias("duplicate_pairs_total"),
                pl.col("within_unit_pair_count").sum().alias("within_unit_pairs_total"),
            )
            .sort(["pipeline_name", "state_name", "label_space"])
        )
        k_lookup = (
            per_unit_frame.group_by(["pipeline_name", "state_name", "label_space"])
            .agg(pl.col("k").n_unique().alias("k_unique"), pl.col("k").first().alias("k_first"))
            .to_dicts()
        )
        k_map = {
            (row["pipeline_name"], row["state_name"], row["label_space"]): row
            for row in k_lookup
        }
        for row in overall_summary.to_dicts():
            key = (row["pipeline_name"], row["state_name"], row["label_space"])
            k_info = k_map[key]
            row["scope"] = "overall"
            row["group_id"] = "__overall__"
            row["k"] = int(k_info["k_first"]) if k_info["k_unique"] == 1 else -1
            row["duplicate_unit_rate"] = float(row["duplicate_units"] / row["units_total"]) if row["units_total"] else np.nan
            row["excess_duplicate_ratio"] = float(row["excess_duplicates_total"] / row["synergies_total"]) if row["synergies_total"] else np.nan
            row["duplicate_pair_rate"] = float(row["duplicate_pairs_total"] / row["within_unit_pairs_total"]) if row["within_unit_pairs_total"] else np.nan
            row["units_nsyn_gt_k_rate"] = float(row["units_nsyn_gt_k"] / row["units_total"]) if row["units_total"] else np.nan
            overall_rows.append(row)

    return SelectedStateRows(
        component_rows=component_rows,
        per_unit_rows=per_unit_rows,
        pair_rows=pair_rows,
        cluster_rows=cluster_rows,
        overall_rows=overall_rows,
    )


def _paper_canonical_maps(
    compare_mod: Any,
    step_common: Any,
    nonstep_common: Any,
    match_summary: dict[str, Any],
) -> dict[str, dict[int, str]]:
    """Build a derived canonical label space from actual step-vs-nonstep matching."""
    step_map: dict[int, str] = {}
    nonstep_map: dict[int, str] = {}
    matched_step: set[int] = set()
    matched_nonstep: set[int] = set()
    for match_index, row in enumerate(match_summary["matched_pairs"]):
        step_cluster = int(step_common.cluster_ids[int(row["step_idx"])])
        nonstep_cluster = int(nonstep_common.cluster_ids[int(row["nonstep_idx"])])
        label = f"match_{match_index:02d}"
        step_map[step_cluster] = label
        nonstep_map[nonstep_cluster] = label
        matched_step.add(step_cluster)
        matched_nonstep.add(nonstep_cluster)
    for cluster_id in step_common.cluster_ids:
        cluster_id = int(cluster_id)
        if cluster_id not in matched_step:
            step_map[cluster_id] = f"step_common_unmatched_{cluster_id}"
    for cluster_id in nonstep_common.cluster_ids:
        cluster_id = int(cluster_id)
        if cluster_id not in matched_nonstep:
            nonstep_map[cluster_id] = f"nonstep_common_unmatched_{cluster_id}"
    return {"global_step": step_map, "global_nonstep": nonstep_map}


def _audit_paper_like(
    compare_mod: Any,
    baseline: dict[str, Any],
    trial_lookup: dict[tuple[str, float, int], Any],
    manifest_lookup: dict[tuple[str, float, int], dict[str, Any]],
    cfg: dict[str, Any],
    paper_cfg: Any,
    seed: int,
) -> dict[str, Any]:
    """Run the paper-like unconstrained audit using the actual compare_Cheung helpers."""
    trial_results = compare_mod._collect_trial_results(trial_lookup, manifest_lookup, paper_cfg, seed)
    vector_df = compare_mod._build_vector_rows(trial_results)

    k_sensitivity_rows: list[dict[str, Any]] = []
    selected_component_rows: list[dict[str, Any]] = []
    selected_member_frames: dict[str, pd.DataFrame] = {}
    cluster_results: dict[str, dict[str, Any]] = {}
    common_summaries: dict[str, Any] = {}

    for offset, group_id in enumerate(["global_step", "global_nonstep"]):
        group_vectors = vector_df.loc[vector_df["group_id"] == group_id].reset_index(drop=True)
        vectors = np.stack(group_vectors["vector"].to_list(), axis=0)
        k_values = list(range(2, min(int(paper_cfg.cluster_k_max), vectors.shape[0]) + 1))
        gap_result = compare_mod.compute_gap_statistic(vectors, k_values, paper_cfg, seed + offset)
        selected_k = int(gap_result["selected_k"])
        selected_member_rows: list[dict[str, Any]] = []
        for row, label in zip(group_vectors.itertuples(index=False), gap_result["labels"].tolist()):
            selected_member_rows.append(
                {
                    "group_id": row.group_id,
                    "step_class": row.step_class,
                    "subject": row.subject,
                    "velocity": float(row.velocity),
                    "trial_num": int(row.trial_num),
                    "trial_id": row.trial_id,
                    "component_index": int(row.component_index),
                    "cluster_id": int(label),
                    "vector": row.vector,
                }
            )
        selected_member_frame = pd.DataFrame(selected_member_rows)
        selected_member_frames[group_id] = selected_member_frame
        common_summary = compare_mod.identify_common_clusters(selected_member_frame, baseline["manifest_df"], paper_cfg)
        common_summaries[group_id] = common_summary

        selected_component_rows.extend(
            _build_component_rows(
                pipeline_name="paper_like",
                state_name=PAPER_STATE,
                label_space=RAW_LABEL_SPACE,
                group_id=group_id,
                k=selected_k,
                sample_map=[
                    {
                        "subject": row.subject,
                        "velocity": float(row.velocity),
                        "trial_num": int(row.trial_num),
                        "trial_id": row.trial_id,
                        "component_index": int(row.component_index),
                    }
                    for row in group_vectors.itertuples(index=False)
                ],
                labels=np.asarray(gap_result["labels"], dtype=np.int32),
                vectors=vectors,
                centroids=np.asarray(gap_result["centroids"], dtype=np.float64),
            )
        )

        for k in k_values:
            labels, centroids, objective = compare_mod._best_plain_kmeans_solution(
                vectors,
                k,
                paper_cfg.kmeans_restarts,
                seed + offset + (k * 1000),
            )
            per_k_rows = _build_component_rows(
                pipeline_name="paper_like",
                state_name=PAPER_STATE,
                label_space=RAW_LABEL_SPACE,
                group_id=group_id,
                k=k,
                sample_map=[
                    {
                        "subject": row.subject,
                        "velocity": float(row.velocity),
                        "trial_num": int(row.trial_num),
                        "trial_id": row.trial_id,
                        "component_index": int(row.component_index),
                    }
                    for row in group_vectors.itertuples(index=False)
                ],
                labels=np.asarray(labels, dtype=np.int32),
                vectors=vectors,
                centroids=np.asarray(centroids, dtype=np.float64),
            )
            summary = _summarize_component_rows(per_k_rows)
            overall_row = next(
                row
                for row in summary.overall_rows
                if row["scope"] == "group"
                and row["pipeline_name"] == "paper_like"
                and row["group_id"] == group_id
                and row["label_space"] == RAW_LABEL_SPACE
                and int(row["k"]) == int(k)
            )
            overall_row.update(
                {
                    "gap_statistic": float(gap_result["gap_by_k"][k]),
                    "gap_sd": float(gap_result["gap_sd_by_k"][k]),
                    "objective_sse": float(objective),
                    "point_to_centroid_sq_sum": float(
                        sum(row["distance_sq_to_assigned_centroid"] for row in per_k_rows)
                    ),
                    "point_to_centroid_sum": float(
                        sum(row["distance_to_assigned_centroid"] for row in per_k_rows)
                    ),
                    "selected_k_flag": bool(k == selected_k),
                    "selection_rule": "gap_statistic_first_k_ge_gap_next_minus_sd",
                }
            )
            k_sensitivity_rows.append(overall_row)

        cluster_results[group_id] = {
            "selected_k": selected_k,
            "gap_result": gap_result,
            "member_frame": selected_member_frame,
        }

    match_summary = compare_mod.match_cluster_centroids(
        common_summaries["global_step"].centroids,
        common_summaries["global_nonstep"].centroids,
        paper_cfg,
    )
    canonical_maps = _paper_canonical_maps(
        compare_mod,
        common_summaries["global_step"],
        common_summaries["global_nonstep"],
        match_summary,
    )

    canonical_component_rows: list[dict[str, Any]] = []
    for row in selected_component_rows:
        canonical_component_rows.append(
            {
                **row,
                "label_space": CANONICAL_LABEL_SPACE,
                "cluster_label": canonical_maps.get(row["group_id"], {}).get(
                    int(row["cluster_id"]),
                    f"{row['group_id']}_raw_{int(row['cluster_id'])}",
                ),
            }
        )

    raw_state = _summarize_component_rows(selected_component_rows)
    canonical_state = _summarize_component_rows(canonical_component_rows)

    return {
        "trial_results": trial_results,
        "vector_df": vector_df,
        "selected_component_rows": selected_component_rows,
        "raw_state": raw_state,
        "canonical_state": canonical_state,
        "k_sensitivity_rows": k_sensitivity_rows,
        "cluster_results": cluster_results,
        "common_summaries": common_summaries,
        "match_summary": match_summary,
    }


def _production_reassignment_rows(
    *,
    group_id: str,
    k: int,
    sample_map: list[dict[str, Any]],
    vectors: np.ndarray,
    raw_labels: np.ndarray,
    post_labels: np.ndarray,
    raw_centroids: np.ndarray,
    post_centroids: np.ndarray,
) -> list[dict[str, Any]]:
    """Build per-component reassignment rows for the selected production K."""
    raw_sq = ((vectors[:, None, :] - raw_centroids[None, :, :]) ** 2).sum(axis=2, dtype=np.float64)
    post_sq = ((vectors[:, None, :] - post_centroids[None, :, :]) ** 2).sum(axis=2, dtype=np.float64)
    rows: list[dict[str, Any]] = []
    for idx, sample in enumerate(sample_map):
        raw_cluster = int(raw_labels[idx])
        post_cluster = int(post_labels[idx])
        rows.append(
            {
                "row_type": "component",
                "group_id": group_id,
                "k": int(k),
                "subject": str(sample["subject"]),
                "velocity": float(sample["velocity"]),
                "trial_num": int(sample["trial_num"]),
                "trial_id": str(sample["trial_id"]),
                "component_index": int(sample["component_index"]),
                "from_cluster_id": raw_cluster,
                "to_cluster_id": post_cluster,
                "was_reassigned": bool(raw_cluster != post_cluster),
                "cost_sq_before_raw_centroid": float(raw_sq[idx, raw_cluster]),
                "cost_sq_after_raw_centroid": float(raw_sq[idx, post_cluster]),
                "cost_sq_delta_raw_centroid": float(raw_sq[idx, post_cluster] - raw_sq[idx, raw_cluster]),
                "cost_before_raw_centroid": float(math.sqrt(max(0.0, raw_sq[idx, raw_cluster]))),
                "cost_after_raw_centroid": float(math.sqrt(max(0.0, raw_sq[idx, post_cluster]))),
                "cost_delta_raw_centroid": float(
                    math.sqrt(max(0.0, raw_sq[idx, post_cluster])) - math.sqrt(max(0.0, raw_sq[idx, raw_cluster]))
                ),
                "cost_sq_before_post_centroid": float(post_sq[idx, post_cluster] if raw_cluster == post_cluster else post_sq[idx, raw_cluster]),
                "cost_sq_after_post_centroid": float(post_sq[idx, post_cluster]),
            }
        )
    return rows


def _audit_production(
    grouped_rows: dict[str, list[SubjectFeatureResult]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Audit production clustering before and after uniqueness enforcement."""
    clustering_cfg = dict(cfg["synergy_clustering"])
    k_sensitivity_rows: list[dict[str, Any]] = []
    selected_pre_rows: list[dict[str, Any]] = []
    selected_post_rows: list[dict[str, Any]] = []
    reassignment_rows: list[dict[str, Any]] = []
    selected_results: dict[str, ProductionKResult] = {}

    for group_id, feature_rows in grouped_rows.items():
        vectors, sample_map = _stack_weight_vectors(feature_rows, group_id)
        subject_hmax = _subject_hmax(feature_rows)
        k_min = max(2, subject_hmax)
        k_max = min(int(clustering_cfg.get("max_clusters", subject_hmax)), int(vectors.shape[0]))
        if k_max < k_min:
            raise ValueError(f"Invalid production K range for {group_id}: [{k_min}, {k_max}]")

        best_result: ProductionKResult | None = None
        selected_result: ProductionKResult | None = None
        for k in range(k_min, k_max + 1):
            raw_labels, raw_model_inertia, algorithm_used = _fit_kmeans(vectors, k, clustering_cfg)
            raw_labels = np.asarray(raw_labels, dtype=np.int32)
            raw_centroids = _cluster_centroids(vectors, raw_labels, k)
            raw_inertia = float(_inertia_from_labels(vectors, raw_labels))
            raw_sq = ((vectors[:, None, :] - raw_centroids[None, :, :]) ** 2).sum(axis=2, dtype=np.float64)
            raw_duplicates = _duplicate_trials(sample_map, raw_labels)
            post_labels = (
                _enforce_unique_trial_labels(vectors, sample_map, raw_labels, k)
                if clustering_cfg.get("disallow_within_trial_duplicate_assignment", True)
                else raw_labels.copy()
            )
            post_labels = np.asarray(post_labels, dtype=np.int32)
            post_centroids = _cluster_centroids(vectors, post_labels, k)
            post_inertia = float(_inertia_from_labels(vectors, post_labels))
            post_duplicates = _duplicate_trials(sample_map, post_labels)
            post_sq_raw_centroids = float(sum(raw_sq[index, int(post_labels[index])] for index in range(len(post_labels))))
            post_sum_raw_centroids = float(
                sum(math.sqrt(max(0.0, raw_sq[index, int(post_labels[index])])) for index in range(len(post_labels)))
            )
            result = ProductionKResult(
                group_id=group_id,
                k=int(k),
                algorithm_used=str(algorithm_used),
                sample_map=sample_map,
                vectors=vectors,
                raw_labels=raw_labels,
                post_labels=post_labels,
                raw_centroids=raw_centroids,
                post_centroids=post_centroids,
                raw_model_inertia=float(raw_model_inertia),
                raw_inertia=float(raw_inertia),
                post_inertia=float(post_inertia),
                raw_point_sq_sum=float(sum(raw_sq[index, int(raw_labels[index])] for index in range(len(raw_labels)))),
                post_point_sq_sum_raw_centroids=post_sq_raw_centroids,
                raw_point_sum=float(
                    sum(math.sqrt(max(0.0, raw_sq[index, int(raw_labels[index])])) for index in range(len(raw_labels)))
                ),
                post_point_sum_raw_centroids=post_sum_raw_centroids,
                raw_duplicates=raw_duplicates,
                post_duplicates=post_duplicates,
                raw_duplicate_count=int(len(raw_duplicates)),
                post_duplicate_count=int(len(post_duplicates)),
                reassigned_count=int(np.sum(raw_labels != post_labels)),
                reassignment_rows=[],
            )
            if best_result is None or result.post_duplicate_count < best_result.post_duplicate_count:
                best_result = result
            if selected_result is None and result.post_duplicate_count == 0:
                selected_result = result

            pre_rows = _build_component_rows(
                pipeline_name="production",
                state_name=PROD_PRE_STATE,
                label_space=RAW_LABEL_SPACE,
                group_id=group_id,
                k=k,
                sample_map=sample_map,
                labels=raw_labels,
                vectors=vectors,
                centroids=raw_centroids,
            )
            pre_summary = _summarize_component_rows(pre_rows)
            pre_overall = next(
                row
                for row in pre_summary.overall_rows
                if row["scope"] == "group"
                and row["group_id"] == group_id
                and int(row["k"]) == int(k)
            )
            pre_overall.update(
                {
                    "gap_statistic": np.nan,
                    "gap_sd": np.nan,
                    "objective_sse": float(raw_inertia),
                    "point_to_centroid_sq_sum": float(result.raw_point_sq_sum),
                    "point_to_centroid_sum": float(result.raw_point_sum),
                    "selected_k_flag": False,
                    "selection_rule": "production_first_zero_duplicate_post_force",
                    "algorithm_used": algorithm_used,
                }
            )
            k_sensitivity_rows.append(pre_overall)

            post_rows = _build_component_rows(
                pipeline_name="production",
                state_name=PROD_POST_STATE,
                label_space=RAW_LABEL_SPACE,
                group_id=group_id,
                k=k,
                sample_map=sample_map,
                labels=post_labels,
                vectors=vectors,
                centroids=post_centroids,
            )
            post_summary = _summarize_component_rows(post_rows)
            post_overall = next(
                row
                for row in post_summary.overall_rows
                if row["scope"] == "group"
                and row["group_id"] == group_id
                and int(row["k"]) == int(k)
            )
            post_overall.update(
                {
                    "gap_statistic": np.nan,
                    "gap_sd": np.nan,
                    "objective_sse": float(post_inertia),
                    "point_to_centroid_sq_sum": float(result.post_point_sq_sum_raw_centroids),
                    "point_to_centroid_sum": float(result.post_point_sum_raw_centroids),
                    "selected_k_flag": False,
                    "selection_rule": "production_first_zero_duplicate_post_force",
                    "algorithm_used": algorithm_used,
                }
            )
            k_sensitivity_rows.append(post_overall)

        if selected_result is None:
            if best_result is None:
                raise RuntimeError(f"Production clustering returned no candidates for {group_id}.")
            selected_result = best_result
        selected_result.reassignment_rows = _production_reassignment_rows(
            group_id=group_id,
            k=selected_result.k,
            sample_map=selected_result.sample_map,
            vectors=selected_result.vectors,
            raw_labels=selected_result.raw_labels,
            post_labels=selected_result.post_labels,
            raw_centroids=selected_result.raw_centroids,
            post_centroids=selected_result.post_centroids,
        )
        selected_results[group_id] = selected_result

        for row in k_sensitivity_rows:
            if (
                row["pipeline_name"] == "production"
                and row["group_id"] == group_id
                and int(row["k"]) == int(selected_result.k)
            ):
                row["selected_k_flag"] = True

        selected_pre_rows.extend(
            _build_component_rows(
                pipeline_name="production",
                state_name=PROD_PRE_STATE,
                label_space=RAW_LABEL_SPACE,
                group_id=group_id,
                k=selected_result.k,
                sample_map=selected_result.sample_map,
                labels=selected_result.raw_labels,
                vectors=selected_result.vectors,
                centroids=selected_result.raw_centroids,
            )
        )
        selected_post_rows.extend(
            _build_component_rows(
                pipeline_name="production",
                state_name=PROD_POST_STATE,
                label_space=RAW_LABEL_SPACE,
                group_id=group_id,
                k=selected_result.k,
                sample_map=selected_result.sample_map,
                labels=selected_result.post_labels,
                vectors=selected_result.vectors,
                centroids=selected_result.post_centroids,
            )
        )
        reassignment_rows.extend(selected_result.reassignment_rows)

    pre_state = _summarize_component_rows(selected_pre_rows)
    post_state = _summarize_component_rows(selected_post_rows)
    return {
        "selected_results": selected_results,
        "raw_state": pre_state,
        "post_state": post_state,
        "k_sensitivity_rows": k_sensitivity_rows,
        "reassignment_rows": reassignment_rows,
    }


def _worst_case_units(
    per_unit_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Select the most severe duplicate units from the paper-like state."""
    duplicate_units = [
        row
        for row in per_unit_rows
        if row["pipeline_name"] == "paper_like"
        and row["state_name"] == PAPER_STATE
        and row["label_space"] == RAW_LABEL_SPACE
        and bool(row["has_duplicate"])
    ]
    unit_pair_lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        if (
            row["pipeline_name"] == "paper_like"
            and row["state_name"] == PAPER_STATE
            and row["label_space"] == RAW_LABEL_SPACE
            and row["pair_type"] == "duplicate"
        ):
            unit_pair_lookup[row["unit_id"]].append(row)
    duplicate_units.sort(
        key=lambda row: (
            -int(row["excess_duplicate_count"]),
            -int(row["duplicate_pair_count"]),
            -float(row["duplicate_pair_mean_cosine"] if not math.isnan(row["duplicate_pair_mean_cosine"]) else -1.0),
            row["trial_id"],
        )
    )
    selected: list[dict[str, Any]] = []
    for row in duplicate_units[:limit]:
        pair_rows_for_unit = unit_pair_lookup.get(row["unit_id"], [])
        selected.append(
            {
                "subject_id": row["subject"],
                "group_id": row["group_id"],
                "trial_id": row["trial_id"],
                "velocity": row["velocity"],
                "trial_num": row["trial_num"],
                "Nsyn": row["nsyn"],
                "chosen_K": row["k"],
                "synergy_indexes": row["component_indices_json"],
                "assigned_clusters": row["cluster_labels_json"],
                "centroid_distances": row["centroid_distances_json"],
                "duplicate_pair_similarity": _json_text(
                    [
                        {
                            "pair": [int(item["component_index_i"]), int(item["component_index_j"])],
                            "cluster": item["cluster_label_i"],
                            "cosine_similarity": round(float(item["cosine_similarity"]), 6),
                            "scalar_product": round(float(item["scalar_product"]), 6),
                        }
                        for item in pair_rows_for_unit
                    ]
                ),
            }
        )
    return selected


def _similarity_summary(pair_rows: list[dict[str, Any]], pipeline_name: str, state_name: str, label_space: str) -> dict[str, Any]:
    """Summarize duplicate and non-duplicate similarity distributions."""
    duplicate_values = [
        row["cosine_similarity"]
        for row in pair_rows
        if row["pipeline_name"] == pipeline_name
        and row["state_name"] == state_name
        and row["label_space"] == label_space
        and row["pair_type"] == "duplicate"
    ]
    nonduplicate_values = [
        row["cosine_similarity"]
        for row in pair_rows
        if row["pipeline_name"] == pipeline_name
        and row["state_name"] == state_name
        and row["label_space"] == label_space
        and row["pair_type"] == "non_duplicate"
    ]
    duplicate_scalars = [
        row["scalar_product"]
        for row in pair_rows
        if row["pipeline_name"] == pipeline_name
        and row["state_name"] == state_name
        and row["label_space"] == label_space
        and row["pair_type"] == "duplicate"
    ]
    nonduplicate_scalars = [
        row["scalar_product"]
        for row in pair_rows
        if row["pipeline_name"] == pipeline_name
        and row["state_name"] == state_name
        and row["label_space"] == label_space
        and row["pair_type"] == "non_duplicate"
    ]
    return {
        "duplicate_pair_count": len(duplicate_values),
        "nonduplicate_pair_count": len(nonduplicate_values),
        "duplicate_cosine_mean": float(np.mean(duplicate_values)) if duplicate_values else np.nan,
        "duplicate_cosine_median": float(np.median(duplicate_values)) if duplicate_values else np.nan,
        "nonduplicate_cosine_mean": float(np.mean(nonduplicate_values)) if nonduplicate_values else np.nan,
        "nonduplicate_cosine_median": float(np.median(nonduplicate_values)) if nonduplicate_values else np.nan,
        "duplicate_scalar_mean": float(np.mean(duplicate_scalars)) if duplicate_scalars else np.nan,
        "nonduplicate_scalar_mean": float(np.mean(nonduplicate_scalars)) if nonduplicate_scalars else np.nan,
    }


def _collect_overall_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine overall rows from multiple states into one Polars frame."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.overall_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_per_unit_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine per-unit rows from multiple states into one Polars frame."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.per_unit_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_pair_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine pair rows from multiple states into one Polars frame."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.pair_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_cluster_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine cluster incidence rows from multiple states into one Polars frame."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.cluster_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_k_sensitivity_frame(*row_lists: list[dict[str, Any]]) -> pl.DataFrame:
    """Combine per-K summary rows into one Polars frame."""
    rows: list[dict[str, Any]] = []
    for row_list in row_lists:
        rows.extend(row_list)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _reassignment_summary_rows(
    selected_results: dict[str, ProductionKResult],
    post_state: SelectedStateRows,
) -> list[dict[str, Any]]:
    """Build summary and transition rows for reassignment_stats.csv."""
    rows: list[dict[str, Any]] = []
    total_synergies = sum(len(result.sample_map) for result in selected_results.values())
    total_reassigned = sum(result.reassigned_count for result in selected_results.values())
    total_pre_sq = sum(result.raw_point_sq_sum for result in selected_results.values())
    total_post_sq = sum(result.post_point_sq_sum_raw_centroids for result in selected_results.values())
    total_pre_sum = sum(result.raw_point_sum for result in selected_results.values())
    total_post_sum = sum(result.post_point_sum_raw_centroids for result in selected_results.values())
    total_raw_inertia = sum(result.raw_inertia for result in selected_results.values())
    total_post_inertia = sum(result.post_inertia for result in selected_results.values())
    overall_post = next(
        row
        for row in post_state.overall_rows
        if row["scope"] == "overall"
        and row["pipeline_name"] == "production"
        and row["state_name"] == PROD_POST_STATE
    )
    rows.append(
        {
            "row_type": "summary_overall",
            "group_id": "__overall__",
            "k": -1,
            "reassigned_synergy_count": int(total_reassigned),
            "synergies_total": int(total_synergies),
            "reassigned_synergy_ratio": float(total_reassigned / total_synergies) if total_synergies else np.nan,
            "assignment_cost_sq_before": float(total_pre_sq),
            "assignment_cost_sq_after": float(total_post_sq),
            "assignment_cost_sq_delta": float(total_post_sq - total_pre_sq),
            "assignment_cost_before": float(total_pre_sum),
            "assignment_cost_after": float(total_post_sum),
            "assignment_cost_delta": float(total_post_sum - total_pre_sum),
            "inertia_before": float(total_raw_inertia),
            "inertia_after": float(total_post_inertia),
            "inertia_delta": float(total_post_inertia - total_raw_inertia),
            "remaining_duplicate_units": int(overall_post["duplicate_units"]),
        }
    )
    transition_counter: Counter[tuple[str, int, int, int]] = Counter()
    for group_id, result in selected_results.items():
        rows.append(
            {
                "row_type": "summary_group",
                "group_id": group_id,
                "k": int(result.k),
                "reassigned_synergy_count": int(result.reassigned_count),
                "synergies_total": int(len(result.sample_map)),
                "reassigned_synergy_ratio": float(result.reassigned_count / len(result.sample_map)) if result.sample_map else np.nan,
                "assignment_cost_sq_before": float(result.raw_point_sq_sum),
                "assignment_cost_sq_after": float(result.post_point_sq_sum_raw_centroids),
                "assignment_cost_sq_delta": float(result.post_point_sq_sum_raw_centroids - result.raw_point_sq_sum),
                "assignment_cost_before": float(result.raw_point_sum),
                "assignment_cost_after": float(result.post_point_sum_raw_centroids),
                "assignment_cost_delta": float(result.post_point_sum_raw_centroids - result.raw_point_sum),
                "inertia_before": float(result.raw_inertia),
                "inertia_after": float(result.post_inertia),
                "inertia_delta": float(result.post_inertia - result.raw_inertia),
                "remaining_duplicate_units": int(result.post_duplicate_count),
            }
        )
        for detail in result.reassignment_rows:
            transition_counter[(group_id, int(result.k), int(detail["from_cluster_id"]), int(detail["to_cluster_id"]))] += 1
    for (group_id, k, from_cluster, to_cluster), count in sorted(transition_counter.items()):
        rows.append(
            {
                "row_type": "transition",
                "group_id": group_id,
                "k": int(k),
                "from_cluster_id": int(from_cluster),
                "to_cluster_id": int(to_cluster),
                "transition_count": int(count),
            }
        )
    return rows


def _plot_gap_sensitivity(k_frame: pl.DataFrame, output_dir: Path) -> None:
    """Plot K versus gap statistic for the paper-like path."""
    subset = k_frame.filter(pl.col("pipeline_name") == "paper_like")
    if subset.is_empty():
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    for group_id, group_frame in subset.group_by("group_id", maintain_order=True):
        group_id = group_id[0] if isinstance(group_id, tuple) else group_id
        rows = group_frame.sort("k").to_dicts()
        ax.plot(
            [row["k"] for row in rows],
            [row["gap_statistic"] for row in rows],
            marker="o",
            label=str(group_id),
        )
    ax.set_xlabel("K")
    ax.set_ylabel("Gap statistic")
    ax.set_title("Paper-like K vs gap statistic")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "k_vs_gap_statistic.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_duplicate_sensitivity(k_frame: pl.DataFrame, output_dir: Path, column: str, filename: str, title: str) -> None:
    """Plot K sensitivity for one duplicate metric."""
    subset = k_frame.filter(pl.col("pipeline_name") == "paper_like")
    if subset.is_empty():
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    for group_id, group_frame in subset.group_by("group_id", maintain_order=True):
        group_id = group_id[0] if isinstance(group_id, tuple) else group_id
        rows = group_frame.sort("k").to_dicts()
        ax.plot(
            [row["k"] for row in rows],
            [row[column] for row in rows],
            marker="o",
            label=str(group_id),
        )
    ax.set_xlabel("K")
    ax.set_ylabel(column)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_group_duplicate_bars(overall_frame: pl.DataFrame, output_dir: Path) -> None:
    """Plot group-specific duplicate-unit rates across selected states."""
    subset = overall_frame.filter(pl.col("scope") == "group")
    if subset.is_empty():
        return
    subset = subset.filter(
        (pl.col("pipeline_name") == "paper_like")
        | ((pl.col("pipeline_name") == "production") & (pl.col("state_name") == PROD_PRE_STATE))
        | ((pl.col("pipeline_name") == "production") & (pl.col("state_name") == PROD_POST_STATE))
    )
    if subset.is_empty():
        return
    rows = subset.select(["pipeline_name", "state_name", "group_id", "duplicate_unit_rate"]).to_dicts()
    labels = [f"{row['group_id']}\n{row['pipeline_name']}\n{row['state_name']}" for row in rows]
    values = [row["duplicate_unit_rate"] for row in rows]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(np.arange(len(rows)), values, color="#3A86FF")
    ax.set_xticks(np.arange(len(rows)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("duplicate_unit_rate")
    ax.set_title("Group-specific duplicate unit rate")
    fig.tight_layout()
    fig.savefig(output_dir / "group_duplicate_unit_rate.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_similarity(pair_frame: pl.DataFrame, output_dir: Path) -> None:
    """Plot duplicate versus non-duplicate similarity distributions."""
    subset = pair_frame.filter(
        (pl.col("pipeline_name") == "paper_like")
        & (pl.col("state_name") == PAPER_STATE)
        & (pl.col("label_space") == RAW_LABEL_SPACE)
    )
    if subset.is_empty():
        return
    dup_values = subset.filter(pl.col("pair_type") == "duplicate")["cosine_similarity"].to_list()
    non_values = subset.filter(pl.col("pair_type") == "non_duplicate")["cosine_similarity"].to_list()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot([dup_values, non_values], tick_labels=["duplicate", "non-duplicate"], showmeans=True)
    ax.set_ylabel("cosine similarity")
    ax.set_title("Within-unit pair similarity")
    fig.tight_layout()
    fig.savefig(output_dir / "duplicate_vs_nonduplicate_similarity.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _summary_lookup(
    overall_frame: pl.DataFrame,
    *,
    pipeline_name: str,
    state_name: str,
    label_space: str,
    scope: str,
    group_id: str,
) -> dict[str, Any]:
    """Fetch one overall-metric row as a Python dict."""
    rows = overall_frame.filter(
        (pl.col("pipeline_name") == pipeline_name)
        & (pl.col("state_name") == state_name)
        & (pl.col("label_space") == label_space)
        & (pl.col("scope") == scope)
        & (pl.col("group_id") == group_id)
    ).to_dicts()
    if not rows:
        raise KeyError(f"Missing overall row for {pipeline_name}/{state_name}/{label_space}/{scope}/{group_id}")
    return rows[0]


def _paper_subject_variation(per_unit_frame: pl.DataFrame) -> list[dict[str, Any]]:
    """Compute per-subject duplicate-unit rates for the paper-like raw state."""
    subset = per_unit_frame.filter(
        (pl.col("pipeline_name") == "paper_like")
        & (pl.col("state_name") == PAPER_STATE)
        & (pl.col("label_space") == RAW_LABEL_SPACE)
    )
    if subset.is_empty():
        return []
    summary = (
        subset.group_by("subject")
        .agg(
            pl.len().alias("units_total"),
            pl.col("has_duplicate").cast(pl.Int64).sum().alias("duplicate_units"),
        )
        .with_columns((pl.col("duplicate_units") / pl.col("units_total")).alias("duplicate_unit_rate"))
        .sort(["duplicate_unit_rate", "duplicate_units", "subject"], descending=[True, True, False])
    )
    return summary.head(5).to_dicts()


def _build_summary_markdown(
    *,
    args: argparse.Namespace,
    cfg: dict[str, Any],
    paper_cfg: Any,
    overall_frame: pl.DataFrame,
    per_unit_frame: pl.DataFrame,
    paper_results: dict[str, Any],
    production_results: dict[str, Any],
    worst_cases: list[dict[str, Any]],
    similarity_summary: dict[str, Any],
    reassignment_summary_rows: list[dict[str, Any]],
) -> str:
    """Render the top-level Markdown summary requested by the user."""
    paper_overall = _summary_lookup(
        overall_frame,
        pipeline_name="paper_like",
        state_name=PAPER_STATE,
        label_space=RAW_LABEL_SPACE,
        scope="overall",
        group_id="__overall__",
    )
    prod_pre_overall = _summary_lookup(
        overall_frame,
        pipeline_name="production",
        state_name=PROD_PRE_STATE,
        label_space=RAW_LABEL_SPACE,
        scope="overall",
        group_id="__overall__",
    )
    prod_post_overall = _summary_lookup(
        overall_frame,
        pipeline_name="production",
        state_name=PROD_POST_STATE,
        label_space=RAW_LABEL_SPACE,
        scope="overall",
        group_id="__overall__",
    )
    paper_step = _summary_lookup(
        overall_frame,
        pipeline_name="paper_like",
        state_name=PAPER_STATE,
        label_space=RAW_LABEL_SPACE,
        scope="group",
        group_id="global_step",
    )
    paper_nonstep = _summary_lookup(
        overall_frame,
        pipeline_name="paper_like",
        state_name=PAPER_STATE,
        label_space=RAW_LABEL_SPACE,
        scope="group",
        group_id="global_nonstep",
    )
    prod_step_post = _summary_lookup(
        overall_frame,
        pipeline_name="production",
        state_name=PROD_POST_STATE,
        label_space=RAW_LABEL_SPACE,
        scope="group",
        group_id="global_step",
    )
    prod_nonstep_post = _summary_lookup(
        overall_frame,
        pipeline_name="production",
        state_name=PROD_POST_STATE,
        label_space=RAW_LABEL_SPACE,
        scope="group",
        group_id="global_nonstep",
    )
    overall_reassign = next(row for row in reassignment_summary_rows if row["row_type"] == "summary_overall")
    match_summary = paper_results["match_summary"]
    canonical_overall = _summary_lookup(
        overall_frame,
        pipeline_name="paper_like",
        state_name=PAPER_STATE,
        label_space=CANONICAL_LABEL_SPACE,
        scope="overall",
        group_id="__overall__",
    )
    subject_variation_rows = _paper_subject_variation(per_unit_frame)

    issue_flag_lines = [
        f"- Paper-like audit used the checked-in `compare_Cheung` runtime overrides `--kmeans-restarts {args.paper_kmeans_restarts} --gap-ref-n {args.paper_gap_ref_n} --gap-ref-restarts {args.paper_gap_ref_restarts}` because the committed `report.md` was generated that way, while the code defaults remain `1000/500/100`.",
        "- Production baseline clustering has no downstream canonical relabeling stage for member assignments; duplicate checks beyond raw group labels are therefore only meaningful in the paper-like path where step-vs-nonstep centroid matching exists.",
    ]

    worst_case_table = ""
    if worst_cases:
        worst_case_table += "| subject_id | group | trial_id | Nsyn | chosen K | synergy_indexes | assigned cluster | centroid distance | pairwise similarity |\n"
        worst_case_table += "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        for row in worst_cases:
            worst_case_table += (
                f"| {row['subject_id']} | {row['group_id']} | {row['trial_id']} | {row['Nsyn']} | {row['chosen_K']} | "
                f"`{row['synergy_indexes']}` | `{row['assigned_clusters']}` | `{row['centroid_distances']}` | "
                f"`{row['duplicate_pair_similarity']}` |\n"
            )

    recommendation = "A"
    if paper_overall["duplicate_unit_rate"] > 0.250 or paper_overall["duplicate_pair_rate"] > 0.100:
        recommendation = "C"
    elif paper_overall["duplicate_unit_rate"] > 0.050 or paper_overall["duplicate_pair_rate"] > 0.020:
        recommendation = "B"

    recommendation_text = {
        "A": "A: 현재 paper-like pipeline 유지 가능",
        "B": "B: 결과는 쓸 수 있으나 duplicate caveat를 반드시 명시해야 함",
        "C": "C: forced reassignment 또는 constrained clustering 없이 biological 해석을 하면 위험함",
    }[recommendation]

    interpretation_lines = []
    if paper_overall["duplicate_unit_rate"] <= 0.050 and paper_overall["duplicate_pair_rate"] <= 0.020:
        interpretation_lines.append(
            "같은 unit 내부 duplicate는 실제로 드물어 biological interpretation을 크게 흔드는 수준은 아니었다."
        )
    elif paper_overall["duplicate_unit_rate"] <= 0.250 and paper_overall["duplicate_pair_rate"] <= 0.100:
        interpretation_lines.append(
            "duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다."
        )
    else:
        interpretation_lines.append(
            "duplicate가 충분히 자주 발생해, unconstrained cluster label을 biological module identity로 직접 해석하면 위험하다."
        )
    if similarity_summary["duplicate_cosine_mean"] > similarity_summary["nonduplicate_cosine_mean"] + 0.100:
        interpretation_lines.append(
            "다만 duplicate pair의 평균 cosine similarity가 non-duplicate보다 뚜렷하게 높아, 일부 중복은 거의 같은 synergy가 같은 cluster로 들어간 사례에 가깝다."
        )
    else:
        interpretation_lines.append(
            "duplicate pair similarity가 non-duplicate와 크게 벌어지지 않아, NMF상 꽤 다른 synergy가 같은 cluster로 묶인 사례도 무시하기 어렵다."
        )

    issue_flag_text = "\n".join(issue_flag_lines)
    worst_case_section = worst_case_table or "No duplicate units were found in the selected paper-like state.\n"
    subject_variation_text = (
        "\n".join(
            f"- {row['subject']}: {int(row['duplicate_units'])}/{int(row['units_total'])} = {float(row['duplicate_unit_rate']):.3f}"
            for row in subject_variation_rows
        )
        if subject_variation_rows
        else "- No subject-level variation rows were available."
    )

    return f"""# Duplicate Assignment Audit Summary

## 1) Executive summary

Ambiguities / missing:
{issue_flag_text}

실제 duplicate는 paper-like unconstrained 경로에서 존재한다. `duplicate_unit_rate`는 {_fmt_fraction(int(paper_overall['duplicate_units']), int(paper_overall['units_total']))}, `excess_duplicate_ratio`는 `{int(paper_overall['excess_duplicates_total'])}/{int(paper_overall['synergies_total'])} = {paper_overall['excess_duplicate_ratio']:.3f}`이고, `duplicate_pair_rate`는 `{int(paper_overall['duplicate_pairs_total'])}/{int(paper_overall['within_unit_pairs_total'])} = {paper_overall['duplicate_pair_rate']:.3f}`이다. 이 수치는 `analysis/compare_Cheung,2021`의 실제 현재 코드 경로를 audit script에서 재실행해 얻었고, checked-in report와 같은 override runtime을 사용했다.

forced reassignment는 repo에 실제로 존재한다. production 경로에서는 `src/synergy_stats/clustering.py::cluster_feature_group()`가 `_fit_kmeans()` 직후 `_enforce_unique_trial_labels()`를 호출하고, 그 뒤 `_duplicate_trials()`로 duplicate를 다시 검사한다. post-force 기준 전체 duplicate는 {_fmt_fraction(int(prod_post_overall['duplicate_units']), int(prod_post_overall['units_total']))}였고, pre-force 기준 전체 duplicate는 {_fmt_fraction(int(prod_pre_overall['duplicate_units']), int(prod_pre_overall['units_total']))}였다.

이 문제가 downstream interpretation을 얼마나 흔드는지는 “paper-like unconstrained label을 biological module identity처럼 바로 읽느냐”에 달려 있다. {interpretation_lines[0]} {interpretation_lines[1]}

## 2) Actual pipeline map

Production path:
- `main.py` -> `scripts/emg/03_extract_synergy_nmf.py::run()` -> `src/synergy_stats/nmf.py::extract_trial_features()` -> `src/synergy_stats/nmf.py::_normalize_components()` -> `scripts/emg/04_cluster_synergies.py::run()` -> `src/synergy_stats/clustering.py::cluster_feature_group()` -> `src/synergy_stats/clustering.py::_fit_kmeans()` -> `src/synergy_stats/clustering.py::_enforce_unique_trial_labels()` -> `src/synergy_stats/clustering.py::_duplicate_trials()` -> `src/synergy_stats/artifacts.py::export_results()`.
- NMF unit: trial.
- Clustering input vector: L2-normalized `W_muscle[:, component_index]`.
- K rule: `k_min = max(2, subject_hmax)` to `k_max = min(max_clusters, n_components)`, then return the first post-force zero-duplicate `K`.
- K-means details: `configs/synergy_stats_config.yaml` sets `algorithm=cuml_kmeans` with sklearn fallback, `repeats=25`, `random_state=42`, `max_iter=300`, and squared-Euclidean inertia.
- Config source: `configs/synergy_stats_config.yaml`.

Paper-like path:
- `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py::main()` -> `_collect_trial_results()` -> `run_paper_nmf_for_trial()` -> `_build_vector_rows()` -> `_run_group_clustering()` -> `compute_gap_statistic()` -> `identify_common_clusters()` -> `match_cluster_centroids()`.
- NMF unit: trial.
- Clustering input vector: row-wise L2-normalized `normalized_structures`.
- K rule: plain k-means for `K = 2..20`, then gap statistic chooses the first `K` satisfying `Gap(k) >= Gap(k+1) - s(k+1)`.
- K-means details: `_plain_kmeans_once()` uses `sklearn.cluster.KMeans(..., n_init=1, algorithm="lloyd")` after `_sample_initial_centroids()` chooses centroid seeds from observed vectors, and `_best_plain_kmeans_solution()` repeats that `{paper_cfg.kmeans_restarts}` times per `K` in this audit run.
- This path has no active within-trial duplicate reassignment.

Label-space distinction:
- Raw group-specific label: actual `cluster_id` emitted by k-means inside each group.
- Downstream canonical label: derived only for the paper-like path from actual step-vs-nonstep Hungarian matching. Stored member labels are not rewritten by repo code; the audit computed this canonical space explicitly to test whether duplicate counts change after matching.
- Result: paper-like raw and canonical duplicate counts were `{int(paper_overall['duplicate_units'])}/{int(paper_overall['units_total'])}` vs `{int(canonical_overall['duplicate_units'])}/{int(canonical_overall['units_total'])}` at the unit level, so downstream matching did not remove duplicates.

## 3) Final K and sensitivity

Paper-like selected K from the checked-in runtime:
- `global_step`: `{int(paper_results['cluster_results']['global_step']['selected_k'])}`
- `global_nonstep`: `{int(paper_results['cluster_results']['global_nonstep']['selected_k'])}`

Production selected K from the actual uniqueness-enforced search:
- `global_step`: `{int(production_results['selected_results']['global_step'].k)}`
- `global_nonstep`: `{int(production_results['selected_results']['global_nonstep'].k)}`

Across the paper-like `K` range, gap statistic, `duplicate_unit_rate`, and `excess_duplicate_ratio` are stored in `k_sensitivity.csv` and plotted in `plots/`. The main practical question was whether slightly larger `K` values sharply reduce duplicate frequency, and this audit records the full observed curve rather than just the final selected `K`.

## 4) Main numbers

Paper-like overall:
- `duplicate_unit_rate`: {_fmt_fraction(int(paper_overall['duplicate_units']), int(paper_overall['units_total']))}
- `excess_duplicate_ratio`: `{int(paper_overall['excess_duplicates_total'])}/{int(paper_overall['synergies_total'])} = {paper_overall['excess_duplicate_ratio']:.3f}`
- `duplicate_pair_rate`: `{int(paper_overall['duplicate_pairs_total'])}/{int(paper_overall['within_unit_pairs_total'])} = {paper_overall['duplicate_pair_rate']:.3f}`
- `units_with_Nsyn_gt_K`: `{int(paper_overall['units_nsyn_gt_k'])}/{int(paper_overall['units_total'])} = {paper_overall['units_nsyn_gt_k_rate']:.3f}`
- `global_step duplicate_unit_rate`: {_fmt_fraction(int(paper_step['duplicate_units']), int(paper_step['units_total']))}
- `global_nonstep duplicate_unit_rate`: {_fmt_fraction(int(paper_nonstep['duplicate_units']), int(paper_nonstep['units_total']))}
- top subject-level duplicate_unit_rate:
{subject_variation_text}

Production selected-K overall:
- pre-force `duplicate_unit_rate`: {_fmt_fraction(int(prod_pre_overall['duplicate_units']), int(prod_pre_overall['units_total']))}
- post-force `duplicate_unit_rate`: {_fmt_fraction(int(prod_post_overall['duplicate_units']), int(prod_post_overall['units_total']))}
- post-force `units_with_Nsyn_gt_K`: `{int(prod_post_overall['units_nsyn_gt_k'])}/{int(prod_post_overall['units_total'])} = {prod_post_overall['units_nsyn_gt_k_rate']:.3f}`
- `global_step` post-force `duplicate_unit_rate`: {_fmt_fraction(int(prod_step_post['duplicate_units']), int(prod_step_post['units_total']))}
- `global_nonstep` post-force `duplicate_unit_rate`: {_fmt_fraction(int(prod_nonstep_post['duplicate_units']), int(prod_nonstep_post['units_total']))}

## 5) Forced reassignment findings

forced reassignment 유무:
- 있음. 정확한 개입 위치는 `src/synergy_stats/clustering.py::_enforce_unique_trial_labels()`.
- 호출 순서는 `cluster_feature_group()` inside `for n_clusters ...` -> `_fit_kmeans()` -> `_enforce_unique_trial_labels()` -> `_duplicate_trials()`이다.

pre/post duplicate 변화:
- pre-force overall `duplicate_unit_rate`: {_fmt_fraction(int(prod_pre_overall['duplicate_units']), int(prod_pre_overall['units_total']))}
- post-force overall `duplicate_unit_rate`: {_fmt_fraction(int(prod_post_overall['duplicate_units']), int(prod_post_overall['units_total']))}

reassignment cost 증가량:
- reassigned synergies: `{int(overall_reassign['reassigned_synergy_count'])}/{int(overall_reassign['synergies_total'])} = {overall_reassign['reassigned_synergy_ratio']:.3f}`
- fixed raw-centroid squared assignment cost delta: `{overall_reassign['assignment_cost_sq_delta']:.3f}`
- fixed raw-centroid assignment distance delta: `{overall_reassign['assignment_cost_delta']:.3f}`
- recomputed clustering inertia delta: `{overall_reassign['inertia_delta']:.3f}`

남은 예외 사례:
- post-force duplicate units: `{int(overall_reassign['remaining_duplicate_units'])}`
- `Nsyn > K` post-force units: `{int(prod_post_overall['units_nsyn_gt_k'])}`
- production post-force duplicate가 남아 있으면 `reassignment_stats.csv`의 `summary_*`와 `component` row, 그리고 `per_unit_metrics.csv`에서 바로 추적할 수 있다.

## 6) Interpretation

- 같은 unit 내부 duplicate가 드물어서 해석에 큰 영향이 없는지: {interpretation_lines[0]}
- 같은 unit 내부 duplicate가 자주 발생해서 cluster를 biological module identity처럼 읽기 어려운지: paper-like unconstrained 경로 기준 `duplicate_unit_rate={paper_overall['duplicate_unit_rate']:.3f}`, `duplicate_pair_rate={paper_overall['duplicate_pair_rate']:.3f}`이므로, 해석 강도는 이 수치와 함께 읽어야 한다.
- 문제가 특정 group/subject/K에 국한되는지: group별 값은 `global_step={paper_step['duplicate_unit_rate']:.3f}`, `global_nonstep={paper_nonstep['duplicate_unit_rate']:.3f}`이고, worst-case unit 10개는 아래 표에 정리했다.

Duplicate similarity summary:
- duplicate pair cosine mean: `{_fmt_num(similarity_summary['duplicate_cosine_mean'])}` from `{similarity_summary['duplicate_pair_count']}` pair(s)
- non-duplicate pair cosine mean: `{_fmt_num(similarity_summary['nonduplicate_cosine_mean'])}` from `{similarity_summary['nonduplicate_pair_count']}` pair(s)
- duplicate pair scalar-product mean: `{_fmt_num(similarity_summary['duplicate_scalar_mean'])}`
- non-duplicate pair scalar-product mean: `{_fmt_num(similarity_summary['nonduplicate_scalar_mean'])}`
- Because clustering vectors are already L2-normalized before clustering in both paths, cosine similarity and scalar product are numerically the same up to floating-point noise.

Worst cases:
{worst_case_section}

## 7) Recommendation

{recommendation_text}

## Reproduction

Run from repo root:

```bash
conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py
```

Q1. paper-like unconstrained pipeline에서 같은 trial/session 내 duplicate assignment는 실제로 얼마나 발생하는가?
A1. `duplicate_unit_rate`는 {_fmt_fraction(int(paper_overall['duplicate_units']), int(paper_overall['units_total']))}, `excess_duplicate_ratio`는 `{int(paper_overall['excess_duplicates_total'])}/{int(paper_overall['synergies_total'])} = {paper_overall['excess_duplicate_ratio']:.3f}`, `duplicate_pair_rate`는 `{int(paper_overall['duplicate_pairs_total'])}/{int(paper_overall['within_unit_pairs_total'])} = {paper_overall['duplicate_pair_rate']:.3f}`였다.

Q2. forced reassignment는 repo에 실제로 존재하는가? 존재하면 정확히 어디서 개입하는가?
A2. 존재한다. `src/synergy_stats/clustering.py::cluster_feature_group()`가 `_fit_kmeans()` 직후 `src/synergy_stats/clustering.py::_enforce_unique_trial_labels()`를 호출해서 같은 trial 내부 duplicate label을 줄이거나 제거하려고 개입한다.

Q3. forced reassignment는 duplicate를 없애는 대신 assignment cost를 얼마나 증가시키는가?
A3. selected production K 기준 전체 reassigned synergies는 `{int(overall_reassign['reassigned_synergy_count'])}/{int(overall_reassign['synergies_total'])} = {overall_reassign['reassigned_synergy_ratio']:.3f}`였고, fixed raw-centroid squared assignment cost는 `{overall_reassign['assignment_cost_sq_delta']:.3f}`, fixed raw-centroid distance sum은 `{overall_reassign['assignment_cost_delta']:.3f}`, recomputed inertia는 `{overall_reassign['inertia_delta']:.3f}`만큼 증가했다.

Q4. 이 duplicate 문제는 biological interpretation을 실제로 흔드는 수준인가?
A4. {interpretation_lines[0]} {interpretation_lines[1]} 따라서 최종 권고는 `{recommendation}`에 해당한다.
"""


def main() -> int:
    """Run the duplicate-assignment audit end-to-end."""
    args = parse_args()
    compare_mod = _load_compare_module()
    cfg = load_pipeline_config(str(args.config))
    paper_cfg = compare_mod._build_method_config(_make_paper_args(args), cfg)
    baseline, manifest_lookup, trial_lookup = _load_trial_inputs(cfg, compare_mod, paper_cfg, args.run_dir)

    if args.results_dir.exists():
        shutil.rmtree(args.results_dir)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = args.results_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    print(f"[M1] Loaded config: {args.config}")
    print(f"[M1] Loaded run dir: {args.run_dir}")
    print(f"[M1] Results dir: {args.results_dir}")
    print(
        "[M1] Paper-like runtime overrides: "
        f"kmeans_restarts={args.paper_kmeans_restarts}, gap_ref_n={args.paper_gap_ref_n}, "
        f"gap_ref_restarts={args.paper_gap_ref_restarts}"
    )

    production_feature_rows = _build_production_feature_rows(trial_lookup, manifest_lookup, cfg)
    grouped_production_rows = _group_feature_rows(production_feature_rows)
    print(f"[M2] Rebuilt production feature rows: {len(production_feature_rows)} trials")

    paper_results = _audit_paper_like(
        compare_mod=compare_mod,
        baseline=baseline,
        trial_lookup=trial_lookup,
        manifest_lookup=manifest_lookup,
        cfg=cfg,
        paper_cfg=paper_cfg,
        seed=int(args.seed),
    )
    print("[M3] Paper-like unconstrained audit complete")

    production_results = _audit_production(grouped_production_rows, cfg)
    print("[M4] Production pre/post reassignment audit complete")

    overall_frame = _collect_overall_frame(
        paper_results["raw_state"],
        paper_results["canonical_state"],
        production_results["raw_state"],
        production_results["post_state"],
    )
    per_unit_frame = _collect_per_unit_frame(
        paper_results["raw_state"],
        paper_results["canonical_state"],
        production_results["raw_state"],
        production_results["post_state"],
    )
    pair_frame = _collect_pair_frame(
        paper_results["raw_state"],
        paper_results["canonical_state"],
        production_results["raw_state"],
        production_results["post_state"],
    )
    cluster_frame = _collect_cluster_frame(
        paper_results["raw_state"],
        paper_results["canonical_state"],
        production_results["raw_state"],
        production_results["post_state"],
    )
    k_frame = _collect_k_sensitivity_frame(
        paper_results["k_sensitivity_rows"],
        production_results["k_sensitivity_rows"],
    ).sort(["pipeline_name", "group_id", "state_name", "k"])
    reassignment_summary_rows = _reassignment_summary_rows(
        production_results["selected_results"],
        production_results["post_state"],
    )
    reassignment_frame = pl.DataFrame(reassignment_summary_rows + production_results["reassignment_rows"])

    worst_cases = _worst_case_units(
        paper_results["raw_state"].per_unit_rows,
        paper_results["raw_state"].pair_rows,
    )
    similarity_summary = _similarity_summary(
        paper_results["raw_state"].pair_rows,
        pipeline_name="paper_like",
        state_name=PAPER_STATE,
        label_space=RAW_LABEL_SPACE,
    )

    _plot_gap_sensitivity(k_frame, plot_dir)
    _plot_duplicate_sensitivity(
        k_frame,
        plot_dir,
        column="duplicate_unit_rate",
        filename="k_vs_duplicate_unit_rate.png",
        title="Paper-like K vs duplicate unit rate",
    )
    _plot_duplicate_sensitivity(
        k_frame,
        plot_dir,
        column="excess_duplicate_ratio",
        filename="k_vs_excess_duplicate_ratio.png",
        title="Paper-like K vs excess duplicate ratio",
    )
    _plot_group_duplicate_bars(overall_frame, plot_dir)
    _plot_similarity(pair_frame, plot_dir)

    _write_csv(overall_frame.sort(["pipeline_name", "state_name", "label_space", "scope", "group_id"]), args.results_dir / "overall_metrics.csv")
    _write_csv(per_unit_frame.sort(["pipeline_name", "state_name", "label_space", "group_id", "subject", "trial_id"]), args.results_dir / "per_unit_metrics.csv")
    _write_csv(pair_frame.sort(["pipeline_name", "state_name", "label_space", "group_id", "trial_id", "component_index_i", "component_index_j"]), args.results_dir / "duplicate_pairs.csv")
    _write_csv(cluster_frame.sort(["pipeline_name", "state_name", "label_space", "group_id", "cluster_label"]), args.results_dir / "per_cluster_stats.csv")
    _write_csv(k_frame, args.results_dir / "k_sensitivity.csv")
    _write_csv(reassignment_frame, args.results_dir / "reassignment_stats.csv")

    summary_text = _build_summary_markdown(
        args=args,
        cfg=cfg,
        paper_cfg=paper_cfg,
        overall_frame=overall_frame,
        per_unit_frame=per_unit_frame,
        paper_results=paper_results,
        production_results=production_results,
        worst_cases=worst_cases,
        similarity_summary=similarity_summary,
        reassignment_summary_rows=reassignment_summary_rows,
    )
    _write_text(args.results_dir / "summary.md", summary_text)

    print(f"[M5] Wrote summary: {args.results_dir / 'summary.md'}")
    print(f"[M5] Wrote tables and plots under: {args.results_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
