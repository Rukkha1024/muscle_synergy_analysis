"""Small end-to-end artifact contract tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.helpers import read_final_parquet, repo_python


def test_fixture_run_writes_expected_artifacts(
    repo_root: Path,
    fixture_bundle: dict[str, object],
    tmp_path: Path,
) -> None:
    """The main pipeline should emit final parquet and run metadata for fixtures."""
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
    subject_figure = run_dir / "figures" / "subject_S01_clusters.png"
    overview_figure = run_dir / "figures" / "overview_all_subject_clusters.png"
    assert manifest_path.exists()
    assert trial_window_metadata.exists()
    assert subject_figure.exists()
    assert overview_figure.exists()
    final_df = read_final_parquet(final_parquet)
    assert {"subject", "velocity", "trial_num"}.issubset(set(final_df.columns))
    assert set(final_df["velocity"].unique().to_list()) == {1}

    window_df = pd.read_csv(trial_window_metadata, encoding="utf-8-sig")
    assert set(window_df["analysis_window_source"].unique()) == {"step_onset", "subject_velocity_mean_step_onset"}
    assert window_df["analysis_window_is_surrogate"].astype(str).str.lower().eq("true").any()
