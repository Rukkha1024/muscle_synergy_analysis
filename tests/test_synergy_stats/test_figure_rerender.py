"""Tests for figure-only rerendering from saved single-parquet artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

import src.synergy_stats.figure_rerender as figure_rerender_module
from src.synergy_stats.figure_rerender import render_figures_from_run_dir
from src.synergy_stats.single_parquet import (
    POOLED_CLUSTER_STRATEGY_H_MEANS_KEY,
    POOLED_CLUSTER_STRATEGY_SUMMARY_KEY,
    POOLED_CLUSTER_STRATEGY_W_MEANS_KEY,
    SUMMARY_FRAME_KEY,
    write_single_parquet_bundle,
)
from tests.helpers import repo_python


def _figure_md5_map(figure_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(figure_dir)): hashlib.md5(path.read_bytes()).hexdigest()
        for path in sorted(figure_dir.rglob("*"))
        if path.is_file()
    }


def _sample_cfg() -> dict[str, object]:
    return {
        "runtime": {
            "final_parquet_path": "outputs/final.parquet",
            "final_parquet_alias_paths": {
                "trialwise": "outputs/final_trialwise.parquet",
                "concatenated": "outputs/final_concatenated.parquet",
            },
        },
        "muscles": {"names": ["M1", "M2"]},
        "figures": {"format": "png", "dpi": 120},
        "cross_group_w_similarity": {"enabled": True, "threshold": 0.8, "output_figures": True},
    }


def _write_source_parquet(path: Path, *, pooled: bool = False, include_cross_group: bool = True) -> Path:
    if pooled:
        bundle = {
            SUMMARY_FRAME_KEY: pd.DataFrame([{"group_id": "pooled_step_nonstep"}]),
            "rep_W": pd.DataFrame(
                [
                    {"group_id": "pooled_step_nonstep", "cluster_id": 0, "muscle": "M1", "W_value": 1.0},
                    {"group_id": "pooled_step_nonstep", "cluster_id": 0, "muscle": "M2", "W_value": 0.0},
                ]
            ),
            "rep_H_long": pd.DataFrame(
                [
                    {"group_id": "pooled_step_nonstep", "cluster_id": 0, "frame_idx": 0, "h_value": 0.1},
                    {"group_id": "pooled_step_nonstep", "cluster_id": 0, "frame_idx": 1, "h_value": 0.5},
                    {"group_id": "pooled_step_nonstep", "cluster_id": 0, "frame_idx": 2, "h_value": 0.2},
                ]
            ),
            "minimal_W": pd.DataFrame(
                [
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "muscle": "M1",
                        "W_value": 1.0,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "muscle": "M2",
                        "W_value": 0.0,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 2,
                        "trial_id": "S02_v1_T2",
                        "component_index": 0,
                        "muscle": "M1",
                        "W_value": 0.9,
                        "analysis_step_class": "nonstep",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 2,
                        "trial_id": "S02_v1_T2",
                        "component_index": 0,
                        "muscle": "M2",
                        "W_value": 0.1,
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            "minimal_H_long": pd.DataFrame(
                [
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "frame_idx": 0,
                        "h_value": 0.1,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "frame_idx": 1,
                        "h_value": 0.5,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 2,
                        "trial_id": "S02_v1_T2",
                        "component_index": 0,
                        "frame_idx": 0,
                        "h_value": 0.2,
                        "analysis_step_class": "nonstep",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 2,
                        "trial_id": "S02_v1_T2",
                        "component_index": 0,
                        "frame_idx": 1,
                        "h_value": 0.4,
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            "labels": pd.DataFrame(
                [
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "cluster_id": 0,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 2,
                        "trial_id": "S02_v1_T2",
                        "component_index": 0,
                        "cluster_id": 0,
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            "trial_windows": pd.DataFrame(
                [
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 2,
                        "trial_id": "S02_v1_T2",
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            POOLED_CLUSTER_STRATEGY_SUMMARY_KEY: pd.DataFrame(
                [
                    {
                        "group_id": "pooled_step_nonstep",
                        "cluster_id": 0,
                        "strategy_label": "step",
                        "n_rows": 1,
                        "cluster_total_rows": 2,
                        "fraction_within_cluster": 0.5,
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "cluster_id": 0,
                        "strategy_label": "nonstep",
                        "n_rows": 1,
                        "cluster_total_rows": 2,
                        "fraction_within_cluster": 0.5,
                    },
                ]
            ),
            POOLED_CLUSTER_STRATEGY_W_MEANS_KEY: pd.DataFrame(
                [
                    {
                        "group_id": "pooled_step_nonstep",
                        "cluster_id": 0,
                        "strategy_label": "step",
                        "muscle": "M1",
                        "W_mean": 1.0,
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "cluster_id": 0,
                        "strategy_label": "nonstep",
                        "muscle": "M1",
                        "W_mean": 0.9,
                    },
                ]
            ),
            POOLED_CLUSTER_STRATEGY_H_MEANS_KEY: pd.DataFrame(
                [
                    {
                        "group_id": "pooled_step_nonstep",
                        "cluster_id": 0,
                        "strategy_label": "step",
                        "frame_idx": 0,
                        "h_mean": 0.1,
                    },
                    {
                        "group_id": "pooled_step_nonstep",
                        "cluster_id": 0,
                        "strategy_label": "nonstep",
                        "frame_idx": 0,
                        "h_mean": 0.2,
                    },
                ]
            ),
        }
    else:
        bundle = {
            SUMMARY_FRAME_KEY: pd.DataFrame(
                [
                    {"group_id": "global_step"},
                    {"group_id": "global_nonstep"},
                ]
            ),
            "rep_W": pd.DataFrame(
                [
                    {"group_id": "global_step", "cluster_id": 0, "muscle": "M1", "W_value": 1.0},
                    {"group_id": "global_step", "cluster_id": 0, "muscle": "M2", "W_value": 0.0},
                    {"group_id": "global_nonstep", "cluster_id": 0, "muscle": "M1", "W_value": 0.9},
                    {"group_id": "global_nonstep", "cluster_id": 0, "muscle": "M2", "W_value": 0.1},
                ]
            ),
            "rep_H_long": pd.DataFrame(
                [
                    {"group_id": "global_step", "cluster_id": 0, "frame_idx": 0, "h_value": 0.1},
                    {"group_id": "global_step", "cluster_id": 0, "frame_idx": 1, "h_value": 0.5},
                    {"group_id": "global_step", "cluster_id": 0, "frame_idx": 2, "h_value": 0.2},
                    {"group_id": "global_nonstep", "cluster_id": 0, "frame_idx": 0, "h_value": 0.2},
                    {"group_id": "global_nonstep", "cluster_id": 0, "frame_idx": 1, "h_value": 0.4},
                    {"group_id": "global_nonstep", "cluster_id": 0, "frame_idx": 2, "h_value": 0.3},
                ]
            ),
            "minimal_W": pd.DataFrame(
                [
                    {
                        "group_id": "global_step",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "muscle": "M1",
                        "W_value": 1.0,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "global_step",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "muscle": "M2",
                        "W_value": 0.0,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "global_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S02_v1_T1",
                        "component_index": 0,
                        "muscle": "M1",
                        "W_value": 0.9,
                        "analysis_step_class": "nonstep",
                    },
                    {
                        "group_id": "global_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S02_v1_T1",
                        "component_index": 0,
                        "muscle": "M2",
                        "W_value": 0.1,
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            "minimal_H_long": pd.DataFrame(
                [
                    {
                        "group_id": "global_step",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "frame_idx": 0,
                        "h_value": 0.1,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "global_step",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "frame_idx": 1,
                        "h_value": 0.5,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "global_step",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "frame_idx": 2,
                        "h_value": 0.2,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "global_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S02_v1_T1",
                        "component_index": 0,
                        "frame_idx": 0,
                        "h_value": 0.2,
                        "analysis_step_class": "nonstep",
                    },
                    {
                        "group_id": "global_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S02_v1_T1",
                        "component_index": 0,
                        "frame_idx": 1,
                        "h_value": 0.4,
                        "analysis_step_class": "nonstep",
                    },
                    {
                        "group_id": "global_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S02_v1_T1",
                        "component_index": 0,
                        "frame_idx": 2,
                        "h_value": 0.3,
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            "labels": pd.DataFrame(
                [
                    {
                        "group_id": "global_step",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "component_index": 0,
                        "cluster_id": 0,
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "global_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S02_v1_T1",
                        "component_index": 0,
                        "cluster_id": 0,
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            "trial_windows": pd.DataFrame(
                [
                    {
                        "group_id": "global_step",
                        "subject": "S01",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S01_v1_T1",
                        "analysis_step_class": "step",
                    },
                    {
                        "group_id": "global_nonstep",
                        "subject": "S02",
                        "velocity": 1,
                        "trial_num": 1,
                        "trial_id": "S02_v1_T1",
                        "analysis_step_class": "nonstep",
                    },
                ]
            ),
            "cross_group_pairwise": pd.DataFrame(
                [
                    {
                        "step_cluster_id": 0,
                        "nonstep_cluster_id": 0,
                        "cosine_similarity": 0.95,
                        "selected_in_assignment": True,
                        "passes_threshold": True,
                        "match_id": "same_synergy_01",
                    }
                ]
            ),
            "cross_group_decision": pd.DataFrame(
                [
                    {
                        "group_id": "global_step",
                        "cluster_id": 0,
                        "assigned_partner_cluster_id": 0,
                        "assigned_cosine_similarity": 0.95,
                        "final_label": "same_synergy",
                        "match_id": "same_synergy_01",
                    },
                    {
                        "group_id": "global_nonstep",
                        "cluster_id": 0,
                        "assigned_partner_cluster_id": 0,
                        "assigned_cosine_similarity": 0.95,
                        "final_label": "same_synergy",
                        "match_id": "same_synergy_01",
                    },
                ]
            ),
        }
        if not include_cross_group:
            bundle["cross_group_pairwise"] = pd.DataFrame()
            bundle["cross_group_decision"] = pd.DataFrame()
    return write_single_parquet_bundle(bundle, path)


def _write_minimal_global_config(config_root: Path, run_dir: Path) -> Path:
    config_root.mkdir(parents=True, exist_ok=True)
    global_config = config_root / "global_config.yaml"
    emg_pipeline_config = config_root / "emg_pipeline_config.yaml"
    synergy_stats_config = config_root / "synergy_stats_config.yaml"

    global_config.write_text(
        "\n".join(
            [
                "runtime:",
                f"  output_dir: {run_dir}",
                "configs:",
                f"  emg_pipeline: {emg_pipeline_config}",
                f"  synergy_stats: {synergy_stats_config}",
                "",
            ]
        ),
        encoding="utf-8-sig",
    )
    emg_pipeline_config.write_text("{}", encoding="utf-8-sig")
    synergy_stats_config.write_text(
        "\n".join(
            [
                "muscles:",
                "  names:",
                "    - M1",
                "    - M2",
                "figures:",
                "  format: png",
                "  dpi: 120",
                "cross_group_w_similarity:",
                "  enabled: true",
                "  threshold: 0.8",
                "  output_figures: true",
                "",
            ]
        ),
        encoding="utf-8-sig",
    )
    return global_config


def test_rerender_missing_artifact_fails_before_replacing_existing_figures(tmp_path: Path) -> None:
    """A missing source frame should fail before the existing figures tree is replaced."""
    run_dir = tmp_path / "trialwise"
    source_path = _write_source_parquet(tmp_path / "final_trialwise.parquet", include_cross_group=True)
    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True)
    original_path = figures_dir / "sentinel.txt"
    original_path.write_text("keep-me", encoding="utf-8-sig")

    bundle = pd.read_parquet(source_path)
    bundle = bundle.loc[bundle["artifact_kind"].astype(str) != "labels"].copy()
    bundle.to_parquet(source_path, index=False)

    try:
        render_figures_from_run_dir(run_dir, _sample_cfg(), source_parquet_path=source_path)
    except FileNotFoundError as exc:
        assert "labels" in str(exc)
    else:
        raise AssertionError("Expected rerender to fail when a required source frame is missing.")

    assert original_path.read_text(encoding="utf-8-sig") == "keep-me"
    assert not (run_dir / "figures.__tmp__").exists()


def test_rerender_rebuilds_expected_figure_tree(tmp_path: Path) -> None:
    """Saved single-parquet artifacts should recreate the full figures tree."""
    run_dir = tmp_path / "trialwise"
    source_path = _write_source_parquet(tmp_path / "final_trialwise.parquet", include_cross_group=True)
    stale_dir = run_dir / "figures"
    stale_dir.mkdir(parents=True)
    (stale_dir / "obsolete.txt").write_text("old", encoding="utf-8-sig")

    rendered = render_figures_from_run_dir(run_dir, _sample_cfg(), source_parquet_path=source_path)

    figure_dir = run_dir / "figures"
    expected_top_level = {
        "cross_group_cosine_heatmap.png",
        "cross_group_decision_summary.png",
        "cross_group_matched_h.png",
        "cross_group_matched_w.png",
        "global_nonstep_clusters.png",
        "global_step_clusters.png",
    }

    assert len(rendered["group_figure_paths"]) == 2
    assert len(rendered["trial_figure_paths"]) == 2
    assert len(rendered["cross_group_figure_paths"]) == 4
    assert expected_top_level.issubset({path.name for path in figure_dir.iterdir() if path.is_file()})
    assert len(list((figure_dir / "nmf_trials").glob("*.png"))) == 2
    assert not (figure_dir / "obsolete.txt").exists()
    assert all(Path(path).exists() for paths in rendered.values() for path in paths)


def test_rerender_is_byte_stable_for_same_saved_parquet_inputs(tmp_path: Path) -> None:
    """Rerendering twice from the same single parquet should reproduce identical figure bytes."""
    run_dir = tmp_path / "trialwise"
    source_path = _write_source_parquet(tmp_path / "final_trialwise.parquet", include_cross_group=True)

    first_render = render_figures_from_run_dir(run_dir, _sample_cfg(), source_parquet_path=source_path)
    assert sum(len(paths) for paths in first_render.values()) == 8
    figure_dir = run_dir / "figures"
    first_hashes = _figure_md5_map(figure_dir)

    second_render = render_figures_from_run_dir(run_dir, _sample_cfg(), source_parquet_path=source_path)
    assert sum(len(paths) for paths in second_render.values()) == 8
    second_hashes = _figure_md5_map(figure_dir)

    assert second_hashes == first_hashes


def test_rerender_cleans_staging_dir_when_plotting_fails(tmp_path: Path, monkeypatch) -> None:
    """A mid-render plotting failure should not leave the staging directory behind."""
    run_dir = tmp_path / "trialwise"
    source_path = _write_source_parquet(tmp_path / "final_trialwise.parquet", include_cross_group=True)

    def _boom(*args, **kwargs):
        raise RuntimeError("plot failed")

    monkeypatch.setattr(figure_rerender_module, "save_group_cluster_figure", _boom)

    try:
        render_figures_from_run_dir(run_dir, _sample_cfg(), source_parquet_path=source_path)
    except RuntimeError as exc:
        assert "plot failed" in str(exc)
    else:
        raise AssertionError("Expected rerender to surface the plotting failure.")

    assert not (run_dir / "figures.__tmp__").exists()
    assert not (run_dir / "figures.__bak__").exists()


def test_rerender_pooled_run_skips_cross_group_artifacts(tmp_path: Path) -> None:
    """A pooled run should rerender pooled figures without split-only cross-group files."""
    run_dir = tmp_path / "concatenated"
    source_path = _write_source_parquet(tmp_path / "final_concatenated.parquet", pooled=True)

    rendered = render_figures_from_run_dir(run_dir, _sample_cfg(), source_parquet_path=source_path)

    figure_dir = run_dir / "figures"
    assert len(rendered["group_figure_paths"]) == 1
    assert len(rendered["trial_figure_paths"]) == 2
    assert len(rendered["cross_group_figure_paths"]) == 0
    assert (figure_dir / "pooled_step_nonstep_clusters.png").exists()
    assert (figure_dir / "04_pooled_cluster_representatives.png").exists()
    assert not (figure_dir / "cross_group_cosine_heatmap.png").exists()
    assert len(list((figure_dir / "nmf_trials").glob("*.png"))) == 2


def test_rerender_split_run_still_fails_when_cross_group_frame_is_missing(tmp_path: Path) -> None:
    """Split rerender should fail fast on an incomplete cross-group source bundle."""
    run_dir = tmp_path / "trialwise"
    source_path = _write_source_parquet(tmp_path / "final_trialwise.parquet", include_cross_group=False)

    try:
        render_figures_from_run_dir(run_dir, _sample_cfg(), source_parquet_path=source_path)
    except FileNotFoundError as exc:
        assert "cross_group_pairwise" in str(exc)
    else:
        raise AssertionError("Expected rerender to fail when a split cross-group frame is missing.")


def test_cli_rerender_uses_saved_mode_alias_parquet_only(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    """The CLI should rerender mode figures from configured alias parquet files."""
    run_dir = tmp_path / "run"
    trialwise_dir = run_dir / "trialwise"
    trialwise_dir.mkdir(parents=True, exist_ok=True)
    config_root = tmp_path / "config"
    outputs_dir = repo_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    alias_path = outputs_dir / "final_trialwise.parquet"
    backup_bytes = alias_path.read_bytes() if alias_path.exists() else None
    source_path = _write_source_parquet(alias_path, include_cross_group=True)
    global_config = _write_minimal_global_config(config_root, run_dir)

    try:
        result = repo_python(
            repo_root,
            "scripts/emg/06_render_figures_only.py",
            "--run-dir",
            str(run_dir),
            "--config",
            str(global_config),
        )
    finally:
        if backup_bytes is None:
            alias_path.unlink(missing_ok=True)
        else:
            alias_path.write_bytes(backup_bytes)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Rerendered 8 figure(s)" in result.stdout
    assert not (run_dir / "run_manifest.json").exists()
    assert (trialwise_dir / "figures" / "global_step_clusters.png").exists()
    assert len(list((trialwise_dir / "figures" / "nmf_trials").glob("*.png"))) == 2
