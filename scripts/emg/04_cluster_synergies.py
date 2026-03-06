"""Cluster the extracted trial-level synergy vectors per subject."""

from __future__ import annotations

import logging

from src.synergy_stats import cluster_subject_features


def run(context: dict) -> dict:
    cfg = context["config"]
    subject_results = {}
    for subject_id, feature_rows in context["feature_rows"].items():
        cluster_result = cluster_subject_features(feature_rows, cfg["synergy_clustering"])
        subject_results[subject_id] = {
            "feature_rows": feature_rows,
            "cluster_result": cluster_result,
        }
    context["subject_results"] = subject_results
    logging.info("Clustered synergies for %s subjects.", len(subject_results))
    return context
