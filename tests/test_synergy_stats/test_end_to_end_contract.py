"""End-to-end contract tests for mode-separated synergy artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook
import pandas as pd
import polars as pl
import pytest
import yaml

from tests.helpers import read_final_parquet, repo_python


def _write_mode_test_configs(
    fixture_bundle: dict[str, object],
    tmp_path: Path,
    *,
    mode: str,
) -> tuple[Path, Path]:
    synergy_cfg_path = tmp_path / f"synergy_stats_{mode}.yaml"
    synergy_cfg_path.write_text(
        "\n".join(
            [
                "feature_extractor:",
                "  type: nmf",
                "  nmf:",
                "    backend: sklearn_nmf",
                "    vaf_threshold: 0.9",
                "    max_components_to_try: 4",
                "    fit_params:",
                "      max_iter: 1000",
                "      tol: 0.0001",
                "synergy_analysis:",
                f"  mode: {mode}",
                "synergy_clustering:",
                "  algorithm: sklearn_kmeans",
                "  selection_method: gap_statistic",
                "  require_zero_duplicate_solution: true",
                "  duplicate_resolution: none",
                "  max_clusters: 4",
                "  max_iter: 100",
                "  repeats: 10",
                "  gap_ref_n: 5",
                "  gap_ref_restarts: 3",
                "  uniqueness_candidate_restarts: 10",
                "  random_state: 7",
                "  representative:",
                "    h_output_interpolation:",
                "      target_windows: 100",
                "figures:",
                "  format: png",
                "  dpi: 120",
                "  overview_columns: 2",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )

    fixture_global_cfg = yaml.safe_load(
        Path(fixture_bundle["global_config"]).read_text(encoding="utf-8-sig")
    )
    event_xlsm_path = tmp_path / f"perturb_inform_equal_length_{mode}.xlsm"
    workbook = load_workbook(Path(fixture_bundle["xlsm"]))
    try:
        sheet = workbook["platform"]
        header_cells = next(sheet.iter_rows(min_row=1, max_row=1))
        header_map = {str(cell.value): cell.column for cell in header_cells}
        for row_idx in range(2, sheet.max_row + 1):
            mixed_value = sheet.cell(row=row_idx, column=header_map["mixed"]).value
            step_tf = sheet.cell(row=row_idx, column=header_map["step_TF"]).value
            if int(mixed_value or 0) == 1 and str(step_tf).strip().lower() == "step":
                sheet.cell(row=row_idx, column=header_map["step_onset"]).value = 12
        workbook.save(event_xlsm_path)
    finally:
        workbook.close()

    fixture_global_cfg["input"]["event_xlsm_path"] = str(event_xlsm_path)
    fixture_global_cfg["configs"]["synergy_stats"] = str(synergy_cfg_path)
    global_cfg_path = tmp_path / f"global_config_{mode}.yaml"
    global_cfg_path.write_text(
        yaml.safe_dump(fixture_global_cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8-sig",
    )
    return synergy_cfg_path, global_cfg_path


def _run_fixture_mode(
    repo_root: Path,
    fixture_bundle: dict[str, object],
    tmp_path: Path,
    *,
    mode: str,
    run_name: str,
):
    _, global_cfg_path = _write_mode_test_configs(fixture_bundle, tmp_path, mode=mode)
    run_dir = tmp_path / run_name
    result = repo_python(
        repo_root,
        "main.py",
        "--config",
        str(global_cfg_path),
        "--mode",
        mode,
        "--out",
        str(run_dir),
        "--overwrite",
        timeout=180,
    )
    return run_dir, result


def test_both_mode_writes_trialwise_and_concatenated_outputs(
    repo_root: Path,
    fixture_bundle: dict[str, object],
    tmp_path: Path,
) -> None:
    """A both-mode run should emit mode bundles plus combined root artifacts."""

    main_path = repo_root / "main.py"
    if not main_path.exists():
        pytest.xfail("main.py is not implemented yet; end-to-end contract is staged.")

    run_dir, result = _run_fixture_mode(
        repo_root,
        fixture_bundle,
        tmp_path,
        mode="both",
        run_name="fixture_run",
    )
    if result.returncode != 0:
        pytest.fail(
            "Fixture run failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    combined_final_parquet = run_dir / "final.parquet"
    final_parquet_alias = repo_root / "outputs" / "final.parquet"
    final_trialwise_alias = repo_root / "outputs" / "final_trialwise.parquet"
    final_concatenated_alias = repo_root / "outputs" / "final_concatenated.parquet"
    manifest_path = run_dir / "run_manifest.json"
    methods_manifest_path = run_dir / "analysis_methods_manifest.json"
    summary_path = run_dir / "final_summary.csv"
    interpretation_workbook = run_dir / "results_interpretation.xlsx"
    audit_workbook = run_dir / "clustering_audit.xlsx"
    root_source_trial_windows_path = run_dir / "all_concatenated_source_trial_windows.csv"

    assert manifest_path.exists()
    assert methods_manifest_path.exists()
    assert summary_path.exists()
    assert interpretation_workbook.exists()
    assert audit_workbook.exists()
    assert root_source_trial_windows_path.exists()
    assert combined_final_parquet.exists()
    assert final_parquet_alias.exists()
    assert final_trialwise_alias.exists()
    assert final_concatenated_alias.exists()
    assert not (run_dir / "cross_group_w_pairwise_cosine.csv").exists()
    assert not (run_dir / "cross_group_w_cluster_decision.csv").exists()
    assert not (run_dir / "figures").exists()

    with manifest_path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    assert manifest["selected_mode"] == "both"
    assert manifest["analysis_modes"] == ["trialwise", "concatenated"]

    with methods_manifest_path.open("r", encoding="utf-8-sig") as handle:
        methods_manifest = json.load(handle)
    assert methods_manifest["analysis_modes"] == ["trialwise", "concatenated"]
    assert set(methods_manifest["modes"]) == {"trialwise", "concatenated"}

    summary_df = pd.read_csv(summary_path, encoding="utf-8-sig")
    assert summary_df.shape[0] == 4
    assert set(summary_df["aggregation_mode"].tolist()) == {"trialwise", "concatenated"}
    assert set(summary_df["group_id"].tolist()) == {"global_step", "global_nonstep"}
    assert set(summary_df["status"].tolist()) == {"success"}

    combined_df = read_final_parquet(combined_final_parquet)
    assert {
        "aggregation_mode",
        "group_id",
        "subject",
        "velocity",
        "trial_num",
        "analysis_unit_id",
        "source_trial_nums_csv",
    }.issubset(set(combined_df.columns))
    assert set(combined_df["aggregation_mode"].unique().to_list()) == {"trialwise", "concatenated"}
    assert combined_df.filter(pl.col("aggregation_mode") == "concatenated").height > 0
    assert set(
        combined_df.filter(pl.col("aggregation_mode") == "concatenated")["trial_num"].unique().to_list()
    ) == {"concat_step", "concat_nonstep"}

    trialwise_df = read_final_parquet(final_trialwise_alias)
    concatenated_df = read_final_parquet(final_concatenated_alias)
    assert set(trialwise_df["aggregation_mode"].unique().to_list()) == {"trialwise"}
    assert set(concatenated_df["aggregation_mode"].unique().to_list()) == {"concatenated"}

    for mode in ("trialwise", "concatenated"):
        mode_dir = run_dir / mode
        assert mode_dir.exists()
        assert (mode_dir / "final.parquet").exists()
        assert (mode_dir / "final_summary.csv").exists()
        assert (mode_dir / "all_cluster_labels.csv").exists()
        assert (mode_dir / "all_clustering_metadata.csv").exists()
        assert (mode_dir / "all_representative_W_posthoc.csv").exists()
        assert (mode_dir / "all_representative_H_posthoc_long.csv").exists()
        assert (mode_dir / "all_minimal_units_W.csv").exists()
        assert (mode_dir / "all_minimal_units_H_long.csv").exists()
        assert (mode_dir / "all_trial_window_metadata.csv").exists()
        if mode == "concatenated":
            assert (mode_dir / "all_concatenated_source_trial_windows.csv").exists()
        else:
            assert not (mode_dir / "all_concatenated_source_trial_windows.csv").exists()
        assert (mode_dir / "clustering_audit.xlsx").exists()
        assert (mode_dir / "results_interpretation.xlsx").exists()
        assert (mode_dir / "cross_group_w_pairwise_cosine.csv").exists()
        assert (mode_dir / "cross_group_w_cluster_decision.csv").exists()
        assert (mode_dir / "figures" / "global_step_clusters.png").exists()
        assert (mode_dir / "figures" / "global_nonstep_clusters.png").exists()
        assert (mode_dir / "figures" / "cross_group_cosine_heatmap.png").exists()
        assert (mode_dir / "figures" / "cross_group_matched_w.png").exists()
        assert (mode_dir / "figures" / "cross_group_matched_h.png").exists()
        assert (mode_dir / "figures" / "cross_group_decision_summary.png").exists()

    concatenated_labels = pl.read_csv(
        run_dir / "concatenated" / "all_cluster_labels.csv",
        encoding="utf8-lossy",
    )
    assert concatenated_labels.height > 0
    assert set(concatenated_labels["trial_num"].unique().to_list()) == {"concat_step", "concat_nonstep"}
    assert set(concatenated_labels["aggregation_mode"].unique().to_list()) == {"concatenated"}

    root_source_trial_windows = pl.read_csv(root_source_trial_windows_path, encoding="utf8-lossy")
    assert root_source_trial_windows.height > 0
    assert set(root_source_trial_windows["aggregation_mode"].unique().to_list()) == {"concatenated"}
    assert {
        "analysis_unit_id",
        "trial_num",
        "source_trial_num",
        "analysis_window_source",
        "analysis_window_start",
        "analysis_window_end",
        "analysis_window_length",
        "analysis_window_is_surrogate",
    }.issubset(set(root_source_trial_windows.columns))
    assert root_source_trial_windows.group_by("analysis_unit_id").len()["len"].max() >= 2

    root_book = load_workbook(interpretation_workbook)
    try:
        assert {
            "summary",
            "clustering_meta",
            "trial_windows",
            "cluster_labels",
            "representative_W",
            "representative_H",
            "minimal_W",
            "minimal_H",
            "table_guide",
        }.issubset(set(root_book.sheetnames))
        assert "cross_group_pairwise" not in root_book.sheetnames
    finally:
        root_book.close()


def test_trialwise_only_run_does_not_write_concatenated_source_trial_manifest(
    repo_root: Path,
    fixture_bundle: dict[str, object],
    tmp_path: Path,
) -> None:
    """A trialwise-only run should not emit the concatenated-only provenance file."""
    main_path = repo_root / "main.py"
    if not main_path.exists():
        pytest.xfail("main.py is not implemented yet; end-to-end contract is staged.")

    run_dir, result = _run_fixture_mode(
        repo_root,
        fixture_bundle,
        tmp_path,
        mode="trialwise",
        run_name="fixture_run_trialwise_only",
    )
    if result.returncode != 0:
        pytest.fail(
            "Fixture run failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    assert not (run_dir / "all_concatenated_source_trial_windows.csv").exists()
    assert not (run_dir / "trialwise" / "all_concatenated_source_trial_windows.csv").exists()
