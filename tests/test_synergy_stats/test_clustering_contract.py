"""Clustering contract tests for global step and nonstep groups."""

from __future__ import annotations

import importlib.util
from collections import defaultdict
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


def _cluster_cfg(**overrides):
    cfg = {
        "algorithm": "sklearn_kmeans",
        "selection_method": "gap_statistic",
        "max_clusters": 4,
        "max_iter": 50,
        "repeats": 5,
        "gap_ref_n": 3,
        "gap_ref_restarts": 2,
        "random_state": 7,
        "disallow_within_trial_duplicate_assignment": True,
        "require_zero_duplicate_solution": True,
        "duplicate_resolution": "none",
    }
    cfg.update(overrides)
    return cfg


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
    cfg = _cluster_cfg()
    result = cluster_func(feature_rows, cfg, "global_step")
    exports = export_func("global_step", feature_rows, result, ["M1", "M2", "M3"], 10)
    assert result.get("status") == "success"
    assert result.get("group_id") == "global_step"
    assert len(result.get("duplicate_trials", [])) == 0
    assert result.get("selection_method") == "gap_statistic"
    assert result.get("selection_status") in {"success_gap_unique", "success_gap_escalated_unique"}
    assert exports["labels"]["group_id"].eq("global_step").all()
    assert exports["labels"]["analysis_is_step"].astype(bool).all()
    assert not exports["labels"]["analysis_is_nonstep"].astype(bool).any()


def test_global_nonstep_group_returns_zero_duplicate_solution() -> None:
    """Global nonstep clustering should preserve zero duplicate assignments."""
    cluster_func, export_func, feature_rows = _make_feature_rows("nonstep")
    cfg = _cluster_cfg()
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
    cfg = _cluster_cfg()
    result = cluster_func(feature_rows, cfg, "global_step")
    exports = export_func("global_step", feature_rows, result, ["M1", "M2", "M3"], 10)
    metadata_columns = set(exports["metadata"].columns)
    label_columns = set(exports["labels"].columns)
    assert {
        "group_id",
        "status",
        "n_trials",
        "n_components",
        "n_clusters",
        "algorithm_used",
        "selection_method",
        "selection_status",
        "k_lb",
        "k_gap_raw",
        "k_selected",
        "k_min_unique",
        "gap_by_k_json",
        "gap_sd_by_k_json",
        "observed_objective_by_k_json",
        "duplicate_trial_count_by_k_json",
    }.issubset(metadata_columns)
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
                **_cluster_cfg(max_clusters=2, max_iter=10, repeats=1, gap_ref_n=2, gap_ref_restarts=1),
            }
        },
        "feature_rows": feature_rows,
    }
    with pytest.raises(ValueError, match="exactly one global group"):
        run_stage(context)


def test_cluster_stage_rejects_legacy_grouping_key(repo_root) -> None:
    """Legacy configs should not include a `synergy_clustering.grouping` section."""
    run_stage = _load_cluster_stage_run(repo_root)
    context = {
        "config": {
            "synergy_clustering": {
                "grouping": {"mode": "global_step_nonstep"},
                **_cluster_cfg(max_clusters=2, max_iter=10, repeats=1, gap_ref_n=2, gap_ref_restarts=1),
            }
        },
        "feature_rows": [],
    }
    with pytest.raises(ValueError, match="grouping` is no longer supported"):
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
    cfg = _cluster_cfg()
    result = cluster_func(w_list, trial_keys, cfg)
    assert result.get("status") == "success"
    assert result.get("group_id") == "compatibility_group"
    assert len(result.get("duplicate_trials", [])) == 0


def test_k_min_starts_from_subject_hmax(monkeypatch: pytest.MonkeyPatch) -> None:
    """K search should start at the global max of per-subject NMF H structures."""
    import src.synergy_stats.clustering as clustering_module

    _, _, result_cls = _load_group_helpers()
    feature_rows = [
        result_cls(
            subject="S01",
            velocity=1,
            trial_num=1,
            bundle=SimpleNamespace(
                W_muscle=np.ones((3, 5), dtype=np.float32),
                H_time=np.ones((10, 5), dtype=np.float32),
                meta={},
            ),
        ),
        result_cls(
            subject="S01",
            velocity=1,
            trial_num=2,
            bundle=SimpleNamespace(
                W_muscle=np.ones((3, 2), dtype=np.float32),
                H_time=np.ones((10, 2), dtype=np.float32),
                meta={},
            ),
        ),
        result_cls(
            subject="S02",
            velocity=1,
            trial_num=1,
            bundle=SimpleNamespace(
                W_muscle=np.ones((3, 3), dtype=np.float32),
                H_time=np.ones((10, 3), dtype=np.float32),
                meta={},
            ),
        ),
    ]
    captured = {}

    def _fake_gap_statistic(*, data, k_values, fit_best_fn, observed_restarts, gap_ref_n, gap_ref_restarts, seed):
        captured["k_values"] = list(k_values)
        labels = np.arange(data.shape[0], dtype=np.int32)
        return {
            "selected_k": int(k_values[0]),
            "gap_by_k": {int(k): float(len(k_values) - idx) for idx, k in enumerate(k_values)},
            "gap_sd_by_k": {int(k): 0.0 for k in k_values},
            "observed_objective_by_k": {int(k): float(k) for k in k_values},
            "results_by_k": {
                int(k): {
                    "labels": labels % int(k),
                    "objective": float(k),
                    "algorithm_used": "mock_kmeans",
                }
                for k in k_values
            },
        }

    monkeypatch.setattr(clustering_module, "compute_gap_statistic", _fake_gap_statistic)
    cfg = _cluster_cfg(max_clusters=6, max_iter=10, repeats=1, require_zero_duplicate_solution=False)
    clustering_module.cluster_feature_group(feature_rows, cfg, "global_step")
    assert captured["k_values"][0] == 5


