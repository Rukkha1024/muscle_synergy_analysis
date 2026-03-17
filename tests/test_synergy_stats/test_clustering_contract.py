"""Clustering contract tests for global step and nonstep groups."""

from __future__ import annotations

import importlib.util
from collections import defaultdict
import json
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
        "torch_device",
        "torch_dtype",
        "selection_method",
        "selection_status",
        "k_lb",
        "k_gap_raw",
        "k_selected",
        "k_min_unique",
        "gap_by_k_json",
        "gap_sd_by_k_json",
        "observed_objective_by_k_json",
        "feasible_objective_by_k_json",
        "duplicate_trial_count_by_k_json",
        "uniqueness_candidate_restarts",
    }.issubset(metadata_columns)
    assert {"group_id", "subject", "velocity", "trial_num", "component_index", "cluster_id"}.issubset(label_columns)


def test_torch_kmeans_reports_runtime_metadata() -> None:
    """Torch clustering should surface the selected algorithm and runtime info."""
    try:
        import torch  # noqa: F401
    except Exception:
        pytest.skip("torch is not available in this environment.")

    cluster_func, export_func, feature_rows = _make_feature_rows("step")
    cfg = _cluster_cfg(
        algorithm="torch_kmeans",
        torch_device="cpu",
        torch_dtype="float32",
        torch_restart_batch_size=4,
        gap_reference_batch_size=2,
        repeats=4,
        gap_ref_n=2,
        gap_ref_restarts=2,
        uniqueness_candidate_restarts=4,
    )
    result = cluster_func(feature_rows, cfg, "global_step")
    exports = export_func("global_step", feature_rows, result, ["M1", "M2", "M3"], 10)

    assert result["status"] == "success"
    assert result["algorithm_used"] == "torch_kmeans"
    assert result["torch_device"] == "cpu"
    assert result["torch_dtype"] == "float32"
    assert exports["metadata"]["algorithm_used"].iloc[0] == "torch_kmeans"
    assert exports["metadata"]["torch_device"].iloc[0] == "cpu"
    assert exports["metadata"]["torch_dtype"].iloc[0] == "float32"


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


def test_cluster_stage_clusters_concatenated_mode_without_special_case(repo_root) -> None:
    """Concatenated rows should use the normal global clustering path."""
    run_stage = _load_cluster_stage_run(repo_root)
    _, _, feature_rows = _make_feature_rows("step")
    _, _, nonstep_rows = _make_feature_rows("nonstep")
    context = {
        "config": {
            "synergy_clustering": {
                **_cluster_cfg(max_clusters=4, max_iter=20, repeats=4, gap_ref_n=2, gap_ref_restarts=1),
            }
        },
        "analysis_modes": ["concatenated"],
        "analysis_mode_feature_rows": {
            "concatenated": feature_rows + nonstep_rows,
        },
    }

    updated = run_stage(context)

    assert "analysis_mode_cluster_group_results" in updated
    assert "concatenated" in updated["analysis_mode_cluster_group_results"]
    assert set(updated["analysis_mode_cluster_group_results"]["concatenated"]) == {
        "global_step",
        "global_nonstep",
    }
    assert updated["analysis_mode_cluster_group_results"]["concatenated"]["global_step"]["cluster_result"]["status"] == "success"


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
    monkeypatch.setattr(
        clustering_module,
        "_search_zero_duplicate_candidate_at_k",
        lambda *args, **kwargs: pytest.fail("zero-duplicate sweep should not run"),
    )
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

    def _fake_search_zero_duplicate_candidate_at_k(data, sample_map, n_clusters, cfg, observed_result=None):
        if n_clusters == 2:
            return {
                "best_zero_duplicate_result": None,
                "feasible_objective": np.nan,
                "min_duplicate_trial_count": 3,
                "representative_duplicate_trials": [("S01", 1, 1)],
                "searched_restarts": 5,
            }
        return {
            "best_zero_duplicate_result": {
                "labels": np.array([0, 1, 1, 2, 0, 2], dtype=np.int32),
                "objective": 30.0,
                "algorithm_used": "mock_candidate_kmeans",
            },
            "feasible_objective": 30.0,
            "min_duplicate_trial_count": 0,
            "representative_duplicate_trials": [],
            "searched_restarts": 5,
        }

    monkeypatch.setattr(clustering_module, "compute_gap_statistic", _fake_gap_statistic)
    monkeypatch.setattr(
        clustering_module,
        "_search_zero_duplicate_candidate_at_k",
        _fake_search_zero_duplicate_candidate_at_k,
    )
    cfg = _cluster_cfg(max_clusters=3, max_iter=10, repeats=1, gap_ref_n=2, gap_ref_restarts=1)
    result = clustering_module.cluster_feature_group(feature_rows, cfg, "global_step")

    assert result.get("status") == "success"
    assert result.get("k_gap_raw") == 2
    assert result.get("k_selected") == 3
    assert result.get("n_clusters") == 3
    assert result.get("k_min_unique") == 3
    assert result.get("selection_status") == "success_gap_escalated_unique"
    assert len(result.get("duplicate_trials", [])) == 0
    assert float(result.get("inertia", 0.0)) == pytest.approx(30.0)
    assert result.get("duplicate_trial_count_by_k") == {2: 3, 3: 0}
    assert result.get("duplicate_trial_evidence_by_k", {}).get(2) == []
    assert result.get("duplicate_trial_evidence_by_k", {}).get(3) == []
    assert np.isnan(result.get("feasible_objective_by_k", {}).get(2, np.nan))
    assert result.get("feasible_objective_by_k", {}).get(3) == pytest.approx(30.0)

    trial_clusters = defaultdict(list)
    for sample, label in zip(result.get("sample_map", []), np.asarray(result.get("labels"))):
        trial_clusters[sample["trial_key"]].append(int(label))
    assert trial_clusters
    assert all(len(values) == len(set(values)) for values in trial_clusters.values())


