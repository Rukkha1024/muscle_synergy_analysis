# -*- coding: utf-8 -*-
"""Analyze VAF-threshold sensitivity for synergy rank and pooled K.

Runs the main trial-selection, trialwise NMF, concatenated NMF,
and pooled clustering logic for VAF thresholds 0.80-0.95.
Summarizes subject-by-strategy rank changes and mode-level K selection.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from statistics import stdev
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.emg_pipeline import (
    build_trial_records,
    load_emg_table,
    load_event_metadata,
    load_pipeline_config,
    merge_event_metadata,
)
from src.synergy_stats.clustering import SubjectFeatureResult, cluster_feature_group
from src.synergy_stats.concatenated import build_concatenated_feature_rows
from src.synergy_stats.nmf import extract_trial_features


DEFAULT_THRESHOLDS = (0.80, 0.85, 0.90, 0.95)
DEFAULT_OUT_DIR = SCRIPT_DIR / "artifacts" / "default_run"
MODE_ORDER = ("trialwise", "concatenated")
STEP_CLASS_ORDER = ("step", "nonstep")


@dataclass
class ThresholdModeResult:
    """Container for one mode's VAF-threshold rerun outputs."""

    threshold: float
    mode: str
    feature_rows: list[SubjectFeatureResult]
    cluster_result: dict[str, Any]


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


def _build_trialwise_feature_rows(
    trial_records: list[Any],
    cfg: dict[str, Any],
    muscle_names: list[str],
) -> list[SubjectFeatureResult]:
    feature_rows: list[SubjectFeatureResult] = []
    for trial in trial_records:
        x_trial = trial.frame[muscle_names].to_numpy(dtype="float32")
        bundle = extract_trial_features(x_trial, cfg)
        bundle.meta.update(
            {
                "subject": trial.key[0],
                "velocity": trial.key[1],
                "trial_num": trial.key[2],
                "aggregation_mode": "trialwise",
                "analysis_unit_id": _trial_id(trial.key[0], trial.key[1], trial.key[2]),
                "source_trial_nums_csv": str(trial.key[2]),
                "analysis_source_trial_count": 1,
                **trial.metadata,
            }
        )
        feature_rows.append(
            SubjectFeatureResult(
                subject=trial.key[0],
                velocity=trial.key[1],
                trial_num=trial.key[2],
                bundle=bundle,
            )
        )
    return feature_rows


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


def _prepare_threshold_cfg(base_cfg: dict[str, Any], threshold: float) -> dict[str, Any]:
    cfg = deepcopy(base_cfg)
    cfg.setdefault("synergy_analysis", {})["mode"] = "both"
    cfg.setdefault("feature_extractor", {}).setdefault("nmf", {})["vaf_threshold"] = float(threshold)
    return cfg


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


def _overall_mode_summary_row(result: ThresholdModeResult) -> dict[str, Any]:
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
        "vaf_mean": round(sum(vaf_values) / len(vaf_values), 6),
        "vaf_min": round(min(vaf_values), 6),
        "vaf_max": round(max(vaf_values), 6),
        "k_lb": cluster_result.get("k_lb"),
        "k_gap_raw": cluster_result.get("k_gap_raw"),
        "k_selected": cluster_result.get("k_selected"),
        "k_min_unique": cluster_result.get("k_min_unique"),
        "selection_status": cluster_result.get("selection_status"),
        "algorithm_used": cluster_result.get("algorithm_used"),
        "n_components_clustered": cluster_result.get("n_components"),
    }


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
    trial_records: list[Any],
    muscle_names: list[str],
    cfg: dict[str, Any],
    threshold: float,
) -> dict[str, ThresholdModeResult]:
    threshold_cfg = _prepare_threshold_cfg(cfg, threshold)
    trialwise_rows = _build_trialwise_feature_rows(trial_records, threshold_cfg, muscle_names)
    concatenated_rows = build_concatenated_feature_rows(trial_records, muscle_names, threshold_cfg)
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
    selected_trial_frame = merged_df.drop_duplicates(subset=["subject", "velocity", "trial_num"]).copy()
    if "analysis_selected_group" in selected_trial_frame.columns:
        selected_trial_frame = selected_trial_frame.loc[selected_trial_frame["analysis_selected_group"].fillna(False)].copy()

    subject_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    for mode in MODE_ORDER:
        for result in threshold_results[mode]:
            overall_row = _overall_mode_summary_row(result)
            overall_rows.append(overall_row)
            cluster_rows.append(
                {
                    "mode": mode,
                    "threshold_label": overall_row["threshold_label"],
                    "analysis_unit_count": overall_row["analysis_unit_count"],
                    "component_count_total": overall_row["component_count_total"],
                    "k_lb": overall_row["k_lb"],
                    "k_gap_raw": overall_row["k_gap_raw"],
                    "k_selected": overall_row["k_selected"],
                    "k_min_unique": overall_row["k_min_unique"],
                    "selection_status": overall_row["selection_status"],
                }
            )
            subject_rows.extend(_subject_strategy_summary_rows(result.feature_rows, mode, result.threshold))

    threshold_component_rows: list[dict[str, Any]] = []
    for mode in MODE_ORDER:
        for threshold in args.thresholds:
            threshold_label = _format_threshold(float(threshold))
            mode_rows = [row for row in subject_rows if row["mode"] == mode and row["threshold_label"] == threshold_label]
            row: dict[str, Any] = {
                "mode": mode,
                "threshold": float(threshold),
                "threshold_label": threshold_label,
                "subject_count_total": len({str(item["subject"]) for item in mode_rows}),
            }
            for step_class in STEP_CLASS_ORDER:
                step_rows = [item for item in mode_rows if item["step_class"] == step_class]
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
            threshold_component_rows.append(row)

    return {
        "config_path": str(args.config),
        "out_dir": str(args.out_dir),
        "thresholds": [float(value) for value in args.thresholds],
        "input": {
            "emg_parquet_path": cfg["input"]["emg_parquet_path"],
            "event_xlsm_path": cfg["input"]["event_xlsm_path"],
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
            "input": payload["input"],
            "data_summary": payload["data_summary"],
            "overall_mode_summary": [
                row for row in payload["overall_mode_summary"] if row["threshold_label"] == threshold_label
            ],
            "cluster_summary": [
                row for row in payload["cluster_summary"] if row["threshold_label"] == threshold_label
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
                "nonstep_subject_count",
                "nonstep_component_mean_sd",
                "nonstep_component_range",
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

    if args.dry_run:
        print("\nDry run complete. Input loading and trial extraction succeeded.")
        return

    threshold_results: dict[str, list[ThresholdModeResult]] = {mode: [] for mode in MODE_ORDER}
    for threshold in args.thresholds:
        _print_section(f"Running threshold {_format_threshold(threshold)}")
        run_results = _run_threshold_analysis(trial_records, muscle_names, cfg, float(threshold))
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
