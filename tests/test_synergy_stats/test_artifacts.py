"""Artifact helper tests for concatenated provenance exports."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from src.synergy_stats.clustering import SubjectFeatureResult, build_group_exports


def test_group_exports_expand_concatenated_source_trial_windows() -> None:
    """Concatenated exports should contain one source-trial row per source trial."""
    feature_rows = [
        SubjectFeatureResult(
            subject="S01",
            velocity=1,
            trial_num="concat_step",
            bundle=SimpleNamespace(
                W_muscle=np.array([[1.0], [0.0]], dtype=np.float32),
                H_time=np.array([[1.0], [2.0]], dtype=np.float32),
                meta={
                    "status": "ok",
                    "n_components": 1,
                    "vaf": 0.95,
                    "aggregation_mode": "concatenated",
                    "analysis_unit_id": "S01_v1_step_concat",
                    "source_trial_nums_csv": "1|3",
                    "analysis_source_trial_count": 2,
                    "analysis_step_class": "step",
                    "analysis_is_step": True,
                    "analysis_is_nonstep": False,
                    "source_trial_details": [
                        {
                            "source_trial_num": 1,
                            "source_trial_order": 1,
                            "source_step_class": "step",
                            "analysis_window_source": "actual_step_onset",
                            "analysis_window_start": 100.0,
                            "analysis_window_end": 180.0,
                            "analysis_window_length": 80,
                            "analysis_window_is_surrogate": False,
                        },
                        {
                            "source_trial_num": 3,
                            "source_trial_order": 2,
                            "source_step_class": "step",
                            "analysis_window_source": "actual_step_onset",
                            "analysis_window_start": 110.0,
                            "analysis_window_end": 190.0,
                            "analysis_window_length": 80,
                            "analysis_window_is_surrogate": False,
                        },
                    ],
                },
            ),
        )
    ]
    cluster_result = {
        "status": "success",
        "group_id": "pooled_step_nonstep",
        "n_clusters": 1,
        "labels": np.array([0], dtype=np.int32),
        "sample_map": [
            {
                "group_id": "pooled_step_nonstep",
                "subject": "S01",
                "velocity": 1,
                "trial_num": "concat_step",
                "component_index": 0,
                "trial_key": ("S01", 1, "concat_step"),
                "trial_id": "S01_v1_Tconcat_step",
            }
        ],
    }

    exports = build_group_exports(
        group_id="pooled_step_nonstep",
        feature_rows=feature_rows,
        cluster_result=cluster_result,
        muscle_names=["TA", "MG"],
        target_windows=10,
    )

    source_trial_windows = exports["source_trial_windows"]
    assert source_trial_windows.shape[0] == 2
    assert {
        "group_id",
        "subject",
        "velocity",
        "trial_num",
        "analysis_unit_id",
        "source_trial_num",
        "source_trial_order",
        "source_step_class",
        "analysis_window_source",
        "analysis_window_start",
        "analysis_window_end",
        "analysis_window_length",
        "analysis_window_is_surrogate",
    }.issubset(set(source_trial_windows.columns))
    assert source_trial_windows["analysis_unit_id"].nunique() == 1
    assert source_trial_windows["source_trial_num"].tolist() == [1, 3]