def test_search_zero_duplicate_candidate_prefers_best_feasible_seed_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate search should use deterministic seeds and keep the best feasible objective."""
    import src.synergy_stats.clustering as clustering_module

    _, _, feature_rows = _make_feature_rows("step")
    data, sample_map = clustering_module._stack_weight_vectors(feature_rows, "global_step")
    seen_seeds = []

    def _fake_fit_single_kmeans_candidate(data, n_clusters, seed, cfg):
        seen_seeds.append(seed)
        candidate_map = {
            200007: {
                "labels": np.array([0, 0, 1, 1, 0, 0], dtype=np.int32),
                "objective": 5.0,
                "algorithm_used": "mock_candidate_kmeans",
            },
            200008: {
                "labels": np.array([0, 1, 1, 0, 0, 1], dtype=np.int32),
                "objective": 7.0,
                "algorithm_used": "mock_candidate_kmeans",
            },
            200009: {
                "labels": np.array([1, 0, 0, 1, 1, 0], dtype=np.int32),
                "objective": 6.0,
                "algorithm_used": "mock_candidate_kmeans",
            },
        }
        return candidate_map[seed]

    monkeypatch.setattr(
        clustering_module,
        "_fit_single_kmeans_candidate",
        _fake_fit_single_kmeans_candidate,
    )

    result = clustering_module._search_zero_duplicate_candidate_at_k(
        data,
        sample_map,
        2,
        _cluster_cfg(uniqueness_candidate_restarts=3, random_state=7),
        observed_result=None,
    )

    assert seen_seeds == [200007, 200008, 200009]
    assert result["searched_restarts"] == 3
    assert result["min_duplicate_trial_count"] == 0
    assert result["representative_duplicate_trials"] == []
    assert result["feasible_objective"] == pytest.approx(6.0)
    assert result["best_zero_duplicate_result"]["objective"] == pytest.approx(6.0)
    assert np.array_equal(
        result["best_zero_duplicate_result"]["labels"],
        np.array([1, 0, 0, 1, 1, 0], dtype=np.int32),
    )


def test_search_zero_duplicate_candidate_considers_observed_gap_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observed gap-best results should count as feasible candidates before extra sweeps."""
    import src.synergy_stats.clustering as clustering_module

    _, _, feature_rows = _make_feature_rows("step")
    data, sample_map = clustering_module._stack_weight_vectors(feature_rows, "global_step")

    monkeypatch.setattr(
        clustering_module,
        "_fit_single_kmeans_candidate",
        lambda data, n_clusters, seed, cfg: {
            "labels": np.array([0, 0, 1, 1, 0, 0], dtype=np.int32),
            "objective": 5.0,
            "algorithm_used": "mock_candidate_kmeans",
        },
    )

    observed_result = {
        "labels": np.array([0, 1, 1, 0, 0, 1], dtype=np.int32),
        "objective": 4.0,
        "algorithm_used": "mock_gap_kmeans",
    }
    result = clustering_module._search_zero_duplicate_candidate_at_k(
        data,
        sample_map,
        2,
        _cluster_cfg(uniqueness_candidate_restarts=3, random_state=7),
        observed_result=observed_result,
    )

    assert result["min_duplicate_trial_count"] == 0
    assert result["representative_duplicate_trials"] == []
    assert result["feasible_objective"] == pytest.approx(4.0)
    assert result["best_zero_duplicate_result"]["algorithm_used"] == "mock_gap_kmeans"


