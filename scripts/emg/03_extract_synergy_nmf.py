"""Extract trialwise and concatenated NMF features for clustering.

This stage resolves the requested analysis modes,
runs the existing NMF extractor on each analysis unit,
and stores per-mode feature rows for later clustering.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean, pstdev

from src.emg_pipeline.log_utils import compact_list, format_float, log_kv_section
from src.synergy_stats.clustering import SubjectFeatureResult
from src.synergy_stats.concatenated import build_concatenated_feature_rows
from src.synergy_stats.methods import primary_analysis_mode, resolve_analysis_modes
from src.synergy_stats.nmf import describe_nmf_runtime, extract_trial_features


def _format_rank_distribution(rank_counts: Counter[int]) -> str:
    if not rank_counts:
        return "n/a"
    return ", ".join(f"{rank}={count}" for rank, count in sorted(rank_counts.items()))


def _trial_id(subject: str, velocity: object, trial_num: object) -> str:
    return f"{subject}_v{velocity}_T{trial_num}"


def _build_trialwise_feature_rows(context: dict) -> list[SubjectFeatureResult]:
    cfg = context["config"]
    muscle_names = list(cfg["muscles"]["names"])
    feature_rows = []
    for trial in context["trial_records"]:
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


def _log_mode_summary(mode: str, feature_rows: list[SubjectFeatureResult]) -> None:
    meta_rows = [item.bundle.meta for item in feature_rows]
    component_counts = [int(meta.get("n_components", 0)) for meta in meta_rows]
    vaf_values = [float(meta.get("vaf")) for meta in meta_rows]
    elapsed_values = [float(meta.get("extractor_metric_elapsed_sec", 0.0)) for meta in meta_rows]
    backend_summary = sorted({str(meta.get("extractor_backend", "")) or "unknown" for meta in meta_rows})
    log_kv_section(
        f"NMF Summary: {mode}",
        [
            ("Analysis units", len(feature_rows)),
            ("Rank distribution", _format_rank_distribution(Counter(component_counts))),
            (
                "VAF range",
                (
                    f"{format_float(min(vaf_values), digits=4)} - {format_float(max(vaf_values), digits=4)}"
                    if vaf_values
                    else "n/a"
                ),
            ),
            ("VAF mean", format_float(mean(vaf_values) if vaf_values else None, digits=4)),
            ("VAF std", format_float(pstdev(vaf_values) if len(vaf_values) > 1 else 0.0, digits=4)),
            ("Total components", sum(component_counts)),
            ("Avg analysis-unit time", f"{format_float(mean(elapsed_values) if elapsed_values else None, digits=3)}s"),
            ("Backends used", compact_list(backend_summary)),
        ],
    )


def run(context: dict) -> dict:
    cfg = context["config"]
    runtime = describe_nmf_runtime(cfg.get("feature_extractor", {}).get("nmf", {}))
    log_kv_section(
        "NMF Runtime",
        [
            ("Requested backend", runtime["backend"]),
            ("Torch device", runtime["torch_device"] or "n/a"),
            ("Torch dtype", runtime["torch_dtype"] or "n/a"),
        ],
    )
    analysis_modes = context.get("analysis_modes") or cfg.get("runtime", {}).get("analysis_modes")
    if not analysis_modes:
        analysis_modes = resolve_analysis_modes(cfg.get("synergy_analysis", {}).get("mode", "both"))

    analysis_mode_feature_rows: dict[str, list[SubjectFeatureResult]] = {}
    if "trialwise" in analysis_modes:
        analysis_mode_feature_rows["trialwise"] = _build_trialwise_feature_rows(context)
        _log_mode_summary("trialwise", analysis_mode_feature_rows["trialwise"])
    if "concatenated" in analysis_modes:
        analysis_mode_feature_rows["concatenated"] = build_concatenated_feature_rows(
            context["trial_records"],
            list(cfg["muscles"]["names"]),
            cfg,
        )
        _log_mode_summary("concatenated", analysis_mode_feature_rows["concatenated"])

    context["analysis_modes"] = [mode for mode in analysis_modes if mode in analysis_mode_feature_rows]
    context["analysis_mode_feature_rows"] = analysis_mode_feature_rows
    context["feature_rows"] = analysis_mode_feature_rows[primary_analysis_mode(context["analysis_modes"])]
    return context
