"""Verify the standalone compare_Cheung duplicate-assignment audit.

This script checks that the expected local artifacts exist, that the
headline metrics are internally consistent, and that no forced-
reassignment artifact was produced for this compare_Cheung-only scope.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import polars as pl


SCRIPT_DIR = Path(__file__).resolve().parent
COMPARE_SCRIPT = SCRIPT_DIR.parent / "compare_Cheung,2021" / "analyze_compare_cheung_synergy_analysis.py"


def parse_args() -> argparse.Namespace:
    """Parse CLI args for audit verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-path", type=Path, default=SCRIPT_DIR / "report.md")
    parser.add_argument("--results-dir", type=Path, default=SCRIPT_DIR / "results")
    return parser.parse_args()


def _require_path(path: Path) -> None:
    """Raise if an expected file is missing."""
    if not path.exists():
        raise FileNotFoundError(f"Missing expected artifact: {path}")


def _fraction(numerator: int, denominator: int) -> str:
    """Render a fraction string with rate."""
    rate = 0.0 if denominator == 0 else numerator / denominator
    return f"{numerator}/{denominator} = {rate:.3f}"


def _load_checksum_manifest(path: Path) -> dict[str, str]:
    """Load the MD5 manifest into a path-to-digest mapping."""
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if not text:
            continue
        digest, rel_path = text.split("  ", maxsplit=1)
        rows[rel_path] = digest
    return rows


def main() -> int:
    """Run artifact and metric consistency checks."""
    args = parse_args()
    checksum_path = SCRIPT_DIR / "checksums.md5"
    required_files = [
        args.report_path,
        checksum_path,
        args.results_dir / "overall_metrics.csv",
        args.results_dir / "per_unit_metrics.csv",
        args.results_dir / "duplicate_pairs.csv",
        args.results_dir / "per_cluster_stats.csv",
        args.results_dir / "k_sensitivity.csv",
        args.results_dir / "plots" / "k_vs_gap_statistic.png",
        args.results_dir / "plots" / "k_vs_duplicate_unit_rate.png",
        args.results_dir / "plots" / "k_vs_excess_duplicate_ratio.png",
        args.results_dir / "plots" / "group_duplicate_unit_rate.png",
        args.results_dir / "plots" / "duplicate_vs_nonduplicate_similarity.png",
    ]
    for path in required_files:
        _require_path(path)

    checksum_rows = _load_checksum_manifest(checksum_path)
    if not checksum_rows:
        raise AssertionError("checksums.md5 is empty")
    for rel_path, expected_digest in checksum_rows.items():
        artifact_path = Path(rel_path)
        _require_path(artifact_path)
        actual_digest = hashlib.md5(artifact_path.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise AssertionError(f"Stale checksum for {artifact_path}: {actual_digest} != {expected_digest}")

    if (args.results_dir / "reassignment_stats.csv").exists():
        raise AssertionError("compare_Cheung-only audit must not emit reassignment_stats.csv")

    overall = pl.read_csv(args.results_dir / "overall_metrics.csv")
    raw_overall = overall.filter(
        (pl.col("pipeline_name") == "paper_like")
        & (pl.col("state_name") == "state1_paper_like_unconstrained")
        & (pl.col("label_space") == "raw_group_label")
        & (pl.col("scope") == "overall")
        & (pl.col("group_id") == "__overall__")
    )
    if raw_overall.height != 1:
        raise AssertionError("Expected exactly one raw overall row")
    row = raw_overall.to_dicts()[0]
    if int(row["duplicate_units"]) <= 0:
        raise AssertionError("Expected raw compare_Cheung outputs to retain at least one duplicate unit")

    expected_duplicate_unit = _fraction(int(row["duplicate_units"]), int(row["units_total"]))
    expected_excess = f"{int(row['excess_duplicates_total'])}/{int(row['synergies_total'])} = {float(row['excess_duplicate_ratio']):.3f}"
    expected_pair = f"{int(row['duplicate_pairs_total'])}/{int(row['within_unit_pairs_total'])} = {float(row['duplicate_pair_rate']):.3f}"

    report_text = args.report_path.read_text(encoding="utf-8-sig")
    for snippet in [
        expected_duplicate_unit,
        expected_excess,
        expected_pair,
        "forced reassignment는 이번 source-of-truth 코드 경로에는 없다.",
        "A3. 이번 source-of-truth 경로에는 forced reassignment 단계 자체가 없어서 해당 사항이 없다.",
    ]:
        if snippet not in report_text:
            raise AssertionError(f"Report is missing expected snippet: {snippet}")

    compare_text = COMPARE_SCRIPT.read_text(encoding="utf-8")
    if "_enforce_unique_trial_labels" in compare_text:
        raise AssertionError("compare_Cheung script unexpectedly references production uniqueness enforcement")

    print("[verify] Required artifacts exist")
    print(f"[verify] Checksum manifest fresh for {len(checksum_rows)} artifact(s)")
    print(f"[verify] Raw duplicate_unit_rate = {expected_duplicate_unit}")
    print(f"[verify] Raw excess_duplicate_ratio = {expected_excess}")
    print(f"[verify] Raw duplicate_pair_rate = {expected_pair}")
    print("[verify] Raw compare_Cheung outputs still retain duplicates, consistent with unconstrained behavior")
    print("[verify] No compare_Cheung reassignment artifact detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
