"""End-to-end contract tests for global and trial-level synergy artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from tests.helpers import read_final_parquet, repo_python


def test_fixture_run_writes_global_group_artifacts(
    repo_root: Path,
    fixture_bundle: dict[str, object],
    tmp_path: Path,
) -> None:
    """The fixture pipeline should emit global clusters plus trial-level NMF figures."""

    main_path = repo_root / "main.py"
    if not main_path.exists():
        pytest.xfail("main.py is not implemented yet; end-to-end contract is staged.")

    run_dir = tmp_path / "fixture_run"
    result = repo_python(
        repo_root,
        "main.py",
        "--config",
        str(fixture_bundle["global_config"]),
        "--out",
        str(run_dir),
        "--overwrite",
        timeout=180,
    )
    if result.returncode != 0:
        pytest.fail(
            "Fixture run failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    final_parquet = repo_root / "outputs" / "final.parquet"
    manifest_path = run_dir / "run_manifest.json"
    trial_window_metadata = run_dir / "all_trial_window_metadata.csv"
    summary_path = run_dir / "final_summary.csv"
    step_figure = run_dir / "figures" / "global_step_clusters.png"
    nonstep_figure = run_dir / "figures" / "global_nonstep_clusters.png"
    trial_figure_dir = run_dir / "figures" / "nmf_trials"
    step_labels = run_dir / "global_step" / "cluster_labels.csv"
    nonstep_labels = run_dir / "global_nonstep" / "cluster_labels.csv"
    step_metadata = run_dir / "global_step" / "clustering_metadata.csv"
    nonstep_metadata = run_dir / "global_nonstep" / "clustering_metadata.csv"

    assert manifest_path.exists()
    assert summary_path.exists()
    assert trial_window_metadata.exists()
    assert step_figure.exists()
    assert nonstep_figure.exists()
    assert trial_figure_dir.exists()
    assert step_labels.exists()
    assert nonstep_labels.exists()
    assert step_metadata.exists()
    assert nonstep_metadata.exists()
    assert not (run_dir / "figures" / "overview_all_subject_clusters.png").exists()
    assert not list(run_dir.glob("subject_*"))

    final_df = read_final_parquet(final_parquet)
    assert {"group_id", "subject", "velocity", "trial_num"}.issubset(set(final_df.columns))
    assert set(final_df["velocity"].unique().to_list()) == {1}

    summary_df = pd.read_csv(summary_path, encoding="utf-8-sig")
    assert summary_df.shape[0] == 2
    assert set(summary_df["group_id"].tolist()) == {"global_step", "global_nonstep"}
    assert set(summary_df["status"].tolist()) == {"success"}

    labels_df = pl.read_csv(run_dir / "all_cluster_labels.csv", encoding="utf8-lossy")
    assert set(labels_df.get_column("group_id").unique().to_list()) == {"global_step", "global_nonstep"}
    assert labels_df.get_column("analysis_selected_group").cast(pl.Boolean).all()

    metadata_df = pl.read_csv(run_dir / "all_clustering_metadata.csv", encoding="utf8-lossy")
    assert set(metadata_df.get_column("selection_method").unique().to_list()) == {"gap_statistic"}
    assert metadata_df.get_column("selection_status").is_in(
        ["success_gap_unique", "success_gap_escalated_unique"]
    ).all()
    assert metadata_df.get_column("k_gap_raw").cast(pl.Int64).min() >= 2
    assert metadata_df.filter(pl.col("k_selected").cast(pl.Int64) < pl.col("k_gap_raw").cast(pl.Int64)).is_empty()
    assert metadata_df.get_column("uniqueness_candidate_restarts").cast(pl.Int64).min() > 0
    assert metadata_df.get_column("feasible_objective_by_k_json").str.len_chars().min() > 0
    assert metadata_df.get_column("duplicate_trial_count_by_k_json").str.len_chars().min() > 0
    for payload in metadata_df.get_column("feasible_objective_by_k_json").to_list():
        parsed = json.loads(payload)
        assert isinstance(parsed, dict)
    for payload in metadata_df.get_column("duplicate_trial_count_by_k_json").to_list():
        parsed = json.loads(payload)
        assert isinstance(parsed, dict)

    step_df = labels_df.filter(pl.col("group_id") == "global_step")
    nonstep_df = labels_df.filter(pl.col("group_id") == "global_nonstep")
    assert step_df.height > 0
    assert nonstep_df.height > 0
    assert step_df.get_column("analysis_is_step").cast(pl.Boolean).all()
    assert not step_df.get_column("analysis_is_nonstep").cast(pl.Boolean).any()
    assert nonstep_df.get_column("analysis_is_nonstep").cast(pl.Boolean).all()
    assert not nonstep_df.get_column("analysis_is_step").cast(pl.Boolean).any()

    window_df = pd.read_csv(trial_window_metadata, encoding="utf-8-sig")
    assert set(window_df["analysis_window_source"].unique()) == {"actual_step_onset", "subject_mean_step_onset"}
    assert window_df["analysis_window_is_surrogate"].astype(str).str.lower().eq("true").any()

    trial_figures = sorted(trial_figure_dir.glob("*.png"))
    assert len(trial_figures) == window_df["trial_id"].nunique()
    assert all("_v" in path.name and "_T" in path.name for path in trial_figures)
    assert all(path.stem.endswith(("_step_nmf", "_nonstep_nmf")) for path in trial_figures)
