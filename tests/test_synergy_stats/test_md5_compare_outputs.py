"""Contract tests for curated MD5 output comparison."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tests.helpers import repo_python


def _load_md5_module(repo_root: Path):
    module_path = repo_root / "scripts" / "emg" / "99_md5_compare_outputs.py"
    spec = importlib.util.spec_from_file_location("md5_compare_outputs", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load MD5 comparison module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_stable_tree(root: Path, stable_paths: set[str]) -> None:
    for relative_path in stable_paths:
        file_path = root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"stable:{relative_path}\n", encoding="utf-8-sig")


def test_md5_compare_passes_when_all_stable_files_match(repo_root: Path, tmp_path: Path) -> None:
    """The MD5 check should pass when every curated stable file exists and matches."""
    md5_module = _load_md5_module(repo_root)
    base_dir = tmp_path / "base"
    new_dir = tmp_path / "new"
    _write_stable_tree(base_dir, md5_module.STABLE_RELATIVE_PATHS)
    _write_stable_tree(new_dir, md5_module.STABLE_RELATIVE_PATHS)

    result = repo_python(
        repo_root,
        "scripts/emg/99_md5_compare_outputs.py",
        "--base",
        str(base_dir),
        "--new",
        str(new_dir),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MD5 comparison passed for curated stable files." in result.stdout


def test_md5_compare_fails_when_same_stable_file_is_missing_from_both_sides(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    """The validator should fail if a required stable file is absent in both trees."""
    md5_module = _load_md5_module(repo_root)
    base_dir = tmp_path / "base"
    new_dir = tmp_path / "new"
    _write_stable_tree(base_dir, md5_module.STABLE_RELATIVE_PATHS)
    _write_stable_tree(new_dir, md5_module.STABLE_RELATIVE_PATHS)
    missing_path = "parquet/all_cluster_labels.parquet"
    (base_dir / missing_path).unlink()
    (new_dir / missing_path).unlink()

    result = repo_python(
        repo_root,
        "scripts/emg/99_md5_compare_outputs.py",
        "--base",
        str(base_dir),
        "--new",
        str(new_dir),
    )
    assert result.returncode == 1
    assert f"MISSING {missing_path}" in result.stdout


def test_md5_compare_ignores_figure_only_differences(repo_root: Path, tmp_path: Path) -> None:
    """Figure-only rerenders should not affect the curated stable MD5 comparison."""
    md5_module = _load_md5_module(repo_root)
    base_dir = tmp_path / "base"
    new_dir = tmp_path / "new"
    _write_stable_tree(base_dir, md5_module.STABLE_RELATIVE_PATHS)
    _write_stable_tree(new_dir, md5_module.STABLE_RELATIVE_PATHS)
    (base_dir / "figures").mkdir(parents=True, exist_ok=True)
    (new_dir / "figures").mkdir(parents=True, exist_ok=True)
    (base_dir / "figures" / "global_step_clusters.png").write_text("old-figure\n", encoding="utf-8-sig")
    (new_dir / "figures" / "global_step_clusters.png").write_text("new-figure\n", encoding="utf-8-sig")

    result = repo_python(
        repo_root,
        "scripts/emg/99_md5_compare_outputs.py",
        "--base",
        str(base_dir),
        "--new",
        str(new_dir),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MD5 comparison passed for curated stable files." in result.stdout


def test_md5_compare_can_optionally_fail_on_figure_only_differences(repo_root: Path, tmp_path: Path) -> None:
    """The optional figure comparison should fail when only figure bytes differ."""
    md5_module = _load_md5_module(repo_root)
    base_dir = tmp_path / "base"
    new_dir = tmp_path / "new"
    _write_stable_tree(base_dir, md5_module.STABLE_RELATIVE_PATHS)
    _write_stable_tree(new_dir, md5_module.STABLE_RELATIVE_PATHS)
    (base_dir / "figures").mkdir(parents=True, exist_ok=True)
    (new_dir / "figures").mkdir(parents=True, exist_ok=True)
    rel_path = Path("figures") / "global_step_clusters.png"
    (base_dir / rel_path).write_text("old-figure\n", encoding="utf-8-sig")
    (new_dir / rel_path).write_text("new-figure\n", encoding="utf-8-sig")

    result = repo_python(
        repo_root,
        "scripts/emg/99_md5_compare_outputs.py",
        "--base",
        str(base_dir),
        "--new",
        str(new_dir),
        "--include-figures",
    )

    assert result.returncode == 1
    assert f"DIFF {rel_path.as_posix()}" in result.stdout
