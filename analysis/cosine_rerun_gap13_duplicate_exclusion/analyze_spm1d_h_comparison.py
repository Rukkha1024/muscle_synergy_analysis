"""SPM 1D paired H-curve comparison between step and nonstep groups.

For each of the 11 same_synergy pairs identified in the cross-group W cosine
matching (gap13 duplicate-exclusion rerun), this script:

1. Extracts per-component H curves (100-frame time series) for step and
   nonstep clusters forming each matched pair.
2. Runs SPM 1D two-sample t-tests (parametric Welch & nonparametric
   permutation) to identify time regions where step/nonstep activations
   significantly differ.
3. Applies BH-FDR correction across the 11 pairs.
4. Generates one figure per pair showing mean±SD overlays and SPM{t} curves.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import polars as pl

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    matplotlib.use("Agg", force=True)
except Exception:
    pass

import matplotlib.pyplot as plt
from matplotlib import font_manager

KOREAN_FONT_CANDIDATES = (
    "NanumGothic",
    "NanumBarunGothic",
    "Malgun Gothic",
    "AppleGothic",
    "Noto Sans CJK KR",
    "Noto Sans KR",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_BASELINE_RUN = REPO_ROOT / "outputs" / "runs" / "default_run"
DEFAULT_ARTIFACT_DIR = (
    SCRIPT_DIR / "artifacts" / "gap13_duplicate_component_exclusion_rerun"
)

N_FRAMES = 100
ALPHA = 0.05
NONPARAM_ITERATIONS = 10_000

STEP_COLOR = "#5C7CFA"
NONSTEP_COLOR = "#E64980"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-run",
        type=Path,
        default=DEFAULT_BASELINE_RUN,
        help="Baseline pipeline output directory.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help="Artifact directory from gap13 duplicate-exclusion rerun.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing figure files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only load data and print summary; skip SPM analysis and figures.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
def _configure_fonts() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    selected = next((n for n in KOREAN_FONT_CANDIDATES if n in available), None)
    if selected:
        matplotlib.rcParams["font.family"] = [selected]
    matplotlib.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_same_synergy_pairs(artifact_dir: Path) -> pl.DataFrame:
    """Return rows from cross_group_w_cluster_decision.csv with same_synergy."""
    path = artifact_dir / "cross_group_w_cluster_decision.csv"
    df = pl.read_csv(path)
    same = df.filter(pl.col("final_label") == "same_synergy")
    # Build pair table: match_id → step_cluster, nonstep_cluster
    step = (
        same.filter(pl.col("group_id") == "global_step")
        .select(["match_id", pl.col("cluster_id").alias("step_cluster")])
    )
    nonstep = (
        same.filter(pl.col("group_id") == "global_nonstep")
        .select(["match_id", pl.col("cluster_id").alias("nonstep_cluster")])
    )
    pairs = step.join(nonstep, on="match_id").sort("match_id")
    return pairs


def load_step_components(artifact_dir: Path) -> pl.DataFrame:
    """Load step K=13 component assignments, excluding duplicates."""
    path = artifact_dir / "step_k13_component_assignments.csv"
    df = pl.read_csv(path)
    return df.filter(pl.col("excluded_from_representative") == False).select(
        ["trial_id", "component_index", pl.col("cluster_id_k13").alias("cluster_id")]
    )


def load_nonstep_components(baseline_run: Path) -> pl.DataFrame:
    """Load nonstep component→cluster from baseline all_cluster_labels.csv."""
    path = baseline_run / "all_cluster_labels.csv"
    df = pl.read_csv(path)
    return (
        df.filter(pl.col("group_id") == "global_nonstep")
        .select(["trial_id", "component_index", "cluster_id"])
    )


def load_h_long(baseline_run: Path) -> pl.DataFrame:
    """Load all H long-format data."""
    path = baseline_run / "all_minimal_units_H_long.csv"
    return pl.read_csv(
        path,
        columns=["group_id", "trial_id", "component_index", "frame_idx", "h_value"],
    )


def build_h_matrix(
    h_long: pl.DataFrame,
    components: pl.DataFrame,
    cluster_id: int,
    group_id: str,
) -> np.ndarray:
    """Build (n_components, N_FRAMES) H matrix for one cluster.

    Returns array of shape (n, 100).
    """
    cluster_comps = components.filter(pl.col("cluster_id") == cluster_id)
    h_group = h_long.filter(pl.col("group_id") == group_id)
    joined = cluster_comps.join(
        h_group, on=["trial_id", "component_index"], how="inner"
    )
    if joined.is_empty():
        return np.empty((0, N_FRAMES))
    pivoted = (
        joined.sort(["trial_id", "component_index", "frame_idx"])
        .group_by(["trial_id", "component_index"], maintain_order=True)
        .agg(pl.col("h_value"))
    )
    mat = np.array(pivoted["h_value"].to_list())
    assert mat.shape[1] == N_FRAMES, f"Expected {N_FRAMES} frames, got {mat.shape[1]}"
    return mat


# ---------------------------------------------------------------------------
# SPM 1D analysis
# ---------------------------------------------------------------------------
def run_spm_tests(step_h: np.ndarray, nonstep_h: np.ndarray):
    """Run parametric and nonparametric SPM 1D two-sample t-tests.

    Returns (param_ti, nonparam_ti) inference objects.
    """
    import spm1d

    t_param = spm1d.stats.ttest2(step_h, nonstep_h, equal_var=False)
    ti_param = t_param.inference(alpha=ALPHA)

    t_nonparam = spm1d.stats.nonparam.ttest2(step_h, nonstep_h)
    ti_nonparam = t_nonparam.inference(alpha=ALPHA, iterations=NONPARAM_ITERATIONS)

    return ti_param, ti_nonparam


def extract_cluster_pvalue(ti) -> float:
    """Extract the minimum cluster-level p-value from an SPM inference object.

    If no supra-threshold clusters exist, returns 1.0.
    """
    clusters = ti.clusters if hasattr(ti, "clusters") else []
    if not clusters:
        return 1.0
    return min(c.P for c in clusters)


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
def save_pair_figure(
    match_id: str,
    step_h: np.ndarray,
    nonstep_h: np.ndarray,
    ti_param,
    ti_nonparam,
    step_cluster: int,
    nonstep_cluster: int,
    fdr_sig_param: bool,
    fdr_sig_nonparam: bool,
    outdir: Path,
) -> Path:
    """Create 2×2 figure for one matched pair and save to disk."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    x = np.arange(N_FRAMES)

    for row, (ti, label, fdr_sig) in enumerate(
        [
            (ti_param, "Parametric (Welch)", fdr_sig_param),
            (ti_nonparam, "Nonparametric (perm)", fdr_sig_nonparam),
        ]
    ):
        ax_mean = axes[row, 0]
        ax_spm = axes[row, 1]

        # Left: mean ± SD overlay
        for mat, color, grp in [
            (step_h, STEP_COLOR, f"step (n={step_h.shape[0]})"),
            (nonstep_h, NONSTEP_COLOR, f"nonstep (n={nonstep_h.shape[0]})"),
        ]:
            m = mat.mean(axis=0)
            s = mat.std(axis=0, ddof=1)
            ax_mean.plot(x, m, color=color, label=grp, linewidth=1.5)
            ax_mean.fill_between(x, m - s, m + s, color=color, alpha=0.2)
        ax_mean.set_ylabel("H (activation)")
        ax_mean.set_xlabel("Normalized time (%)")
        ax_mean.legend(fontsize=8)
        ax_mean.set_title(f"{label} — Mean ± SD")

        # Right: SPM{t} curve + threshold + shading
        t_stat = ti.z if hasattr(ti, "z") else ti.z
        ax_spm.plot(x, t_stat, color="black", linewidth=1.2)
        thr = ti.zstar
        ax_spm.axhline(thr, color="red", linestyle="--", linewidth=0.8, label=f"threshold={thr:.2f}")
        ax_spm.axhline(-thr, color="red", linestyle="--", linewidth=0.8)

        clusters = ti.clusters if hasattr(ti, "clusters") else []
        for cl in clusters:
            idx_start = int(np.floor(cl.endpoints[0]))
            idx_end = int(np.ceil(cl.endpoints[1]))
            idx_end = min(idx_end, N_FRAMES - 1)
            ax_spm.axvspan(idx_start, idx_end, color="gold", alpha=0.35)

        ax_spm.set_ylabel("SPM{t}")
        ax_spm.set_xlabel("Normalized time (%)")
        ax_spm.legend(fontsize=8, loc="upper right")

        sig_label = "Sig (BH-FDR)" if fdr_sig else "n.s. (BH-FDR)"
        ax_spm.set_title(f"{label} — SPM{{t}}  [{sig_label}]")

    fig.suptitle(
        f"{match_id}   |   step cluster {step_cluster} ↔ nonstep cluster {nonstep_cluster}",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"spm1d_h_pair_{match_id}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    _configure_fonts()

    # Load data
    print("=" * 60)
    print("SPM 1D H-curve comparison: step vs nonstep")
    print("=" * 60)

    pairs = load_same_synergy_pairs(args.artifact_dir)
    print(f"\nLoaded {len(pairs)} same_synergy pairs:")
    print(pairs)

    step_comps = load_step_components(args.artifact_dir)
    nonstep_comps = load_nonstep_components(args.baseline_run)
    h_long = load_h_long(args.baseline_run)

    print(f"\nStep components (excl. duplicates): {len(step_comps)}")
    print(f"Nonstep components: {len(nonstep_comps)}")
    print(f"H long rows: {len(h_long)}")

    # Build H matrices per pair
    pair_data = []
    for row in pairs.iter_rows(named=True):
        match_id = row["match_id"]
        sc = row["step_cluster"]
        nc = row["nonstep_cluster"]
        step_h = build_h_matrix(h_long, step_comps, sc, "global_step")
        nonstep_h = build_h_matrix(h_long, nonstep_comps, nc, "global_nonstep")
        pair_data.append(
            {
                "match_id": match_id,
                "step_cluster": sc,
                "nonstep_cluster": nc,
                "step_h": step_h,
                "nonstep_h": nonstep_h,
            }
        )
        print(
            f"  {match_id}: step_cluster={sc} ({step_h.shape[0]} comps) ↔ "
            f"nonstep_cluster={nc} ({nonstep_h.shape[0]} comps)"
        )

    if args.dry_run:
        print("\n[DRY-RUN] Data loading complete. Exiting without SPM analysis.")
        return

    # SPM analysis
    import spm1d  # noqa: F811
    from statsmodels.stats.multitest import multipletests

    print("\n--- SPM 1D analysis ---")
    results = []
    for pd_ in pair_data:
        match_id = pd_["match_id"]
        step_h = pd_["step_h"]
        nonstep_h = pd_["nonstep_h"]

        if step_h.shape[0] < 2 or nonstep_h.shape[0] < 2:
            print(f"  {match_id}: SKIP (n_step={step_h.shape[0]}, n_nonstep={nonstep_h.shape[0]})")
            results.append(
                {
                    "match_id": match_id,
                    "p_param": 1.0,
                    "p_nonparam": 1.0,
                    "ti_param": None,
                    "ti_nonparam": None,
                    **pd_,
                }
            )
            continue

        ti_param, ti_nonparam = run_spm_tests(step_h, nonstep_h)
        p_param = extract_cluster_pvalue(ti_param)
        p_nonparam = extract_cluster_pvalue(ti_nonparam)

        results.append(
            {
                **pd_,
                "p_param": p_param,
                "p_nonparam": p_nonparam,
                "ti_param": ti_param,
                "ti_nonparam": ti_nonparam,
            }
        )
        n_cl_param = len(ti_param.clusters) if hasattr(ti_param, "clusters") else 0
        n_cl_nonparam = len(ti_nonparam.clusters) if hasattr(ti_nonparam, "clusters") else 0
        print(
            f"  {match_id}: p_param={p_param:.4f} ({n_cl_param} clusters), "
            f"p_nonparam={p_nonparam:.4f} ({n_cl_nonparam} clusters)"
        )

    # BH-FDR correction
    p_param_arr = np.array([r["p_param"] for r in results])
    p_nonparam_arr = np.array([r["p_nonparam"] for r in results])

    _, fdr_param, _, _ = multipletests(p_param_arr, alpha=ALPHA, method="fdr_bh")
    _, fdr_nonparam, _, _ = multipletests(p_nonparam_arr, alpha=ALPHA, method="fdr_bh")

    # multipletests returns (reject, pvals_corrected, ...) — fdr_* here is corrected p
    reject_param, pcorr_param, _, _ = multipletests(p_param_arr, alpha=ALPHA, method="fdr_bh")
    reject_nonparam, pcorr_nonparam, _, _ = multipletests(p_nonparam_arr, alpha=ALPHA, method="fdr_bh")

    print("\n--- BH-FDR corrected results ---")
    print(f"{'match_id':<20} {'p_param':>8} {'p_corr_p':>8} {'sig_p':>6}  "
          f"{'p_nonp':>8} {'p_corr_np':>9} {'sig_np':>6}")
    print("-" * 80)
    for i, r in enumerate(results):
        sig_p = "***" if reject_param[i] else "n.s."
        sig_np = "***" if reject_nonparam[i] else "n.s."
        print(
            f"{r['match_id']:<20} {r['p_param']:>8.4f} {pcorr_param[i]:>8.4f} {sig_p:>6}  "
            f"{r['p_nonparam']:>8.4f} {pcorr_nonparam[i]:>9.4f} {sig_np:>6}"
        )

    # Generate figures
    fig_dir = args.artifact_dir / "figures"
    print(f"\n--- Generating figures → {fig_dir} ---")
    for i, r in enumerate(results):
        if r["ti_param"] is None:
            print(f"  {r['match_id']}: skipped (insufficient data)")
            continue
        out = save_pair_figure(
            match_id=r["match_id"],
            step_h=r["step_h"],
            nonstep_h=r["nonstep_h"],
            ti_param=r["ti_param"],
            ti_nonparam=r["ti_nonparam"],
            step_cluster=r["step_cluster"],
            nonstep_cluster=r["nonstep_cluster"],
            fdr_sig_param=reject_param[i],
            fdr_sig_nonparam=reject_nonparam[i],
            outdir=fig_dir,
        )
        print(f"  {r['match_id']}: {out.name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