def test_gap_selection_rescues_same_k_when_feasible_candidate_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gap raw K should stay fixed when a same-K zero-duplicate candidate exists."""
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

    def _fake_search_zero_duplicate_candidate_at_k(data, sample_map, n_clusters, cfg, observed_result=None):
        if n_clusters == 2:
            return {
                "best_zero_duplicate_result": {
                    "labels": np.array([0, 1, 1, 0, 0, 1], dtype=np.int32),
                    "objective": 20.0,
                    "algorithm_used": "mock_candidate_kmeans",
                },
                "feasible_objective": 20.0,
                "min_duplicate_trial_count": 0,
                "representative_duplicate_trials": [],
                "searched_restarts": 5,
            }
        return {
            "best_zero_duplicate_result": {
                "labels": np.array([0, 1, 1, 2, 0, 2], dtype=np.int32),
                "objective": 30.0,
                "algorithm_used": "mock_candidate_kmeans",
            },
            "feasible_objective": 30.0,
            "min_duplicate_trial_count": 0,
            "representative_duplicate_trials": [],
            "searched_restarts": 5,
        }

    monkeypatch.setattr(clustering_module, "compute_gap_statistic", _fake_gap_statistic)
    monkeypatch.setattr(
        clustering_module,
        "_search_zero_duplicate_candidate_at_k",
        _fake_search_zero_duplicate_candidate_at_k,
    )
    cfg = _cluster_cfg(max_clusters=3, max_iter=10, repeats=1, gap_ref_n=2, gap_ref_restarts=1)
    result = clustering_module.cluster_feature_group(feature_rows, cfg, "global_step")

    assert result.get("status") == "success"
    assert result.get("k_gap_raw") == 2
    assert result.get("k_selected") == 2
    assert result.get("n_clusters") == 2
    assert result.get("k_min_unique") == 2
    assert result.get("selection_status") == "success_gap_unique"
    assert result.get("duplicate_trials") == []
    assert float(result.get("inertia", 0.0)) == pytest.approx(20.0)
    assert result.get("feasible_objective_by_k") == {2: 20.0, 3: 30.0}


def test_gap_selection_fails_when_no_zero_duplicate_solution_exists_at_or_above_gap_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap selection should fail when every candidate K at or above gap K still has duplicates."""
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

    def _fake_search_zero_duplicate_candidate_at_k(data, sample_map, n_clusters, cfg, observed_result=None):
        return {
            "best_zero_duplicate_result": None,
            "feasible_objective": np.nan,
            "min_duplicate_trial_count": 2 if n_clusters == 2 else 1,
            "representative_duplicate_trials": [("S01", 1, 1)],
            "representative_duplicate_evidence": [],
            "searched_restarts": 5,
        }

    monkeypatch.setattr(clustering_module, "compute_gap_statistic", _fake_gap_statistic)
    monkeypatch.setattr(
        clustering_module,
        "_search_zero_duplicate_candidate_at_k",
        _fake_search_zero_duplicate_candidate_at_k,
    )
    result = clustering_module.cluster_feature_group(feature_rows, _cluster_cfg(max_clusters=3), "global_step")

    assert result.get("status") == "failed"
    assert result.get("selection_status") == "failed_no_zero_duplicate_at_or_above_gap_k"
    assert result.get("k_gap_raw") == 2
    assert np.isnan(result.get("k_selected", np.nan))
    assert np.isnan(result.get("k_min_unique", np.nan))
    assert result.get("duplicate_trial_count_by_k") == {2: 2, 3: 1}


