"""Clustering contract tests for global step and nonstep groups."""

from __future__ import annotations

import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest

from tests.helpers import resolve_callable


def _sample_w_list() -> tuple[list[np.ndarray], list[tuple[str, int, int]]]:
    """Build per-trial W matrices with clear cross-trial cluster families."""
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    c = np.array([0.9, 0.1, 0.0], dtype=np.float32)
    d = np.array([0.1, 0.9, 0.0], dtype=np.float32)
    w_list = [
        np.stack([a, b], axis=1),
        np.stack([c, d], axis=1),
        np.stack([a, d], axis=1),
    ]
    trial_keys = [("S01", 1, 1), ("S01", 1, 2), ("S02", 1, 1)]
    return w_list, trial_keys


def _load_group_helpers():
    try:
        cluster_func, _, _ = resolve_callable(
            ["src.synergy_stats", "src.synergy_stats.clustering"],
            ["cluster_feature_group"],
        )
        export_func, _, _ = resolve_callable(
            ["src.synergy_stats.clustering"],
            ["build_group_exports"],
        )
        result_cls, _, _ = resolve_callable(
            ["src.synergy_stats.clustering"],
            ["SubjectFeatureResult"],
        )
    except LookupError as exc:
        pytest.xfail(f"Global clustering helpers are not implemented yet: {exc}")
    return cluster_func, export_func, result_cls


