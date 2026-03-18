"""Write parquet-first artifacts or rebuild Excel from saved parquet."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.synergy_stats import export_results
from src.synergy_stats.artifacts import export_from_parquet
from src.emg_pipeline.log_utils import log_kv_section


def run(context: dict) -> dict:
    context = export_results(context)
    output_dir = Path(context["config"]["runtime"]["output_dir"])
    figure_root = output_dir / "figures"
    workbook_count = len(list(output_dir.rglob("*.xlsx")))
    parquet_paths = {path.resolve() for path in output_dir.rglob("*.parquet")}
    final_parquet_path = context["artifacts"].get("final_parquet_path")
    if final_parquet_path:
        parquet_paths.add(Path(final_parquet_path).resolve())
    figure_count = len([path for path in figure_root.rglob("*") if path.is_file()]) if figure_root.exists() else 0
    log_kv_section(
        "Export Summary",
        [
            ("Output directory", output_dir),
            ("Excel workbooks", workbook_count),
            ("Parquet files", len([path for path in parquet_paths if path.is_file()])),
            ("Figures", figure_count),
        ],
    )
    return context


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild Excel workbooks from parquet files.")
    parser.add_argument(
        "--from-parquet",
        help="Run directory containing parquet/ subdirectories.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if not args.from_parquet:
        raise SystemExit("Use this CLI with --from-parquet <run_dir> to rebuild Excel workbooks.")
    export_from_parquet(Path(args.from_parquet).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