def test_cluster_rejects_unsupported_selection_method(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unsupported selection methods should fail before clustering starts."""
    import src.synergy_stats.clustering as clustering_module

    _, _, feature_rows = _make_feature_rows("step")
    monkeypatch.setattr(clustering_module, "compute_gap_statistic", lambda **kwargs: pytest.fail("should not run"))

    with pytest.raises(ValueError, match="Unsupported selection_method"):
        clustering_module.cluster_feature_group(
            feature_rows,
            _cluster_cfg(selection_method="elbow"),
            "global_step",
        )


def test_cluster_main_path_does_not_call_repair_assignment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main clustering path should resolve duplicates through candidate search only."""
    import src.synergy_stats.clustering as clustering_module

    _, _, feature_rows = _make_feature_rows("step")

    def _fake_gap_statistic(*, data, k_values, fit_best_fn, observed_restarts, gap_ref_n, gap_ref_restarts, seed):
        return {
            "selected_k": 2,
            "gap_by_k": {2: 1.5},
            "gap_sd_by_k": {2: 0.1},
            "observed_objective_by_k": {2: 2.0},
            "results_by_k": {
                2: {
                    "labels": np.array([0, 0, 1, 1, 0, 0], dtype=np.int32),
                    "objective": 2.0,
                    "algorithm_used": "mock_kmeans",
                }
            },
        }

    monkeypatch.setattr(clustering_module, "compute_gap_statistic", _fake_gap_statistic)
    monkeypatch.setattr(
        clustering_module,
        "_search_zero_duplicate_candidate_at_k",
        lambda data, sample_map, n_clusters, cfg, observed_result=None: {
            "best_zero_duplicate_result": {
                "labels": np.array([0, 1, 1, 0, 0, 1], dtype=np.int32),
                "objective": 20.0,
                "algorithm_used": "mock_candidate_kmeans",
            },
            "feasible_objective": 20.0,
            "min_duplicate_trial_count": 0,
            "representative_duplicate_trials": [],
            "searched_restarts": 5,
        },
    )

    result = clustering_module.cluster_feature_group(feature_rows, _cluster_cfg(max_clusters=2), "global_step")
    assert result.get("status") == "success"
    assert result.get("duplicate_trials") == []


def test_group_exports_serialize_strict_json_metrics() -> None:
    """Exported metric JSON should stay parseable even when feasible values are missing."""
    cluster_func, export_func, feature_rows = _make_feature_rows("step")
    cfg = _cluster_cfg()
    result = cluster_func(feature_rows, cfg, "global_step")
    result["feasible_objective_by_k"] = {2: np.nan, 3: 1.0}
    exports = export_func("global_step", feature_rows, result, ["M1", "M2", "M3"], 10)

    feasible_payload = exports["metadata"].loc[0, "feasible_objective_by_k_json"]
    parsed = json.loads(feasible_payload)
    assert parsed["2"] is None
    assert parsed["3"] == pytest.approx(1.0)


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


def test_duplicate_trial_evidence_captures_trial_and_cluster_details() -> None:
    """Duplicate evidence should flatten trial-level and cluster-level duplicate structure."""
    import src.synergy_stats.clustering as clustering_module

    _, _, feature_rows = _make_feature_rows("step")
    data, sample_map = clustering_module._stack_weight_vectors(feature_rows, "global_step")
    labels = np.array([0, 0, 1, 1, 0, 0], dtype=np.int32)

    evidence = clustering_module._duplicate_trial_evidence(sample_map, labels)

    assert len(evidence) == 3
    first = evidence[0]
    assert first["trial_id"] == "S01_v1_T1"
    assert first["duplicate_cluster_labels"] == [0]
    assert first["duplicate_component_indexes"] == [0, 1]
    assert first["duplicate_cluster_count"] == 1
    assert first["duplicate_component_count"] == 2
    assert first["duplicate_cluster_details"] == [
        {"cluster_id": 0, "component_indexes": [0, 1], "component_count": 2}
    ]
