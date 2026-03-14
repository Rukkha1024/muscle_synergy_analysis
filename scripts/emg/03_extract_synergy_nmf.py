"""Extract per-trial NMF features for later global clustering."""

from __future__ import annotations

import logging

from src.synergy_stats.clustering import SubjectFeatureResult
from src.synergy_stats.nmf import describe_nmf_runtime, extract_trial_features


def run(context: dict) -> dict:
    cfg = context["config"]
    muscle_names = list(cfg["muscles"]["names"])
    runtime = describe_nmf_runtime(cfg.get("feature_extractor", {}).get("nmf", {}))
    logging.info(
        "NMF runtime requested_backend=%s torch_device=%s torch_dtype=%s",
        runtime["backend"],
        runtime["torch_device"] or "n/a",
        runtime["torch_dtype"] or "n/a",
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
    backend_summary = sorted({str(item.bundle.meta.get("extractor_backend", "")) for item in feature_rows})
    logging.info("Extracted features for %s selected trials.", len(feature_rows))
    logging.info("NMF backends used: %s", ", ".join(backend_summary))
    return context