def test_gap_selection_escalates_to_first_zero_duplicate_solution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gap raw K should be preserved separately from the first feasible zero-duplicate K."""
    import src.synergy_stats.clustering as clustering_module

    _, _, feature_rows = _make_feature_rows("step")

    def _fake_gap_statistic(*, data, k_values, fit_best_fn, observed_restarts, gap_ref_n, gap_ref_restarts, seed):
        labels_k2 = np.array([0, 0, 1, 1, 0, 0], dtype=np.int32)
        labels_k3 = np.array([0, 1, 1, 2, 0, 2], dtype=np.int32)
        return {
            "selected_k": 2,
            "gap_by_k": {2: 1.5, 3: 1.0},
            "gap_sd_by_k": {2: 0.1, 3: 0.1},
            "observed_objective_by_k": {2: 2.0, 3: 3.0},
            "results_by_k": {
                2: {"labels": labels_k2, "objective": 2.0, "algorithm_used": "mock_kmeans"},
                3: {"labels": labels_k3, "objective": 3.0, "algorithm_used": "mock_kmeans"},
            },
        }

    monkeypatch.setattr(clustering_module, "compute_gap_statistic", _fake_gap_statistic)
    cfg = _cluster_cfg(max_clusters=3, max_iter=10, repeats=1, gap_ref_n=2, gap_ref_restarts=1)
    result = clustering_module.cluster_feature_group(feature_rows, cfg, "global_step")

    assert result.get("status") == "success"
    assert result.get("k_gap_raw") == 2
    assert result.get("k_selected") == 3
    assert result.get("n_clusters") == 3
    assert result.get("k_min_unique") == 3
    assert result.get("selection_status") == "success_gap_escalated_unique"
    assert len(result.get("duplicate_trials", [])) == 0
    assert float(result.get("inertia", 0.0)) == pytest.approx(3.0)
    assert result.get("duplicate_trial_count_by_k") == {2: 3, 3: 0}

    trial_clusters = defaultdict(list)
    for sample, label in zip(result.get("sample_map", []), np.asarray(result.get("labels"))):
        trial_clusters[sample["trial_key"]].append(int(label))
    assert trial_clusters
    assert all(len(values) == len(set(values)) for values in trial_clusters.values())


def test_cluster_fails_when_max_clusters_is_lower_than_subject_hmax() -> None:
    """Clustering should fail fast when config max_clusters cannot satisfy subject Hmax k_min."""
    import src.synergy_stats.clustering as clustering_module

    _, _, result_cls = _load_group_helpers()
    feature_rows = [
        result_cls(
            subject="S01",
            velocity=1,
            trial_num=1,
            bundle=SimpleNamespace(
                W_muscle=np.ones((3, 5), dtype=np.float32),
                H_time=np.ones((10, 5), dtype=np.float32),
                meta={},
            ),
        ),
        result_cls(
            subject="S02",
            velocity=1,
            trial_num=1,
            bundle=SimpleNamespace(
                W_muscle=np.ones((3, 2), dtype=np.float32),
                H_time=np.ones((10, 2), dtype=np.float32),
                meta={},
            ),
        ),
    ]
    cfg = _cluster_cfg(max_clusters=4, max_iter=10, repeats=1)
    result = clustering_module.cluster_feature_group(feature_rows, cfg, "global_step")
    assert result.get("status") == "failed"
    assert "Invalid K range" in str(result.get("reason"))


def test_greedy_fallback_assignment_is_deterministic_for_ties() -> None:
    """Fallback assignment should remain deterministic even when costs tie."""
    import src.synergy_stats.clustering as clustering_module

    costs = np.ones((11, 17), dtype=np.float64)
    first = clustering_module._minimum_cost_unique_assignment(costs)
    second = clustering_module._minimum_cost_unique_assignment(costs)

    assert np.array_equal(first, second)
    assert len(set(first.tolist())) == costs.shape[0]
