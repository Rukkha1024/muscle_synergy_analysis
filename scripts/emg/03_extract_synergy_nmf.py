"""Extract NMF features for each trial slice."""

from __future__ import annotations

import logging
from collections import defaultdict

from src.synergy_stats.clustering import SubjectFeatureResult
from src.synergy_stats.nmf import extract_trial_features


def run(context: dict) -> dict:
    cfg = context["config"]
    muscle_names = list(cfg["muscles"]["names"])
    feature_rows = defaultdict(list)
    for trial in context["trial_records"]:
        X_trial = trial.frame[muscle_names].to_numpy(dtype="float32")
        bundle = extract_trial_features(X_trial, cfg)
        feature_rows[trial.key[0]].append(
            SubjectFeatureResult(
                subject=trial.key[0],
                velocity=trial.key[1],
                trial_num=trial.key[2],
                bundle=bundle,
            )
        )
    context["feature_rows"] = dict(feature_rows)
    logging.info("Extracted features for %s subjects.", len(feature_rows))
    return context
