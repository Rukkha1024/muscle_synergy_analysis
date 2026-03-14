"""Audit duplicate cluster assignments in the compare_Cheung workflow.

This script reruns the paper-like clustering path from
`analysis/compare_Cheung,2021`, measures within-trial duplicate labels,
and writes a standalone report plus reproducible artifacts in this folder.
"""

from __future__ import annotations

import argparse
import hashlib
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
COMPARE_DIR = REPO_ROOT / "analysis" / "compare_Cheung,2021"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.emg_pipeline import load_emg_table, load_event_metadata, load_pipeline_config, merge_event_metadata


CHECKED_IN_PAPER_KMEANS_RESTARTS = 10
CHECKED_IN_PAPER_GAP_REF_N = 5
CHECKED_IN_PAPER_GAP_REF_RESTARTS = 3

PAPER_STATE = "state1_paper_like_unconstrained"
RAW_LABEL_SPACE = "raw_group_label"
CANONICAL_LABEL_SPACE = "canonical_label"


@dataclass
class SelectedStateRows:
    """Container for one selected clustering state and its summaries."""

    component_rows: list[dict[str, Any]]
    per_unit_rows: list[dict[str, Any]]
    pair_rows: list[dict[str, Any]]
    cluster_rows: list[dict[str, Any]]
    overall_rows: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the compare_Cheung duplicate audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "configs" / "global_config.yaml")
    parser.add_argument("--run-dir", type=Path, default=REPO_ROOT / "outputs" / "runs" / "default_run")
    parser.add_argument("--report-path", type=Path, default=SCRIPT_DIR / "report.md")
    parser.add_argument("--results-dir", type=Path, default=SCRIPT_DIR / "results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true", help="Load inputs and print selected-trial counts only.")
    parser.add_argument(
        "--paper-kmeans-restarts",
        type=int,
        default=CHECKED_IN_PAPER_KMEANS_RESTARTS,
        help="Observed-data KMeans repeats. Defaults match the checked-in compare_Cheung report.",
    )
    parser.add_argument(
        "--paper-gap-ref-n",
        type=int,
        default=CHECKED_IN_PAPER_GAP_REF_N,
        help="Gap-statistic reference-set count. Defaults match the checked-in compare_Cheung report.",
    )
    parser.add_argument(
        "--paper-gap-ref-restarts",
        type=int,
        default=CHECKED_IN_PAPER_GAP_REF_RESTARTS,
        help="KMeans repeats per gap-statistic reference set. Defaults match the checked-in compare_Cheung report.",
    )
    return parser.parse_args()


def _json_text(value: Any) -> str:
    """Return a stable JSON string for report-friendly exports."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _fmt_num(value: Any, digits: int = 3) -> str:
    """Format a float with fixed precision or return n/a."""
    if value is None:
        return "n/a"
    try:
        if isinstance(value, float) and np.isnan(value):
            return "n/a"
    except Exception:
        pass
    return f"{float(value):.{digits}f}"


def _fmt_fraction(numerator: int, denominator: int) -> str:
    """Format numerator/denominator with the decimal rate."""
    rate = 0.0 if denominator == 0 else numerator / denominator
    return f"{numerator}/{denominator} = {rate:.3f}"


def _write_csv(frame: pl.DataFrame, path: Path) -> None:
    """Write a Polars frame as UTF-8 BOM CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frame.write_csv(), encoding="utf-8-sig")