def _load_cluster_stage_run(repo_root):
    module_path = repo_root / "scripts" / "emg" / "04_cluster_synergies.py"
    spec = importlib.util.spec_from_file_location("cluster_synergies_stage", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load clustering stage module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def _make_feature_rows(group_kind: str):
    cluster_func, export_func, result_cls = _load_group_helpers()
    w_list, trial_keys = _sample_w_list()
    feature_rows = []
    for (subject, velocity, trial_num), W in zip(trial_keys, w_list):
        meta = {
            "analysis_selected_group": True,
            "analysis_step_class": group_kind,
            "analysis_is_step": group_kind == "step",
            "analysis_is_nonstep": group_kind == "nonstep",
        }
        feature_rows.append(
            result_cls(
                subject=subject,
                velocity=velocity,
                trial_num=trial_num,
                bundle=SimpleNamespace(
                    W_muscle=W,
                    H_time=np.tile(np.array([[1.0, 0.5]], dtype=np.float32), (6, 1)),
                    meta=meta,
                ),
            )
        )
    return cluster_func, export_func, feature_rows


def test_global_step_group_returns_zero_duplicate_solution() -> None:
    """Global step clustering should preserve zero duplicate assignments."""
    cluster_func, export_func, feature_rows = _make_feature_rows("step")
    cfg = {
        "algorithm": "sklearn_kmeans",
        "max_clusters": 4,
        "max_iter": 50,
        "repeats": 5,
        "random_state": 7,
        "disallow_within_trial_duplicate_assignment": True,
    }
    result = cluster_func(feature_rows, cfg, "global_step")
    exports = export_func("global_step", feature_rows, result, ["M1", "M2", "M3"], 10)
    assert result.get("status") == "success"
    assert result.get("group_id") == "global_step"
    assert len(result.get("duplicate_trials", [])) == 0
    assert exports["labels"]["group_id"].eq("global_step").all()
    assert exports["labels"]["analysis_is_step"].astype(bool).all()
    assert not exports["labels"]["analysis_is_nonstep"].astype(bool).any()


def test_global_nonstep_group_returns_zero_duplicate_solution() -> None:
    """Global nonstep clustering should preserve zero duplicate assignments."""
    cluster_func, export_func, feature_rows = _make_feature_rows("nonstep")
    cfg = {
        "algorithm": "sklearn_kmeans",
        "max_clusters": 4,
        "max_iter": 50,
        "repeats": 5,
        "random_state": 7,
        "disallow_within_trial_duplicate_assignment": True,
    }
    result = cluster_func(feature_rows, cfg, "global_nonstep")
    exports = export_func("global_nonstep", feature_rows, result, ["M1", "M2", "M3"], 10)
    assert result.get("status") == "success"
    assert result.get("group_id") == "global_nonstep"
    assert len(result.get("duplicate_trials", [])) == 0
    assert exports["labels"]["group_id"].eq("global_nonstep").all()
    assert exports["labels"]["analysis_is_nonstep"].astype(bool).all()
    assert not exports["labels"]["analysis_is_step"].astype(bool).any()


def test_group_exports_include_group_summary_schema() -> None:
    """Group exports should expose group_id-driven summary and label schema."""
    cluster_func, export_func, feature_rows = _make_feature_rows("step")
    cfg = {
        "algorithm": "sklearn_kmeans",
        "max_clusters": 4,
        "max_iter": 50,
        "repeats": 5,
        "random_state": 7,
        "disallow_within_trial_duplicate_assignment": True,
    }
    result = cluster_func(feature_rows, cfg, "global_step")
    exports = export_func("global_step", feature_rows, result, ["M1", "M2", "M3"], 10)
    metadata_columns = set(exports["metadata"].columns)
    label_columns = set(exports["labels"].columns)
    assert {"group_id", "status", "n_trials", "n_components", "n_clusters", "algorithm_used"}.issubset(metadata_columns)
    assert {"group_id", "subject", "velocity", "trial_num", "component_index", "cluster_id"}.issubset(label_columns)


@pytest.mark.parametrize(
    ("is_step", "is_nonstep"),
    [
        (True, True),
        (False, False),
    ],
)
def test_cluster_stage_rejects_selected_trials_without_exactly_one_group(
    repo_root,
    is_step: bool,
    is_nonstep: bool,
) -> None:
    """Selected trials must map to exactly one global target group."""
    _, _, result_cls = _load_group_helpers()
    run_stage = _load_cluster_stage_run(repo_root)
    feature_rows = [
        result_cls(
            subject="S01",
            velocity=1,
            trial_num=1,
            bundle=SimpleNamespace(
                W_muscle=np.array([[1.0], [0.0], [0.0]], dtype=np.float32),
                H_time=np.array([[1.0]], dtype=np.float32),
                meta={
                    "analysis_selected_group": True,
                    "analysis_is_step": is_step,
                    "analysis_is_nonstep": is_nonstep,
                },
            ),
        )
    ]
    context = {
        "config": {
            "synergy_clustering": {
                "grouping": {"mode": "global_step_nonstep"},
                "algorithm": "sklearn_kmeans",
                "max_clusters": 2,
                "max_iter": 10,
                "repeats": 1,
                "random_state": 7,
                "disallow_within_trial_duplicate_assignment": True,
            }
        },
        "feature_rows": feature_rows,
    }
    with pytest.raises(ValueError, match="exactly one global group"):
        run_stage(context)


def test_cluster_intra_subject_compatibility_wrapper_still_returns_success() -> None:
    """The public compatibility wrapper should remain callable for legacy imports."""
    try:
        cluster_func, _, _ = resolve_callable(
            ["src.synergy_stats", "src.synergy_stats.clustering"],
            ["cluster_intra_subject"],
        )
    except LookupError as exc:
        pytest.xfail(f"Compatibility clustering wrapper is not implemented yet: {exc}")
    w_list, trial_keys = _sample_w_list()
    cfg = {
        "algorithm": "sklearn_kmeans",
        "max_clusters": 4,
        "max_iter": 50,
        "repeats": 5,
        "random_state": 7,
        "disallow_within_trial_duplicate_assignment": True,
    }
    result = cluster_func(w_list, trial_keys, cfg)
    assert result.get("status") == "success"
    assert result.get("group_id") == "compatibility_group"
    assert len(result.get("duplicate_trials", [])) == 0
