"""Tests for figure-only rerendering from saved EMG run artifacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import src.synergy_stats.figure_rerender as figure_rerender_module
from src.synergy_stats.figure_rerender import render_figures_from_run_dir
from tests.helpers import repo_python


def _write_csv(rows: list[dict[str, object]], path: Path) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _sample_cfg() -> dict[str, object]:
    return {
        "muscles": {"names": ["M1", "M2"]},
        "figures": {"format": "png", "dpi": 120},
        "cross_group_w_similarity": {"enabled": True, "threshold": 0.8, "output_figures": True},
    }


def _write_minimal_run_artifacts(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        [
            {"group_id": "global_step", "cluster_id": 0, "muscle": "M1", "W_value": 1.0},
            {"group_id": "global_step", "cluster_id": 0, "muscle": "M2", "W_value": 0.0},
            {"group_id": "global_nonstep", "cluster_id": 0, "muscle": "M1", "W_value": 0.9},
            {"group_id": "global_nonstep", "cluster_id": 0, "muscle": "M2", "W_value": 0.1},
        ],
        run_dir / "all_representative_W_posthoc.csv",
    )
    _write_csv(
        [
            {"group_id": "global_step", "cluster_id": 0, "frame_idx": 0, "h_value": 0.1},
            {"group_id": "global_step", "cluster_id": 0, "frame_idx": 1, "h_value": 0.5},
            {"group_id": "global_step", "cluster_id": 0, "frame_idx": 2, "h_value": 0.2},
            {"group_id": "global_nonstep", "cluster_id": 0, "frame_idx": 0, "h_value": 0.2},
            {"group_id": "global_nonstep", "cluster_id": 0, "frame_idx": 1, "h_value": 0.4},
            {"group_id": "global_nonstep", "cluster_id": 0, "frame_idx": 2, "h_value": 0.3},
        ],
        run_dir / "all_representative_H_posthoc_long.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_minimal_units_W.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_minimal_units_H_long.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_cluster_labels.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_trial_window_metadata.csv",
    )
    _write_csv(
        [
            {
                "step_cluster_id": 0,
                "nonstep_cluster_id": 0,
                "cosine_similarity": 0.95,
                "selected_in_assignment": True,
                "passes_threshold": True,
                "match_id": "same_synergy_01",
            }
        ],
        run_dir / "cross_group_w_pairwise_cosine.csv",
    )
    _write_csv(
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
        ],
        run_dir / "cross_group_w_cluster_decision.csv",
    )


def _write_minimal_pooled_run_artifacts(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        [
            {"group_id": "pooled_step_nonstep", "cluster_id": 0, "muscle": "M1", "W_value": 1.0},
            {"group_id": "pooled_step_nonstep", "cluster_id": 0, "muscle": "M2", "W_value": 0.0},
        ],
        run_dir / "all_representative_W_posthoc.csv",
    )
    _write_csv(
        [
            {"group_id": "pooled_step_nonstep", "cluster_id": 0, "frame_idx": 0, "h_value": 0.1},
            {"group_id": "pooled_step_nonstep", "cluster_id": 0, "frame_idx": 1, "h_value": 0.5},
            {"group_id": "pooled_step_nonstep", "cluster_id": 0, "frame_idx": 2, "h_value": 0.2},
        ],
        run_dir / "all_representative_H_posthoc_long.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_minimal_units_W.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_minimal_units_H_long.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_cluster_labels.csv",
    )
    _write_csv(
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
        ],
        run_dir / "all_trial_window_metadata.csv",
    )


def _write_minimal_global_config(config_root: Path) -> Path:
    config_root.mkdir(parents=True, exist_ok=True)
    global_config = config_root / "global_config.yaml"
    emg_pipeline_config = config_root / "emg_pipeline_config.yaml"
    synergy_stats_config = config_root / "synergy_stats_config.yaml"

    global_config.write_text(
        "\n".join(
            [
                "runtime:",
                "  output_dir: outputs/runs/default_run",
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
    """A missing source CSV should fail before the existing figures tree is replaced."""
    run_dir = tmp_path / "run"
    _write_minimal_run_artifacts(run_dir)
    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True)
    original_path = figures_dir / "sentinel.txt"
    original_path.write_text("keep-me", encoding="utf-8-sig")
    (run_dir / "all_cluster_labels.csv").unlink()

    try:
        render_figures_from_run_dir(run_dir, _sample_cfg())
    except FileNotFoundError as exc:
        assert "all_cluster_labels.csv" in str(exc)
    else:
        raise AssertionError("Expected rerender to fail when a required CSV is missing.")

    assert original_path.read_text(encoding="utf-8-sig") == "keep-me"
    assert not (run_dir / "figures.__tmp__").exists()


def test_rerender_rebuilds_expected_figure_tree(tmp_path: Path) -> None:
    """Saved CSV artifacts should be sufficient to recreate the full figures tree."""
    run_dir = tmp_path / "run"
    _write_minimal_run_artifacts(run_dir)
    stale_dir = run_dir / "figures"
    stale_dir.mkdir(parents=True)
    (stale_dir / "obsolete.txt").write_text("old", encoding="utf-8-sig")

    rendered = render_figures_from_run_dir(run_dir, _sample_cfg())

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


def test_rerender_cleans_staging_dir_when_plotting_fails(tmp_path: Path, monkeypatch) -> None:
    """A mid-render plotting failure should not leave the staging directory behind."""
    run_dir = tmp_path / "run"
    _write_minimal_run_artifacts(run_dir)

    def _boom(*args, **kwargs):
        raise RuntimeError("plot failed")

    monkeypatch.setattr(figure_rerender_module, "save_group_cluster_figure", _boom)

    try:
        render_figures_from_run_dir(run_dir, _sample_cfg())
    except RuntimeError as exc:
        assert "plot failed" in str(exc)
    else:
        raise AssertionError("Expected rerender to surface the plotting failure.")

    assert not (run_dir / "figures.__tmp__").exists()
    assert not (run_dir / "figures.__bak__").exists()


def test_rerender_pooled_run_skips_cross_group_artifacts(tmp_path: Path) -> None:
    """A pooled run should rerender group and trial figures without split-only files."""
    run_dir = tmp_path / "pooled_run"
    _write_minimal_pooled_run_artifacts(run_dir)

    rendered = render_figures_from_run_dir(run_dir, _sample_cfg())

    figure_dir = run_dir / "figures"
    assert len(rendered["group_figure_paths"]) == 1
    assert len(rendered["trial_figure_paths"]) == 2
    assert len(rendered["cross_group_figure_paths"]) == 0
    assert (figure_dir / "pooled_step_nonstep_clusters.png").exists()
    assert not (figure_dir / "cross_group_cosine_heatmap.png").exists()
    assert len(list((figure_dir / "nmf_trials").glob("*.png"))) == 2


def test_rerender_split_run_still_fails_when_cross_group_csv_is_missing(tmp_path: Path) -> None:
    """Legacy split rerender should fail fast on an incomplete cross-group artifact set."""
    run_dir = tmp_path / "split_run_missing_cross_group"
    _write_minimal_run_artifacts(run_dir)
    (run_dir / "cross_group_w_pairwise_cosine.csv").unlink()

    try:
        render_figures_from_run_dir(run_dir, _sample_cfg())
    except FileNotFoundError as exc:
        assert "cross_group_w_pairwise_cosine.csv" in str(exc)
    else:
        raise AssertionError("Expected rerender to fail when a split cross-group CSV is missing.")


def test_cli_rerender_uses_saved_run_artifacts_only(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    """The CLI should rerender figures from saved CSV artifacts without pipeline context files."""
    run_dir = tmp_path / "run"
    config_root = tmp_path / "config"
    _write_minimal_run_artifacts(run_dir)
    global_config = _write_minimal_global_config(config_root)

    result = repo_python(
        repo_root,
        "scripts/emg/06_render_figures_only.py",
        "--run-dir",
        str(run_dir),
        "--config",
        str(global_config),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Rerendered 8 figure(s)" in result.stdout
    assert not (run_dir / "run_manifest.json").exists()
    assert (run_dir / "figures" / "global_step_clusters.png").exists()
    assert len(list((run_dir / "figures" / "nmf_trials").glob("*.png"))) == 2