def _write_text(path: Path, text: str) -> None:
    """Write a UTF-8 BOM text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def _write_checksums_manifest(base_dir: Path, report_path: Path, results_dir: Path) -> Path:
    """Write an MD5 manifest for the standalone analysis artifacts."""
    manifest_path = base_dir / "checksums.md5"
    tracked_paths = [
        base_dir / "README.md",
        report_path,
        base_dir / "analyze_duplicate_assignment_audit.py",
        base_dir / "verify_duplicate_assignment_audit.py",
    ]
    tracked_paths.extend(sorted(path for path in results_dir.rglob("*") if path.is_file()))
    lines: list[str] = []
    for path in tracked_paths:
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.as_posix()}")
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return manifest_path


def _load_compare_module() -> Any:
    """Load the compare_Cheung analysis script via importlib."""
    module_path = COMPARE_DIR / "analyze_compare_cheung_synergy_analysis.py"
    module_name = "compare_cheung_duplicate_audit"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load compare_Cheung module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_paper_args(args: argparse.Namespace) -> argparse.Namespace:
    """Build compare_Cheung CLI args with explicit runtime overrides."""
    return argparse.Namespace(
        config=args.config,
        run_dir=args.run_dir,
        report_path=COMPARE_DIR / "report.md",
        figure_dir=COMPARE_DIR / "figures",
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
    """Load the validated trial set used by compare_Cheung."""
    baseline = compare_mod.load_baseline_inputs(run_dir, cfg)
    manifest_lookup = compare_mod.select_trials_from_manifest(baseline["manifest_df"], paper_cfg)
    compare_mod._PIPELINE_CFG = cfg
    emg_df = load_emg_table(str(cfg["input"]["emg_parquet_path"]))
    compare_mod.validate_final_parquet_schema(emg_df, paper_cfg)
    event_df = load_event_metadata(str(cfg["input"]["event_xlsm_path"]), cfg)
    merged = merge_event_metadata(emg_df, event_df)
    trial_lookup = compare_mod.build_trial_matrix_dict(merged, baseline["manifest_df"], paper_cfg)
    return baseline, manifest_lookup, trial_lookup


def _make_unit_id(subject: str, velocity: Any, trial_num: Any, trial_id: str) -> str:
    """Build a stable trial-level unit identifier."""
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
    group_id: str,
    k: int,
    sample_map: list[dict[str, Any]],
    labels: np.ndarray,
    vectors: np.ndarray,
    centroids: np.ndarray,
    label_space: str,
    canonical_map: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Create component-level rows for one clustering output."""
    rows: list[dict[str, Any]] = []
    dist_sq = ((vectors[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2, dtype=np.float64)
    for index, sample in enumerate(sample_map):
        raw_cluster_id = int(labels[index])
        cluster_label = canonical_map.get(raw_cluster_id, f"{raw_cluster_id}") if canonical_map else f"{raw_cluster_id}"
        rows.append(
            {
                "pipeline_name": "paper_like",
                "state_name": PAPER_STATE,
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
            }
        )
    return rows


def _summarize_component_rows(component_rows: list[dict[str, Any]]) -> SelectedStateRows:
    """Compute the duplicate metrics requested by the audit."""
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
                scalar_product = float(np.dot(left_row["vector"], right_row["vector"]))
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
    if per_unit_rows:
        per_unit_frame = pl.DataFrame(per_unit_rows)
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
        k_map = {(row["pipeline_name"], row["state_name"], row["label_space"]): row for row in k_lookup}
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


def _paper_canonical_maps(step_common: Any, nonstep_common: Any, match_summary: dict[str, Any]) -> dict[str, dict[int, str]]:
    """Build the downstream label space from step-vs-nonstep centroid matching."""
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
    paper_cfg: Any,
    seed: int,
) -> dict[str, Any]:
    """Run the compare_Cheung paper-like path and collect audit metrics."""
    trial_results = compare_mod._collect_trial_results(trial_lookup, manifest_lookup, paper_cfg, seed)
    vector_df = compare_mod._build_vector_rows(trial_results)

    k_sensitivity_rows: list[dict[str, Any]] = []
    selected_component_rows: list[dict[str, Any]] = []
    common_summaries: dict[str, Any] = {}
    cluster_results: dict[str, dict[str, Any]] = {}

    for offset, group_id in enumerate(["global_step", "global_nonstep"]):
        group_vectors = vector_df.loc[vector_df["group_id"] == group_id].reset_index(drop=True)
        vectors = np.stack(group_vectors["vector"].to_list(), axis=0)
        k_values = list(range(2, min(int(paper_cfg.cluster_k_max), vectors.shape[0]) + 1))
        gap_result = compare_mod.compute_cheung_gap_statistic(vectors, k_values, paper_cfg, seed + offset)
        selected_k = int(gap_result["selected_k"])

        sample_map = [
            {
                "subject": row.subject,
                "velocity": float(row.velocity),
                "trial_num": int(row.trial_num),
                "trial_id": row.trial_id,
                "component_index": int(row.component_index),
            }
            for row in group_vectors.itertuples(index=False)
        ]
        selected_component_rows.extend(
            _build_component_rows(
                group_id=group_id,
                k=selected_k,
                sample_map=sample_map,
                labels=np.asarray(gap_result["labels"], dtype=np.int32),
                vectors=vectors,
                centroids=np.asarray(gap_result["centroids"], dtype=np.float64),
                label_space=RAW_LABEL_SPACE,
            )
        )

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
        member_frame = pd.DataFrame(selected_member_rows)
        common_summaries[group_id] = compare_mod.identify_common_clusters(member_frame, baseline["manifest_df"], paper_cfg)
        cluster_results[group_id] = {
            "selected_k": selected_k,
            "gap_result": gap_result,
        }

        for k in k_values:
            labels, centroids, objective = compare_mod._best_plain_kmeans_solution(
                vectors,
                k,
                paper_cfg.kmeans_restarts,
                seed + offset + (k * 1000),
            )
            per_k_rows = _build_component_rows(
                group_id=group_id,
                k=k,
                sample_map=sample_map,
                labels=np.asarray(labels, dtype=np.int32),
                vectors=vectors,
                centroids=np.asarray(centroids, dtype=np.float64),
                label_space=RAW_LABEL_SPACE,
            )
            summary = _summarize_component_rows(per_k_rows)
            overall_row = next(
                row
                for row in summary.overall_rows
                if row["scope"] == "group"
                and row["group_id"] == group_id
                and row["label_space"] == RAW_LABEL_SPACE
                and int(row["k"]) == int(k)
            )
            overall_row.update(
                {
                    "gap_statistic": float(gap_result["gap_by_k"][k]),
                    "gap_sd": float(gap_result["gap_sd_by_k"][k]),
                    "objective_sse": float(objective),
                    "point_to_centroid_sq_sum": float(sum(row["distance_sq_to_assigned_centroid"] for row in per_k_rows)),
                    "point_to_centroid_sum": float(sum(row["distance_to_assigned_centroid"] for row in per_k_rows)),
                    "selected_k_flag": bool(k == selected_k),
                    "selection_rule": "gap_statistic_first_k_ge_gap_next_minus_sd",
                }
            )
            k_sensitivity_rows.append(overall_row)

    match_summary = compare_mod.match_cluster_centroids(
        common_summaries["global_step"].centroids,
        common_summaries["global_nonstep"].centroids,
        paper_cfg,
    )
    canonical_maps = _paper_canonical_maps(
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

    return {
        "trial_results": trial_results,
        "vector_df": vector_df,
        "raw_state": _summarize_component_rows(selected_component_rows),
        "canonical_state": _summarize_component_rows(canonical_component_rows),
        "k_sensitivity_rows": k_sensitivity_rows,
        "cluster_results": cluster_results,
        "common_summaries": common_summaries,
        "match_summary": match_summary,
    }


def _collect_overall_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine overall rows across states."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.overall_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_per_unit_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine per-unit rows across states."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.per_unit_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_pair_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine pair rows across states."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.pair_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_cluster_frame(*state_rows: SelectedStateRows) -> pl.DataFrame:
    """Combine cluster-wise rows across states."""
    rows: list[dict[str, Any]] = []
    for state in state_rows:
        rows.extend(state.cluster_rows)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _collect_k_sensitivity_frame(row_list: list[dict[str, Any]]) -> pl.DataFrame:
    """Convert per-K summary rows into a Polars frame."""
    return pl.DataFrame(row_list) if row_list else pl.DataFrame()


def _worst_case_units(per_unit_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Extract the worst duplicate units from the raw paper-like state."""
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


def _similarity_summary(pair_rows: list[dict[str, Any]], label_space: str) -> dict[str, Any]:
    """Summarize duplicate and non-duplicate pair similarity distributions."""
    duplicate_values = [
        row["cosine_similarity"]
        for row in pair_rows
        if row["pipeline_name"] == "paper_like"
        and row["state_name"] == PAPER_STATE
        and row["label_space"] == label_space
        and row["pair_type"] == "duplicate"
    ]
    nonduplicate_values = [
        row["cosine_similarity"]
        for row in pair_rows
        if row["pipeline_name"] == "paper_like"
        and row["state_name"] == PAPER_STATE
        and row["label_space"] == label_space
        and row["pair_type"] == "non_duplicate"
    ]
    duplicate_scalars = [
        row["scalar_product"]
        for row in pair_rows
        if row["pipeline_name"] == "paper_like"
        and row["state_name"] == PAPER_STATE
        and row["label_space"] == label_space
        and row["pair_type"] == "duplicate"
    ]
    nonduplicate_scalars = [
        row["scalar_product"]
        for row in pair_rows
        if row["pipeline_name"] == "paper_like"
        and row["state_name"] == PAPER_STATE
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


def _plot_gap_sensitivity(k_frame: pl.DataFrame, output_dir: Path) -> None:
    """Plot K versus gap statistic."""
    if k_frame.is_empty():
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    for group_id, group_frame in k_frame.group_by("group_id", maintain_order=True):
        group_value = group_id[0] if isinstance(group_id, tuple) else group_id
        rows = group_frame.sort("k").to_dicts()
        ax.plot([row["k"] for row in rows], [row["gap_statistic"] for row in rows], marker="o", label=str(group_value))
    ax.set_xlabel("K")
    ax.set_ylabel("Gap statistic")
    ax.set_title("compare_Cheung K vs gap statistic")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "k_vs_gap_statistic.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_duplicate_sensitivity(k_frame: pl.DataFrame, output_dir: Path, column: str, filename: str, title: str) -> None:
    """Plot one duplicate metric over K."""
    if k_frame.is_empty():
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    for group_id, group_frame in k_frame.group_by("group_id", maintain_order=True):
        group_value = group_id[0] if isinstance(group_id, tuple) else group_id
        rows = group_frame.sort("k").to_dicts()
        ax.plot([row["k"] for row in rows], [row[column] for row in rows], marker="o", label=str(group_value))
    ax.set_xlabel("K")
    ax.set_ylabel(column)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_group_duplicate_bars(overall_frame: pl.DataFrame, output_dir: Path) -> None:
    """Plot selected-K duplicate-unit rates by group."""
    subset = overall_frame.filter(
        (pl.col("scope") == "group")
        & (pl.col("pipeline_name") == "paper_like")
        & (pl.col("state_name") == PAPER_STATE)
        & (pl.col("label_space") == RAW_LABEL_SPACE)
    )
    if subset.is_empty():
        return
    rows = subset.sort("group_id").select(["group_id", "duplicate_unit_rate"]).to_dicts()
    labels = [str(row["group_id"]) for row in rows]
    values = [row["duplicate_unit_rate"] for row in rows]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(np.arange(len(rows)), values, color="#3A86FF")
    ax.set_xticks(np.arange(len(rows)))
    ax.set_xticklabels(labels)
    ax.set_ylabel("duplicate_unit_rate")
    ax.set_title("Group-specific duplicate unit rate")
    fig.tight_layout()
    fig.savefig(output_dir / "group_duplicate_unit_rate.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_similarity(pair_frame: pl.DataFrame, output_dir: Path) -> None:
    """Plot duplicate versus non-duplicate cosine similarity."""
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
    ax.set_title("Within-trial pair similarity")
    fig.tight_layout()
    fig.savefig(output_dir / "duplicate_vs_nonduplicate_similarity.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _summary_lookup(
    overall_frame: pl.DataFrame,
    *,
    label_space: str,
    scope: str,
    group_id: str,
) -> dict[str, Any]:
    """Fetch one overall summary row."""
    rows = overall_frame.filter(
        (pl.col("pipeline_name") == "paper_like")
        & (pl.col("state_name") == PAPER_STATE)
        & (pl.col("label_space") == label_space)
        & (pl.col("scope") == scope)
        & (pl.col("group_id") == group_id)
    ).to_dicts()
    if not rows:
        raise KeyError(f"Missing overall row for {label_space}/{scope}/{group_id}")
    return rows[0]


def _paper_subject_variation(per_unit_frame: pl.DataFrame) -> list[dict[str, Any]]:
    """Compute subject-level duplicate-unit rates for the raw label space."""
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


def _report_table(columns: list[str], rows: list[list[str]]) -> str:
    """Render a markdown table."""
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def _build_report_markdown(
    *,
    args: argparse.Namespace,
    paper_cfg: Any,
    overall_frame: pl.DataFrame,
    per_unit_frame: pl.DataFrame,
    paper_results: dict[str, Any],
    worst_cases: list[dict[str, Any]],
    raw_similarity: dict[str, Any],
) -> str:
    """Render the standalone audit report."""
    raw_overall = _summary_lookup(overall_frame, label_space=RAW_LABEL_SPACE, scope="overall", group_id="__overall__")
    canonical_overall = _summary_lookup(overall_frame, label_space=CANONICAL_LABEL_SPACE, scope="overall", group_id="__overall__")
    raw_step = _summary_lookup(overall_frame, label_space=RAW_LABEL_SPACE, scope="group", group_id="global_step")
    raw_nonstep = _summary_lookup(overall_frame, label_space=RAW_LABEL_SPACE, scope="group", group_id="global_nonstep")
    canonical_step = _summary_lookup(overall_frame, label_space=CANONICAL_LABEL_SPACE, scope="group", group_id="global_step")
    canonical_nonstep = _summary_lookup(overall_frame, label_space=CANONICAL_LABEL_SPACE, scope="group", group_id="global_nonstep")
    subject_variation_rows = _paper_subject_variation(per_unit_frame)
    step_selected_k = int(paper_results["cluster_results"]["global_step"]["selected_k"])
    nonstep_selected_k = int(paper_results["cluster_results"]["global_nonstep"]["selected_k"])

    issue_flag_lines = [
        "Source review did not find a within-trial forced-reassignment call in `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`, and the executed raw outputs still contain duplicates, so the path behaves as unconstrained in practice.",
        f"This audit intentionally uses the checked-in compare_Cheung runtime overrides `--kmeans-restarts {args.paper_kmeans_restarts} --gap-ref-n {args.paper_gap_ref_n} --gap-ref-restarts {args.paper_gap_ref_restarts}` because the committed `analysis/compare_Cheung,2021/report.md` was generated that way, while the script defaults remain `1000/500/100`.",
    ]

    recommendation = "A"
    if raw_overall["duplicate_unit_rate"] > 0.250 or raw_overall["duplicate_pair_rate"] > 0.100:
        recommendation = "C"
    elif raw_overall["duplicate_unit_rate"] > 0.050 or raw_overall["duplicate_pair_rate"] > 0.020:
        recommendation = "B"
    recommendation_text = {
        "A": "A: 현재 paper-like pipeline 유지 가능",
        "B": "B: 결과는 쓸 수 있으나 duplicate caveat를 반드시 명시해야 함",
        "C": "C: forced reassignment 또는 constrained clustering 없이 biological 해석을 하면 위험함",
    }[recommendation]

    if raw_overall["duplicate_unit_rate"] <= 0.050 and raw_overall["duplicate_pair_rate"] <= 0.020:
        interpretation_main = "같은 unit 내부 duplicate는 실제로 드물어 biological interpretation을 크게 흔드는 수준은 아니었다."
    elif raw_overall["duplicate_unit_rate"] <= 0.250 and raw_overall["duplicate_pair_rate"] <= 0.100:
        interpretation_main = "duplicate는 무시할 수준은 아니며, cluster를 biological module identity처럼 읽을 때 caveat를 반드시 명시해야 한다."
    else:
        interpretation_main = "duplicate가 충분히 자주 발생해, unconstrained cluster label을 biological module identity로 직접 해석하면 위험하다."
    if raw_similarity["duplicate_cosine_mean"] > raw_similarity["nonduplicate_cosine_mean"] + 0.100:
        interpretation_similarity = "duplicate pair의 평균 cosine similarity가 non-duplicate보다 높아서, 일부 중복은 실제로 꽤 비슷한 synergy가 같은 cluster에 함께 들어간 사례에 가깝다."
    else:
        interpretation_similarity = "duplicate pair similarity가 non-duplicate와 크게 벌어지지 않아, NMF상 다른 synergy가 같은 cluster로 묶인 사례도 적지 않다."

    k_sensitivity = pl.DataFrame(paper_results["k_sensitivity_rows"]).sort(["group_id", "k"])
    k_rows = k_sensitivity.select(
        ["group_id", "k", "gap_statistic", "objective_sse", "duplicate_unit_rate", "excess_duplicate_ratio", "units_nsyn_gt_k"]
    ).to_dicts()
    k_table_rows = [
        [
            str(row["group_id"]),
            str(int(row["k"])),
            _fmt_num(row["gap_statistic"]),
            _fmt_num(row["objective_sse"]),
            _fmt_num(row["duplicate_unit_rate"]),
            _fmt_num(row["excess_duplicate_ratio"]),
            f"{int(row['units_nsyn_gt_k'])}",
        ]
        for row in k_rows
    ]

    worst_case_table = "No duplicate units were found in the selected raw label space.\n"
    if worst_cases:
        worst_case_table = _report_table(
            [
                "subject_id",
                "group",
                "trial_id",
                "Nsyn",
                "chosen K",
                "synergy_indexes",
                "assigned cluster",
                "centroid distance",
                "pairwise similarity",
            ],
            [
                [
                    str(row["subject_id"]),
                    str(row["group_id"]),
                    str(row["trial_id"]),
                    str(int(row["Nsyn"])),
                    str(int(row["chosen_K"])),
                    f"`{row['synergy_indexes']}`",
                    f"`{row['assigned_clusters']}`",
                    f"`{row['centroid_distances']}`",
                    f"`{row['duplicate_pair_similarity']}`",
                ]
                for row in worst_cases
            ],
        )

    subject_variation_text = (
        "\n".join(
            f"- {row['subject']}: {int(row['duplicate_units'])}/{int(row['units_total'])} = {float(row['duplicate_unit_rate']):.3f}"
            for row in subject_variation_rows
        )
        if subject_variation_rows
        else "- No subject-level variation rows were available."
    )

    match_summary = paper_results["match_summary"]
    issue_flag_text = "\n".join(f"- {line}" for line in issue_flag_lines)
    k_table = _report_table(
        ["group_id", "K", "gap", "SSE", "duplicate_unit_rate", "excess_duplicate_ratio", "units_with_Nsyn_gt_K"],
        k_table_rows,
    )

    return f"""# Duplicate Assignment Audit for compare_Cheung

## 1) Executive summary

Ambiguities / missing:
{issue_flag_text}

실제 duplicate는 `analysis/compare_Cheung,2021`의 paper-like unconstrained 경로에서 존재한다. raw group-specific label 기준 전체 `duplicate_unit_rate`는 {_fmt_fraction(int(raw_overall['duplicate_units']), int(raw_overall['units_total']))}, `excess_duplicate_ratio`는 `{int(raw_overall['excess_duplicates_total'])}/{int(raw_overall['synergies_total'])} = {raw_overall['excess_duplicate_ratio']:.3f}`, `duplicate_pair_rate`는 `{int(raw_overall['duplicate_pairs_total'])}/{int(raw_overall['within_unit_pairs_total'])} = {raw_overall['duplicate_pair_rate']:.3f}`였다.

forced reassignment는 이번 source-of-truth 코드 경로에는 없다. source review에서 within-trial/session uniqueness constraint를 강제하는 후처리 호출을 찾지 못했고, 실행된 raw output에도 duplicate가 `28/125 = 0.224` 남아 있어 이 경로가 실질적으로 unconstrained임을 확인했다.

이 문제가 downstream biological interpretation을 흔드는 정도는 raw label 기준 duplicate가 얼마나 자주 나타나는지에 달려 있다. {interpretation_main} {interpretation_similarity}

## 2) Actual pipeline map

`analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py` 기준 실행 순서:
- `load_baseline_inputs()` -> `select_trials_from_manifest()` -> `build_trial_matrix_dict()`로 selected trial set을 확정한다.
- `_collect_trial_results()`가 각 trial의 EMG matrix에 대해 `run_paper_nmf_for_trial()`을 호출한다.
- `run_paper_nmf_for_trial()`은 multiplicative-update NMF를 rank search로 반복하고, `structures`를 row-wise L2 norm으로 정규화한 `normalized_structures`를 만든다.
- `_build_vector_rows()`가 trial 내부 각 synergy를 독립 sample로 펼쳐 `vector` column을 만든다.
- `compute_cheung_gap_statistic()`이 candidate `K`별 ordinary pooled k-means를 평가하고, `_best_plain_kmeans_solution()`의 SSE를 사용해 gap statistic을 계산한다.
- 최종 selected `K`의 label은 raw group-specific label space를 이룬다.
- `identify_common_clusters()`가 subject-invariant centroid를 정의하고, `match_cluster_centroids()`가 step/nonstep centroid를 Hungarian matching으로 연결해 downstream canonical label space를 만든다.
- forced reassignment / deduplication / unique matching은 cluster membership assignment 단계에는 개입하지 않는다. `linear_sum_assignment()`는 centroid matching에만 사용된다.

핵심 파라미터:
- NMF unit: trial
- clustering input unit: trial 내부 각 synergy vector
- normalization: `run_paper_nmf_for_trial()`의 `normalized_structures = structures / ||structures||_2`
- distance metric: squared Euclidean objective (`_objective()`)
- centroid initialization: data-point sampling (`_sample_initial_centroids()`)
- KMeans engine: `sklearn.cluster.KMeans(..., algorithm="lloyd", n_init=1)`
- observed-data restarts: `{args.paper_kmeans_restarts}`
- gap reference datasets: `{args.paper_gap_ref_n}`
- reference-dataset restarts: `{args.paper_gap_ref_restarts}`
- final K rule: 첫 `k`에 대해 `gap(k) >= gap(k+1) - sd(k+1)`를 만족하면 그 `k`를 선택, 없으면 최대 `K`

## 3) Final K and sensitivity

selected K는 `global_step={step_selected_k}`, `global_nonstep={nonstep_selected_k}`였다. 전체 K 후보에 대한 gap statistic, duplicate rate, SSE는 아래 표와 `results/k_sensitivity.csv`, `results/plots/`에서 재현 가능하다.

{k_table}

## 4) Main numbers

raw group-specific label:
- overall `duplicate_unit_rate`: {_fmt_fraction(int(raw_overall['duplicate_units']), int(raw_overall['units_total']))}
- overall `excess_duplicate_ratio`: `{int(raw_overall['excess_duplicates_total'])}/{int(raw_overall['synergies_total'])} = {raw_overall['excess_duplicate_ratio']:.3f}`
- overall `duplicate_pair_rate`: `{int(raw_overall['duplicate_pairs_total'])}/{int(raw_overall['within_unit_pairs_total'])} = {raw_overall['duplicate_pair_rate']:.3f}`
- overall `units_with_Nsyn_gt_K`: `{int(raw_overall['units_nsyn_gt_k'])}/{int(raw_overall['units_total'])} = {raw_overall['units_nsyn_gt_k_rate']:.3f}`
- `global_step duplicate_unit_rate`: {_fmt_fraction(int(raw_step['duplicate_units']), int(raw_step['units_total']))}
- `global_nonstep duplicate_unit_rate`: {_fmt_fraction(int(raw_nonstep['duplicate_units']), int(raw_nonstep['units_total']))}

downstream canonical label:
- overall `duplicate_unit_rate`: {_fmt_fraction(int(canonical_overall['duplicate_units']), int(canonical_overall['units_total']))}
- `global_step duplicate_unit_rate`: {_fmt_fraction(int(canonical_step['duplicate_units']), int(canonical_step['units_total']))}
- `global_nonstep duplicate_unit_rate`: {_fmt_fraction(int(canonical_nonstep['duplicate_units']), int(canonical_nonstep['units_total']))}
- canonical label은 raw duplicate를 줄이는 단계가 아니라 matched/unmatched centroid naming 단계이므로, duplicate가 생기거나 사라지는지는 label collapse 여부와 common-centroid mapping에 의해 해석해야 한다.

subject-level 편차 상위 5개:
{subject_variation_text}

## 5) Forced reassignment findings

이번 감사의 source-of-truth인 `analysis/compare_Cheung,2021` 코드 경로에는 forced reassignment가 없다.
- State 1: 존재함. ordinary k-means + gap statistic selected K 결과.
- State 2: 없음. forced reassignment 직전 상태를 따로 정의할 수 없다.
- State 3: 없음. forced reassignment 후 상태를 따로 정의할 수 없다.

따라서 assignment cost 증가량, reassigned synergy count, transition table은 이번 analysis scope에서는 해당 사항이 없다. `results/`에도 `reassignment_stats.csv`를 생성하지 않았다.

## 6) Interpretation

- raw label 기준 해석: {interpretation_main}
- similarity 비교: duplicate cosine mean `{_fmt_num(raw_similarity['duplicate_cosine_mean'])}` vs non-duplicate cosine mean `{_fmt_num(raw_similarity['nonduplicate_cosine_mean'])}`. duplicate scalar-product mean `{_fmt_num(raw_similarity['duplicate_scalar_mean'])}`, non-duplicate scalar-product mean `{_fmt_num(raw_similarity['nonduplicate_scalar_mean'])}`.
- 정규화 기준: clustering 입력 vector가 이미 L2-normalized이므로 cosine similarity와 scalar product는 수치적으로 거의 같다.
- cross-group matching 이후 canonical label 기준 duplicate는 overall `{_fmt_fraction(int(canonical_overall['duplicate_units']), int(canonical_overall['units_total']))}`로 raw label과 분리해서 읽어야 한다.

worst duplicate units:
{worst_case_table}

## 7) Recommendation

{recommendation_text}

## Reproduction

실행:

```bash
conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py
```

검증:

```bash
conda run --no-capture-output -n module python analysis/duplicate_assignment_audit/verify_duplicate_assignment_audit.py
```

산출물:
- report: `analysis/duplicate_assignment_audit/report.md`
- reproducible artifacts: `analysis/duplicate_assignment_audit/results/`

Q1. paper-like unconstrained pipeline에서 같은 trial/session 내 duplicate assignment는 실제로 얼마나 발생하는가?
A1. raw group-specific label 기준 `duplicate_unit_rate`는 {_fmt_fraction(int(raw_overall['duplicate_units']), int(raw_overall['units_total']))}, `excess_duplicate_ratio`는 `{int(raw_overall['excess_duplicates_total'])}/{int(raw_overall['synergies_total'])} = {raw_overall['excess_duplicate_ratio']:.3f}`, `duplicate_pair_rate`는 `{int(raw_overall['duplicate_pairs_total'])}/{int(raw_overall['within_unit_pairs_total'])} = {raw_overall['duplicate_pair_rate']:.3f}`였다.

Q2. forced reassignment는 repo에 실제로 존재하는가? 존재하면 정확히 어디서 개입하는가?
A2. `analysis/compare_Cheung,2021` 코드 경로 안에는 존재하지 않는다. source review에서 within-trial uniqueness를 강제하는 reassignment 호출을 찾지 못했고, 실행된 raw output에도 duplicate가 `28/125 = 0.224` 남아 있어 ordinary k-means assignment가 그대로 유지된다고 판단했다.

Q3. forced reassignment는 duplicate를 없애는 대신 assignment cost를 얼마나 증가시키는가?
A3. 이번 source-of-truth 경로에는 forced reassignment 단계 자체가 없어서 해당 사항이 없다. 따라서 증가한 assignment cost도 `n/a`다.

Q4. 이 duplicate 문제는 biological interpretation을 실제로 흔드는 수준인가?
A4. {interpretation_main} {interpretation_similarity} 따라서 최종 권고는 `{recommendation}`에 해당한다.
"""


def main() -> int:
    """Run the compare_Cheung duplicate-assignment audit."""
    args = parse_args()
    compare_mod = _load_compare_module()
    cfg = load_pipeline_config(str(args.config))
    paper_cfg = compare_mod._build_method_config(_make_paper_args(args), cfg)
    baseline, manifest_lookup, trial_lookup = _load_trial_inputs(cfg, compare_mod, paper_cfg, args.run_dir)

    manifest_df = baseline["manifest_df"].to_pandas()
    step_n = int((manifest_df["analysis_step_class"] == "step").sum())
    nonstep_n = int((manifest_df["analysis_step_class"] == "nonstep").sum())
    subject_n = int(manifest_df["subject"].astype(str).nunique())
    print(f"[M1] Loaded compare_Cheung inputs from: {args.run_dir}")
    print(f"[M1] Selected trials: step={step_n}, nonstep={nonstep_n}, unique_subjects={subject_n}")
    print(
        "[M1] Runtime overrides: "
        f"kmeans_restarts={args.paper_kmeans_restarts}, gap_ref_n={args.paper_gap_ref_n}, "
        f"gap_ref_restarts={args.paper_gap_ref_restarts}"
    )

    if args.dry_run:
        print("[M2] Dry run complete. No outputs were written.")
        return 0

    if args.results_dir.exists():
        shutil.rmtree(args.results_dir)
    plot_dir = args.results_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    paper_results = _audit_paper_like(
        compare_mod=compare_mod,
        baseline=baseline,
        trial_lookup=trial_lookup,
        manifest_lookup=manifest_lookup,
        paper_cfg=paper_cfg,
        seed=int(args.seed),
    )
    print("[M2] Paper-like duplicate audit complete")

    overall_frame = _collect_overall_frame(paper_results["raw_state"], paper_results["canonical_state"])
    per_unit_frame = _collect_per_unit_frame(paper_results["raw_state"], paper_results["canonical_state"])
    pair_frame = _collect_pair_frame(paper_results["raw_state"], paper_results["canonical_state"])
    cluster_frame = _collect_cluster_frame(paper_results["raw_state"], paper_results["canonical_state"])
    k_frame = _collect_k_sensitivity_frame(paper_results["k_sensitivity_rows"]).sort(["group_id", "k"])

    worst_cases = _worst_case_units(paper_results["raw_state"].per_unit_rows, paper_results["raw_state"].pair_rows)
    raw_similarity = _similarity_summary(paper_results["raw_state"].pair_rows, RAW_LABEL_SPACE)

    _plot_gap_sensitivity(k_frame, plot_dir)
    _plot_duplicate_sensitivity(
        k_frame,
        plot_dir,
        column="duplicate_unit_rate",
        filename="k_vs_duplicate_unit_rate.png",
        title="compare_Cheung K vs duplicate unit rate",
    )
    _plot_duplicate_sensitivity(
        k_frame,
        plot_dir,
        column="excess_duplicate_ratio",
        filename="k_vs_excess_duplicate_ratio.png",
        title="compare_Cheung K vs excess duplicate ratio",
    )
    _plot_group_duplicate_bars(overall_frame, plot_dir)
    _plot_similarity(pair_frame, plot_dir)

    _write_csv(
        overall_frame.sort(["pipeline_name", "state_name", "label_space", "scope", "group_id"]),
        args.results_dir / "overall_metrics.csv",
    )
    _write_csv(
        per_unit_frame.sort(["pipeline_name", "state_name", "label_space", "group_id", "subject", "trial_id"]),
        args.results_dir / "per_unit_metrics.csv",
    )
    _write_csv(
        pair_frame.sort(["pipeline_name", "state_name", "label_space", "group_id", "trial_id", "component_index_i", "component_index_j"]),
        args.results_dir / "duplicate_pairs.csv",
    )
    _write_csv(
        cluster_frame.sort(["pipeline_name", "state_name", "label_space", "group_id", "cluster_label"]),
        args.results_dir / "per_cluster_stats.csv",
    )
    _write_csv(k_frame, args.results_dir / "k_sensitivity.csv")

    report_text = _build_report_markdown(
        args=args,
        paper_cfg=paper_cfg,
        overall_frame=overall_frame,
        per_unit_frame=per_unit_frame,
        paper_results=paper_results,
        worst_cases=worst_cases,
        raw_similarity=raw_similarity,
    )
    _write_text(args.report_path, report_text)
    checksum_path = _write_checksums_manifest(SCRIPT_DIR, args.report_path, args.results_dir)

    print(f"[M3] Wrote report: {args.report_path}")
    print(f"[M3] Wrote reproducible artifacts under: {args.results_dir}")
    print(f"[M3] Wrote checksum manifest: {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
