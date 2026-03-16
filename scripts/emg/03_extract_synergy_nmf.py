"""Extract per-trial NMF features for later global clustering."""

from __future__ import annotations

from collections import Counter
from statistics import mean, pstdev

from src.synergy_stats.clustering import SubjectFeatureResult
from src.synergy_stats.nmf import describe_nmf_runtime, extract_trial_features
from src.emg_pipeline.log_utils import compact_list, format_float, log_kv_section


def _format_rank_distribution(rank_counts: Counter[int]) -> str:
    if not rank_counts:
        return "n/a"
    return ", ".join(f"{rank}={count}" for rank, count in sorted(rank_counts.items()))


def run(context: dict) -> dict:
    cfg = context["config"]
    muscle_names = list(cfg["muscles"]["names"])
    runtime = describe_nmf_runtime(cfg.get("feature_extractor", {}).get("nmf", {}))
    log_kv_section(
        "NMF Runtime",
        [
            ("Requested backend", runtime["backend"]),
            ("Torch device", runtime["torch_device"] or "n/a"),
            ("Torch dtype", runtime["torch_dtype"] or "n/a"),
        ],
    )
    feature_rows = []
    for trial in context["trial_records"]:
        X_trial = trial.frame[muscle_names].to_numpy(dtype="float32")
        bundle = extract_trial_features(X_trial, cfg)
        bundle.meta.update(
            {
                "subject": trial.key[0],
                "velocity": trial.key[1],
                "trial_num": trial.key[2],
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
    context["feature_rows"] = feature_rows
    meta_rows = [item.bundle.meta for item in feature_rows]
    component_counts = [int(meta.get("n_components", 0)) for meta in meta_rows]
    vaf_values = [float(meta.get("vaf")) for meta in meta_rows]
    elapsed_values = [float(meta.get("extractor_metric_elapsed_sec", 0.0)) for meta in meta_rows]
    backend_summary = sorted({str(meta.get("extractor_backend", "")) or "unknown" for meta in meta_rows})
    log_kv_section(
        "NMF Summary",
        [
            ("Trials", len(feature_rows)),
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
            ("Avg trial time", f"{format_float(mean(elapsed_values) if elapsed_values else None, digits=3)}s"),
            ("Backends used", compact_list(backend_summary)),
        ],
    )
    return context
