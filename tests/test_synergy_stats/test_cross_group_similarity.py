"""Contract tests for cross-group representative W similarity outputs."""

from __future__ import annotations

import math

import pandas as pd

from src.synergy_stats.cross_group_similarity import (
    annotate_pairwise_assignment,
    build_cluster_decision,
    build_cluster_w_matrix,
    compute_pairwise_cosine,
    solve_assignment,
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
