"""Contract tests for cross-group representative W similarity outputs."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.synergy_stats.cross_group_similarity import (
    annotate_pairwise_assignment,
    build_cluster_decision,
    build_cluster_w_matrix,
    compute_pairwise_cosine,
    solve_assignment,
)
from src.synergy_stats.figures import (
    save_cross_group_decision_summary,
    save_cross_group_heatmap,
    save_cross_group_matched_h,
    save_cross_group_matched_w,
)


def _representative_w_rows(step_vectors: list[tuple[float, float]], nonstep_vectors: list[tuple[float, float]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for group_id, vectors in (("global_step", step_vectors), ("global_nonstep", nonstep_vectors)):
        for cluster_id, (m1, m2) in enumerate(vectors):
            rows.extend(
                [
                    {"group_id": group_id, "cluster_id": cluster_id, "muscle": "M1", "W_value": m1},
                    {"group_id": group_id, "cluster_id": cluster_id, "muscle": "M2", "W_value": m2},
                ]
            )
    return pd.DataFrame(rows)


def _run_similarity(step_vectors: list[tuple[float, float]], nonstep_vectors: list[tuple[float, float]], threshold: float):
    rep_w = _representative_w_rows(step_vectors, nonstep_vectors)
    step_df, nonstep_df = build_cluster_w_matrix(rep_w, ["M1", "M2"])
    pairwise_df = compute_pairwise_cosine(step_df, nonstep_df)
    assigned_df = solve_assignment(pairwise_df)
    annotated_pairwise_df = annotate_pairwise_assignment(pairwise_df, assigned_df, threshold)
    decision_df = build_cluster_decision(step_df, nonstep_df, pairwise_df, assigned_df, threshold)
    return annotated_pairwise_df, decision_df


def test_cross_group_similarity_accepts_clean_same_synergy_matches() -> None:
    """All assigned edges above threshold should become same_synergy matches."""
    pairwise_df, decision_df = _run_similarity(
        step_vectors=[(1.0, 0.0), (0.0, 1.0)],
        nonstep_vectors=[(0.95, 0.05), (0.05, 0.95)],
        threshold=0.8,
    )

    assert len(pairwise_df.index) == 4
    assert (
        pairwise_df.loc[:, ["step_cluster_id", "nonstep_cluster_id"]]
        .drop_duplicates()
        .shape[0]
        == 4
    )
    assert set(decision_df["final_label"].tolist()) == {"same_synergy"}
    assert decision_df["match_id"].notna().all()
    assert decision_df.loc[decision_df["group_id"] == "global_step", "match_id"].nunique() == 2


def test_cross_group_similarity_keeps_below_threshold_assignment_as_group_specific() -> None:
    """Assigned edges below threshold should stay selected but not create same_synergy."""
    pairwise_df, decision_df = _run_similarity(
        step_vectors=[(1.0, 0.0), (0.0, 1.0)],
        nonstep_vectors=[(0.75, math.sqrt(1.0 - 0.75**2)), (0.0, 1.0)],
        threshold=0.8,
    )

    below_threshold_edge = pairwise_df[
        (pairwise_df["step_cluster_id"] == 0) & (pairwise_df["nonstep_cluster_id"] == 0)
    ].iloc[0]
    assert bool(below_threshold_edge["selected_in_assignment"]) is True
    assert bool(below_threshold_edge["passes_threshold"]) is False
    assert pd.isna(below_threshold_edge["match_id"])

    affected_rows = decision_df[
        ((decision_df["group_id"] == "global_step") & (decision_df["cluster_id"] == 0))
        | ((decision_df["group_id"] == "global_nonstep") & (decision_df["cluster_id"] == 0))
    ]
    assert set(affected_rows["final_label"].tolist()) == {"group_specific_synergy"}
    assert affected_rows["match_id"].isna().all()
    assert affected_rows["assigned_partner_cluster_id"].notna().all()


def test_cross_group_similarity_preserves_best_partner_for_unmatched_rectangular_case() -> None:
    """A cluster left unmatched by rectangular assignment should keep best-partner cosine info."""
    pairwise_df, decision_df = _run_similarity(
        step_vectors=[(1.0, 0.0), (0.0, 1.0), (0.8, 0.6)],
        nonstep_vectors=[(1.0, 0.0), (0.0, 1.0)],
        threshold=0.8,
    )

    assert len(pairwise_df.index) == 6
    unmatched_row = decision_df[
        (decision_df["group_id"] == "global_step") & (decision_df["assigned_partner_cluster_id"].isna())
    ].iloc[0]
    assert unmatched_row["final_label"] == "group_specific_synergy"
    assert pd.isna(unmatched_row["assigned_cosine_similarity"])
    assert unmatched_row["best_partner_cluster_id"] == 0
    assert math.isclose(float(unmatched_row["best_partner_cosine_similarity"]), 0.8, rel_tol=1e-9)


_FIGURE_CFG = {"figures": {"format": "png", "dpi": 72}}


def _build_figure_data(
    step_vectors: list[tuple[float, float]],
    nonstep_vectors: list[tuple[float, float]],
    threshold: float,
):
    rep_w = _representative_w_rows(step_vectors, nonstep_vectors)
    step_df, nonstep_df = build_cluster_w_matrix(rep_w, ["M1", "M2"])
    pairwise_df = compute_pairwise_cosine(step_df, nonstep_df)
    assigned_df = solve_assignment(pairwise_df)
    annotated_pairwise_df = annotate_pairwise_assignment(pairwise_df, assigned_df, threshold)
    decision_df = build_cluster_decision(step_df, nonstep_df, pairwise_df, assigned_df, threshold)
    return step_df, nonstep_df, annotated_pairwise_df, decision_df


def test_save_cross_group_heatmap_creates_file(tmp_path: Path) -> None:
    _, _, pairwise_df, _ = _build_figure_data(
        step_vectors=[(1.0, 0.0), (0.0, 1.0)],
        nonstep_vectors=[(0.95, 0.05), (0.05, 0.95)],
        threshold=0.8,
    )
    out = tmp_path / "heatmap.png"
    save_cross_group_heatmap(pairwise_df, 0.8, _FIGURE_CFG, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_save_cross_group_matched_w_creates_file(tmp_path: Path) -> None:
    step_df, nonstep_df, _, decision_df = _build_figure_data(
        step_vectors=[(1.0, 0.0), (0.0, 1.0)],
        nonstep_vectors=[(0.95, 0.05), (0.05, 0.95)],
        threshold=0.8,
    )
    out = tmp_path / "matched_w.png"
    save_cross_group_matched_w(step_df, nonstep_df, decision_df, ["M1", "M2"], _FIGURE_CFG, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_save_cross_group_decision_summary_creates_file(tmp_path: Path) -> None:
    _, _, _, decision_df = _build_figure_data(
        step_vectors=[(1.0, 0.0), (0.0, 1.0), (0.8, 0.6)],
        nonstep_vectors=[(1.0, 0.0), (0.0, 1.0)],
        threshold=0.8,
    )
    out = tmp_path / "decision.png"
    save_cross_group_decision_summary(decision_df, 0.8, _FIGURE_CFG, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_save_cross_group_matched_w_handles_mixed_decisions(tmp_path: Path) -> None:
    """Matched W figure should handle both same_synergy and group_specific clusters."""
    step_df, nonstep_df, _, decision_df = _build_figure_data(
        step_vectors=[(1.0, 0.0), (0.0, 1.0), (0.8, 0.6)],
        nonstep_vectors=[(1.0, 0.0), (0.0, 1.0)],
        threshold=0.8,
    )
    out = tmp_path / "matched_mixed.png"
    save_cross_group_matched_w(step_df, nonstep_df, decision_df, ["M1", "M2"], _FIGURE_CFG, out)
    assert out.exists()
    assert out.stat().st_size > 0


def _build_fake_h_data(
    n_frames: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build fake rep_H, minimal_H, and labels for cross-group matched H tests."""
    import numpy as np

    rng = np.random.default_rng(42)
    rep_h_rows = []
    minimal_h_rows = []
    label_rows = []

    for group_id, cluster_ids, n_trials in [
        ("global_step", [0, 1], 3),
        ("global_nonstep", [0, 1], 3),
    ]:
        for cid in cluster_ids:
            base = rng.random(n_frames)
            for fi in range(n_frames):
                rep_h_rows.append({
                    "group_id": group_id,
                    "cluster_id": cid,
                    "frame_idx": fi,
                    "h_value": float(base[fi]),
                })
            for t in range(n_trials):
                trial_id = f"S{t}_v1_T0"
                comp_idx = cid
                label_rows.append({
                    "group_id": group_id,
                    "trial_id": trial_id,
                    "component_index": comp_idx,
                    "cluster_id": cid,
                })
                curve = base + rng.normal(0, 0.1, n_frames)
                for fi in range(n_frames):
                    minimal_h_rows.append({
                        "group_id": group_id,
                        "trial_id": trial_id,
                        "component_index": comp_idx,
                        "frame_idx": fi,
                        "h_value": float(curve[fi]),
                    })

    rep_h = pd.DataFrame(rep_h_rows)
    minimal_h = pd.DataFrame(minimal_h_rows)
    labels = pd.DataFrame(label_rows)
    return rep_h, minimal_h, labels


def test_save_cross_group_matched_h_creates_file(tmp_path: Path) -> None:
    """Matched H figure should be created with same_synergy and group_specific panels."""
    _, _, _, decision_df = _build_figure_data(
        step_vectors=[(1.0, 0.0), (0.0, 1.0), (0.8, 0.6)],
        nonstep_vectors=[(1.0, 0.0), (0.0, 1.0)],
        threshold=0.8,
    )
    rep_h, minimal_h, labels = _build_fake_h_data()
    out = tmp_path / "matched_h.png"
    save_cross_group_matched_h(
        rep_h_step=rep_h[rep_h["group_id"] == "global_step"],
        rep_h_nonstep=rep_h[rep_h["group_id"] == "global_nonstep"],
        minimal_h=minimal_h,
        labels=labels,
        decision_df=decision_df,
        cfg=_FIGURE_CFG,
        output_path=out,
    )
    assert out.exists()
    assert out.stat().st_size > 0
