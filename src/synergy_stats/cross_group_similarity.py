"""Compute cross-group representative W similarity artifacts.

This module pivots representative W rows into cluster vectors,
solves step-vs-nonstep cosine assignment after clustering,
and prepares pairwise and per-cluster interpretation tables.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from scipy.optimize import linear_sum_assignment


STEP_GROUP_ID = "global_step"
NONSTEP_GROUP_ID = "global_nonstep"
IDENTITY_COLUMNS = {"group_id", "cluster_id"}


def _to_polars(frame: pd.DataFrame | pl.DataFrame | list[dict[str, Any]]) -> pl.DataFrame:
    if isinstance(frame, pl.DataFrame):
        return frame
    if isinstance(frame, pd.DataFrame):
        return pl.from_pandas(frame)
    return pl.DataFrame(frame)


def _normalize_cluster_ids(frame: pl.DataFrame) -> pl.DataFrame:
    cluster_columns = [
        column_name
        for column_name in (
            "cluster_id",
            "step_cluster_id",
            "nonstep_cluster_id",
            "assigned_partner_cluster_id",
            "best_partner_cluster_id",
        )
        if column_name in frame.columns
    ]
    if not cluster_columns:
        return frame
    return frame.with_columns([pl.col(column_name).cast(pl.Int64, strict=False) for column_name in cluster_columns])


def _vector_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in IDENTITY_COLUMNS]


def _l2_normalize_rows(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    safe_norms = np.where(norms > 0, norms, 1.0)
    return values / safe_norms


def _require_nonempty_groups(step_df: pd.DataFrame, nonstep_df: pd.DataFrame) -> None:
    if step_df.empty or nonstep_df.empty:
        raise ValueError("Cross-group representative W similarity requires non-empty step and nonstep clusters.")


def _assignment_labels(assigned_df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if assigned_df.empty:
        return assigned_df.assign(
            selected_in_assignment=pd.Series(dtype=bool),
            passes_threshold=pd.Series(dtype=bool),
            match_id=pd.Series(dtype=object),
        )
    labeled = assigned_df.sort_values(["step_cluster_id", "nonstep_cluster_id"]).reset_index(drop=True).copy()
    labeled["selected_in_assignment"] = True
    labeled["passes_threshold"] = labeled["assigned_cosine_similarity"] >= float(threshold)
    match_ids: list[str | None] = []
    accepted_index = 0
    for passes_threshold in labeled["passes_threshold"].tolist():
        if passes_threshold:
            accepted_index += 1
            match_ids.append(f"same_synergy_{accepted_index:02d}")
        else:
            match_ids.append(None)
    labeled["match_id"] = match_ids
    return labeled


def build_cluster_w_matrix(
    rep_w_long: pd.DataFrame | pl.DataFrame | list[dict[str, Any]],
    muscle_order: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = _normalize_cluster_ids(_to_polars(rep_w_long))
    if frame.is_empty():
        raise ValueError("Representative W rows are required to build cross-group similarity matrices.")

    required_columns = {"group_id", "cluster_id", "muscle", "W_value"}
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Representative W rows are missing required columns: {missing_columns}")

    filtered = frame.filter(pl.col("group_id").is_in([STEP_GROUP_ID, NONSTEP_GROUP_ID]))
    if filtered.is_empty():
        raise ValueError("Representative W rows do not include global_step/global_nonstep clusters.")

    pivoted = filtered.pivot(
        values="W_value",
        index=["group_id", "cluster_id"],
        on="muscle",
        aggregate_function="first",
    )
    missing_muscles = [muscle for muscle in muscle_order if muscle not in pivoted.columns]
    if missing_muscles:
        raise ValueError(f"Representative W rows are missing muscles required by config: {missing_muscles}")

    ordered = (
        pivoted.select(["group_id", "cluster_id", *muscle_order])
        .sort(["group_id", "cluster_id"])
    )
    null_counts = ordered.null_count().row(0)[2:]
    if any(count > 0 for count in null_counts):
        raise ValueError("Representative W rows contain null muscle weights after pivot.")

    matrix = ordered.to_pandas()
    vector_columns = _vector_columns(matrix)
    matrix.loc[:, vector_columns] = _l2_normalize_rows(matrix[vector_columns].to_numpy(dtype=np.float64))
    step_df = matrix.loc[matrix["group_id"] == STEP_GROUP_ID].reset_index(drop=True)
    nonstep_df = matrix.loc[matrix["group_id"] == NONSTEP_GROUP_ID].reset_index(drop=True)
    _require_nonempty_groups(step_df, nonstep_df)
    return step_df, nonstep_df


def compute_pairwise_cosine(step_df: pd.DataFrame, nonstep_df: pd.DataFrame) -> pd.DataFrame:
    _require_nonempty_groups(step_df, nonstep_df)
    step_columns = _vector_columns(step_df)
    nonstep_columns = _vector_columns(nonstep_df)
    if step_columns != nonstep_columns:
        raise ValueError("Step and nonstep representative W matrices must share the same muscle columns.")

    step_vectors = step_df[step_columns].to_numpy(dtype=np.float64)
    nonstep_vectors = nonstep_df[nonstep_columns].to_numpy(dtype=np.float64)
    cosine_matrix = np.clip(step_vectors @ nonstep_vectors.T, -1.0, 1.0)
    rows = []
    for step_index, step_cluster_id in enumerate(step_df["cluster_id"].tolist()):
        for nonstep_index, nonstep_cluster_id in enumerate(nonstep_df["cluster_id"].tolist()):
            rows.append(
                {
                    "step_cluster_id": int(step_cluster_id),
                    "nonstep_cluster_id": int(nonstep_cluster_id),
                    "cosine_similarity": float(cosine_matrix[step_index, nonstep_index]),
                }
            )
    return pd.DataFrame(rows).sort_values(["step_cluster_id", "nonstep_cluster_id"]).reset_index(drop=True)


def solve_assignment(pairwise_df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    frame = _normalize_cluster_ids(_to_polars(pairwise_df))
    if frame.is_empty():
        raise ValueError("Pairwise cosine rows are required before solving assignment.")

    step_ids = sorted(frame.get_column("step_cluster_id").unique().to_list())
    nonstep_ids = sorted(frame.get_column("nonstep_cluster_id").unique().to_list())
    if not step_ids or not nonstep_ids:
        raise ValueError("Assignment requires at least one step cluster and one nonstep cluster.")

    matrix = (
        frame.to_pandas()
        .pivot(index="step_cluster_id", columns="nonstep_cluster_id", values="cosine_similarity")
        .reindex(index=step_ids, columns=nonstep_ids)
    )
    if matrix.isnull().values.any():
        raise ValueError("Pairwise cosine table must contain every unique step/nonstep cluster combination.")

    row_indices, col_indices = linear_sum_assignment(1.0 - matrix.to_numpy(dtype=np.float64))
    assigned_rows = [
        {
            "step_cluster_id": int(step_ids[row_index]),
            "nonstep_cluster_id": int(nonstep_ids[col_index]),
            "assigned_cosine_similarity": float(matrix.iat[row_index, col_index]),
        }
        for row_index, col_index in zip(row_indices.tolist(), col_indices.tolist(), strict=True)
    ]
    return pd.DataFrame(assigned_rows).sort_values(["step_cluster_id", "nonstep_cluster_id"]).reset_index(drop=True)


def annotate_pairwise_assignment(
    pairwise_df: pd.DataFrame | pl.DataFrame,
    assigned_df: pd.DataFrame | pl.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    pairwise = _normalize_cluster_ids(_to_polars(pairwise_df)).to_pandas()
    assigned = _assignment_labels(_normalize_cluster_ids(_to_polars(assigned_df)).to_pandas(), threshold)
    annotated = pairwise.merge(
        assigned[
            [
                "step_cluster_id",
                "nonstep_cluster_id",
                "selected_in_assignment",
                "passes_threshold",
                "match_id",
            ]
        ],
        on=["step_cluster_id", "nonstep_cluster_id"],
        how="left",
    )
    annotated["selected_in_assignment"] = annotated["selected_in_assignment"].eq(True)
    annotated["passes_threshold"] = annotated["passes_threshold"].eq(True)
    return annotated.sort_values(["step_cluster_id", "nonstep_cluster_id"]).reset_index(drop=True)


def build_cluster_decision(
    step_df: pd.DataFrame,
    nonstep_df: pd.DataFrame,
    pairwise_df: pd.DataFrame | pl.DataFrame,
    assigned_df: pd.DataFrame | pl.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    _require_nonempty_groups(step_df, nonstep_df)
    pairwise = _normalize_cluster_ids(_to_polars(pairwise_df)).to_pandas()
    assigned = _assignment_labels(_normalize_cluster_ids(_to_polars(assigned_df)).to_pandas(), threshold)

    if pairwise.empty:
        raise ValueError("Pairwise cosine rows are required to build the cluster decision table.")

    step_best = (
        pairwise.sort_values(["step_cluster_id", "cosine_similarity", "nonstep_cluster_id"], ascending=[True, False, True])
        .groupby("step_cluster_id", as_index=False)
        .first()
        .rename(
            columns={
                "step_cluster_id": "cluster_id",
                "nonstep_cluster_id": "best_partner_cluster_id",
                "cosine_similarity": "best_partner_cosine_similarity",
            }
        )
    )
    nonstep_best = (
        pairwise.sort_values(
            ["nonstep_cluster_id", "cosine_similarity", "step_cluster_id"],
            ascending=[True, False, True],
        )
        .groupby("nonstep_cluster_id", as_index=False)
        .first()
        .rename(
            columns={
                "nonstep_cluster_id": "cluster_id",
                "step_cluster_id": "best_partner_cluster_id",
                "cosine_similarity": "best_partner_cosine_similarity",
            }
        )
    )

    step_clusters = step_df.loc[:, ["group_id", "cluster_id"]].copy()
    nonstep_clusters = nonstep_df.loc[:, ["group_id", "cluster_id"]].copy()
    step_assigned = assigned.rename(
        columns={
            "nonstep_cluster_id": "assigned_partner_cluster_id",
        }
    ).loc[:, ["step_cluster_id", "assigned_partner_cluster_id", "assigned_cosine_similarity", "match_id", "passes_threshold"]]
    step_assigned = step_assigned.rename(columns={"step_cluster_id": "cluster_id"})
    nonstep_assigned = assigned.rename(
        columns={
            "step_cluster_id": "assigned_partner_cluster_id",
        }
    ).loc[:, ["nonstep_cluster_id", "assigned_partner_cluster_id", "assigned_cosine_similarity", "match_id", "passes_threshold"]]
    nonstep_assigned = nonstep_assigned.rename(columns={"nonstep_cluster_id": "cluster_id"})

    decision_frames = [
        step_clusters.merge(step_best, on="cluster_id", how="left").merge(step_assigned, on="cluster_id", how="left"),
        nonstep_clusters.merge(nonstep_best, on="cluster_id", how="left").merge(nonstep_assigned, on="cluster_id", how="left"),
    ]
    decision = pd.concat(decision_frames, ignore_index=True)
    passes_threshold = decision["passes_threshold"].eq(True)
    decision["final_label"] = np.where(
        passes_threshold,
        "same_synergy",
        "group_specific_synergy",
    )
    decision.loc[decision["final_label"] != "same_synergy", "match_id"] = None
    decision = decision[
        [
            "group_id",
            "cluster_id",
            "final_label",
            "match_id",
            "assigned_partner_cluster_id",
            "assigned_cosine_similarity",
            "best_partner_cluster_id",
            "best_partner_cosine_similarity",
        ]
    ]
    return decision.sort_values(["group_id", "cluster_id"]).reset_index(drop=True)


def build_pairwise_matrix(pairwise_df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    frame = _normalize_cluster_ids(_to_polars(pairwise_df)).to_pandas()
    if frame.empty:
        return pd.DataFrame(columns=["step_cluster_id"])
    matrix = (
        frame.pivot(index="step_cluster_id", columns="nonstep_cluster_id", values="cosine_similarity")
        .sort_index(axis=0)
        .sort_index(axis=1)
        .reset_index()
    )
    matrix.columns = [
        "step_cluster_id",
        *[f"nonstep_cluster_{int(column)}" for column in matrix.columns[1:]],
    ]
    return matrix


def build_cross_group_summary(
    step_df: pd.DataFrame,
    nonstep_df: pd.DataFrame,
    decision_df: pd.DataFrame | pl.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    decision = _normalize_cluster_ids(_to_polars(decision_df)).to_pandas()
    accepted_matches = decision.loc[decision["match_id"].notna(), "match_id"].nunique()
    return pd.DataFrame(
        [
            {
                "step_cluster_count": int(len(step_df.index)),
                "nonstep_cluster_count": int(len(nonstep_df.index)),
                "accepted_same_synergy_match_count": int(accepted_matches),
                "group_specific_step_cluster_count": int(
                    decision[
                        (decision["group_id"] == STEP_GROUP_ID)
                        & (decision["final_label"] == "group_specific_synergy")
                    ].shape[0]
                ),
                "group_specific_nonstep_cluster_count": int(
                    decision[
                        (decision["group_id"] == NONSTEP_GROUP_ID)
                        & (decision["final_label"] == "group_specific_synergy")
                    ].shape[0]
                ),
                "threshold": float(threshold),
            }
        ]
    )
