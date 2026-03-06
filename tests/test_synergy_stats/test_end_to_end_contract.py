"""Small end-to-end artifact contract tests."""

from __future__ import annotations

from pathlib import Path

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
    assert manifest_path.exists()
    final_df = read_final_parquet(final_parquet)
    assert {"subject", "velocity", "trial_num"}.issubset(set(final_df.columns))
