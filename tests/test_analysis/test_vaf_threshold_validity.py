"""Tests for the VAF threshold validity analysis extension."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np

from tests.helpers import repo_python


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_compute_local_vaf_marks_low_variance_channels_not_applicable(repo_root: Path) -> None:
    """Near-zero-variance channels should be excluded from local-VAF summaries."""
    helper_module = _load_module(
        "validation_helpers",
        repo_root / "analysis" / "vaf_threshold_sensitivity" / "validation_helpers.py",
    )

    observed = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    reconstructed = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float32)
    result = helper_module.compute_local_vaf(
        observed,
        reconstructed,
        variance_epsilon=1.0e-8,
        channel_names=["TA", "MG"],
        local_vaf_floor=0.75,
    )

    assert result["n_applicable_channels"] == 1
    assert result["n_not_applicable_channels"] == 1
    assert result["channel_rows"][0]["muscle"] == "TA"
    assert result["channel_rows"][0]["local_vaf"] == 0.5
    assert result["channel_rows"][1]["muscle"] == "MG"
    assert result["channel_rows"][1]["status"] == "not_applicable"
    assert result["muscle_pass_rate"] == 0.0
    assert result["all_muscles_pass"] is False


def test_generate_null_trial_preserves_channel_values(repo_root: Path) -> None:
    """Both null generators should keep each channel's values inside the same trial."""
    helper_module = _load_module(
        "validation_helpers",
        repo_root / "analysis" / "vaf_threshold_sensitivity" / "validation_helpers.py",
    )

    observed = np.array(
        [
            [1.0, 4.0],
            [2.0, 5.0],
            [3.0, 6.0],
        ],
        dtype=np.float32,
    )
    rng_shift = np.random.default_rng(7)
    rng_shuffle = np.random.default_rng(11)

    shifted = helper_module.generate_null_trial(observed, "circular_shift", rng_shift)
    shuffled = helper_module.generate_null_trial(observed, "time_shuffle", rng_shuffle)

    assert shifted.shape == observed.shape
    assert shuffled.shape == observed.shape
    assert np.allclose(np.sort(shifted[:, 0]), np.sort(observed[:, 0]))
    assert np.allclose(np.sort(shifted[:, 1]), np.sort(observed[:, 1]))
    assert np.allclose(np.sort(shuffled[:, 0]), np.sort(observed[:, 0]))
    assert np.allclose(np.sort(shuffled[:, 1]), np.sort(observed[:, 1]))


def test_evaluate_local_vaf_keeps_concatenated_two_layer_structure(repo_root: Path) -> None:
    """Observed local-VAF output should preserve both concatenated summary layers."""
    script_module = _load_module(
        "vaf_threshold_validity",
        repo_root / "analysis" / "vaf_threshold_sensitivity" / "analyze_vaf_threshold_validity.py",
    )

    perfect_candidate = script_module.RankCandidate(
        rank=1,
        W_muscle=np.array([[1.0], [0.0]], dtype=np.float32),
        H_time=np.array([[1.0], [2.0]], dtype=np.float32),
        vaf=1.0,
        extractor_backend="sklearn_nmf",
        extractor_torch_device="",
        extractor_torch_dtype="",
    )
    trialwise_unit = script_module.AnalysisUnit(
        mode="trialwise",
        subject="S01",
        velocity=1,
        trial_num=1,
        step_class="step",
        analysis_unit_id="S01_v1_T1",
        x_matrix=np.array([[1.0, 0.0], [2.0, 0.0]], dtype=np.float32),
        source_trials=[
            script_module.SourceTrial(
                subject="S01",
                velocity=1,
                trial_num=1,
                step_class="step",
                matrix=np.array([[1.0, 0.0], [2.0, 0.0]], dtype=np.float32),
                metadata={},
            )
        ],
        candidates=[perfect_candidate],
        elapsed_sec=0.01,
    )
    concatenated_unit = script_module.AnalysisUnit(
        mode="concatenated",
        subject="S01",
        velocity=1,
        trial_num="concat_step",
        step_class="step",
        analysis_unit_id="S01_v1_step_concat",
        x_matrix=np.array([[1.0, 0.0], [2.0, 0.0], [3.0, 0.0], [4.0, 0.0]], dtype=np.float32),
        source_trials=[
            script_module.SourceTrial(
                subject="S01",
                velocity=1,
                trial_num=1,
                step_class="step",
                matrix=np.array([[1.0, 0.0], [2.0, 0.0]], dtype=np.float32),
                metadata={},
            ),
            script_module.SourceTrial(
                subject="S01",
                velocity=1,
                trial_num=2,
                step_class="step",
                matrix=np.array([[3.0, 0.0], [4.0, 0.0]], dtype=np.float32),
                metadata={},
            ),
        ],
        candidates=[
            script_module.RankCandidate(
                rank=1,
                W_muscle=np.array([[1.0], [0.0]], dtype=np.float32),
                H_time=np.array([[1.0], [2.0], [3.0], [4.0]], dtype=np.float32),
                vaf=1.0,
                extractor_backend="sklearn_nmf",
                extractor_torch_device="",
                extractor_torch_dtype="",
            )
        ],
        elapsed_sec=0.01,
    )

    result = script_module.evaluate_local_vaf(
        [trialwise_unit],
        [concatenated_unit],
        thresholds=[0.90],
        muscle_names=["TA", "MG"],
        local_vaf_floor=0.75,
        variance_epsilon=1.0e-8,
    )

    assert result["trialwise_summary"][0]["summary_layer"] == "trial_channel"
    assert len(result["concatenated"]["subject_muscle_channel_summary"]) == 1
    assert len(result["concatenated"]["source_trial_split_summary"]) == 1
    assert result["concatenated"]["subject_muscle_channel_summary"][0]["analysis_unit_count"] == 1
    assert result["concatenated"]["source_trial_split_summary"][0]["analysis_unit_count"] == 2
    assert len(result["concatenated"]["source_trial_split_rows"]) == 4


def test_cli_dry_run_reports_eligibility_counts(
    repo_root: Path,
    fixture_bundle: dict[str, Path],
    tmp_path: Path,
) -> None:
    """The dry-run CLI should print threshold and hold-out eligibility counts."""
    validation_config = tmp_path / "config_validation.yaml"
    validation_config.write_text(
        "\n".join(
            [
                "thresholds:",
                "  - 0.89",
                "  - 0.90",
                "local_vaf_floor: 0.75",
                "variance_epsilon: 1.0e-8",
                "null_methods:",
                "  - circular_shift",
                "null_repeats_screening: 2",
                "null_repeats_exact: 3",
                "holdout_min_trials: 2",
                "seed: 7",
                f"out_dir: {tmp_path / 'artifacts'}",
                "",
            ]
        ),
        encoding="utf-8-sig",
    )

    result = repo_python(
        repo_root,
        "analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py",
        "--config",
        str(fixture_bundle["global_config"]),
        "--validation-config",
        str(validation_config),
        "--dry-run",
        timeout=180,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VAF Threshold Validity" in result.stdout
    assert "Hold-out eligible groups:" in result.stdout
    assert "Thresholds: ['89%', '90%']" in result.stdout
    assert "Dry run complete. Input loading and eligibility checks succeeded." in result.stdout
