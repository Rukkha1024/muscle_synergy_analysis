"""End-to-end contract tests for global step/nonstep artifacts."""

from __future__ import annotations

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
    """The fixture pipeline should emit only global step/nonstep cluster outputs."""

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
    step_labels = run_dir / "global_step" / "cluster_labels.csv"
    nonstep_labels = run_dir / "global_nonstep" / "cluster_labels.csv"

    assert manifest_path.exists()
    assert summary_path.exists()
    assert trial_window_metadata.exists()
    assert step_figure.exists()
    assert nonstep_figure.exists()
    assert step_labels.exists()
    assert nonstep_labels.exists()
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
