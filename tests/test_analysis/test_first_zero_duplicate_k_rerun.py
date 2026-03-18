"""Contract tests for the analysis-only first-zero-duplicate K rerun."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

from src.synergy_stats.single_parquet import write_single_parquet_bundle
from tests.helpers import repo_python


def _load_analysis_module(repo_root: Path):
    module_path = repo_root / "analysis" / "first_zero_duplicate_k_rerun" / "analyze_first_zero_duplicate_k_rerun.py"
    spec = importlib.util.spec_from_file_location("first_zero_duplicate_k_rerun", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load analysis module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_minimal_w_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    trials = [
        ("S01", 1.0, 1, [(0, {"M1": 1.0, "M2": 0.0, "M3": 0.0}), (1, {"M1": 0.0, "M2": 1.0, "M3": 0.0})]),
        ("S01", 1.0, 2, [(0, {"M1": 1.0, "M2": 0.0, "M3": 0.0}), (1, {"M1": 0.0, "M2": 0.0, "M3": 1.0})]),
        ("S02", 1.0, 1, [(0, {"M1": 0.0, "M2": 1.0, "M3": 0.0}), (1, {"M1": 0.0, "M2": 0.0, "M3": 1.0})]),
    ]
    for subject, velocity, trial_num, components in trials:
        for component_index, weights in components:
            for muscle, value in weights.items():
                rows.append(
                    {
                        "aggregation_mode": "concatenated",
                        "group_id": "pooled_step_nonstep",
                        "subject": subject,
                        "velocity": velocity,
                        "trial_num": trial_num,
                        "trial_id": f"{subject}_v{velocity}_T{trial_num}",
                        "component_index": component_index,
                        "analysis_unit_id": f"{subject}_v{velocity}_T{trial_num}",
                        "n_components": 2,
                        "status": "ok",
                        "muscle": muscle,
                        "W_value": value,
                    }
                )
    return pd.DataFrame(rows)


def _build_metadata_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "aggregation_mode": "concatenated",
                "group_id": "pooled_step_nonstep",
                "n_trials": 3,
                "n_components": 6,
                "n_clusters": 2,
                "status": "success",
                "selection_method": "gap_statistic",
                "selection_status": "success_gap_unique",
                "k_gap_raw": 2,
                "k_selected": 2,
                "k_min_unique": 3,
                "algorithm_used": "sklearn_kmeans",
                "torch_device": "",
                "torch_dtype": "",
                "random_state": 7,
                "max_iter": 50,
                "uniqueness_candidate_restarts": 25,
                "duplicate_trial_count_by_k_json": json.dumps({"2": 1, "3": 0}, ensure_ascii=False),
            }
        ]
    )


def _build_final_summary_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "aggregation_mode": "concatenated",
                "group_id": "pooled_step_nonstep",
                "n_trials": 3,
                "n_components": 6,
                "n_clusters": 2,
                "status": "success",
                "selection_method": "gap_statistic",
                "selection_status": "success_gap_unique",
                "k_gap_raw": 2,
                "k_selected": 2,
                "k_min_unique": 3,
            }
        ]
    )


def _write_source_bundle(path: Path) -> Path:
    bundle = {
        "minimal_W": _build_minimal_w_frame(),
        "metadata": _build_metadata_frame(),
        "final_summary": _build_final_summary_frame(),
    }
    write_single_parquet_bundle(bundle, path)
    return path


def test_scan_first_zero_duplicate_k_selects_expected_value(repo_root: Path) -> None:
    """Synthetic vectors should first become duplicate-free at K=3."""
    analysis_module = _load_analysis_module(repo_root)
    feature_rows, muscle_names = analysis_module._rebuild_feature_rows(_build_minimal_w_frame(), "pooled_step_nonstep")
    result = analysis_module.scan_first_zero_duplicate_k(
        feature_rows,
        group_id="pooled_step_nonstep",
        cfg={
            "algorithm": "sklearn_kmeans",
            "random_state": 7,
            "max_iter": 50,
            "uniqueness_candidate_restarts": 25,
        },
        k_max=3,
    )

    assert muscle_names == ["M1", "M2", "M3"]
    assert result["k_min"] == 2
    assert result["selected_k"] == 3
    assert [row["duplicate_trial_count"] for row in result["scan_rows"]] == [1, 0]


def test_cli_writes_analysis_artifacts_from_source_bundle(repo_root: Path, tmp_path: Path) -> None:
    """The CLI should load one source parquet and write analysis-scoped outputs."""
    source_path = _write_source_bundle(tmp_path / "final_concatenated.parquet")
    out_dir = tmp_path / "artifacts"

    result = repo_python(
        repo_root,
        "analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py",
        "--source-parquet",
        str(source_path),
        "--out-dir",
        str(out_dir),
        "--algorithm",
        "sklearn_kmeans",
        "--overwrite",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Gap statistic used: False" in result.stdout
    assert "First zero-duplicate K: 3" in result.stdout
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "k_scan.json").exists()
    assert (out_dir / "checksums.md5").exists()
    assert (out_dir / "k_duplicate_burden.png").exists()

    with (out_dir / "summary.json").open("r", encoding="utf-8-sig") as handle:
        summary = json.load(handle)
    assert summary["selection_method"] == "first_zero_duplicate"
    assert summary["k_selected_first_zero_duplicate"] == 3
    assert summary["pipeline_k_gap_raw"] == 2
