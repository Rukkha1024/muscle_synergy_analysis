"""Write single-parquet artifacts or rebuild mode Excel from them."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.synergy_stats import export_results
from src.synergy_stats.artifacts import export_from_parquet
from src.emg_pipeline.config import load_pipeline_config, prepare_runtime_paths
from src.emg_pipeline.log_utils import log_kv_section


def run(context: dict) -> dict:
    context = export_results(context)
    output_dir = Path(context["config"]["runtime"]["output_dir"])
    workbook_count = len(list(output_dir.rglob("*.xlsx")))
    parquet_paths = {path.resolve() for path in output_dir.rglob("*.parquet")}
    final_parquet_path = context["artifacts"].get("final_parquet_path")
    if final_parquet_path:
        parquet_paths.add(Path(final_parquet_path).resolve())
    for path in context["artifacts"].get("final_parquet_alias_paths", {}).values():
        parquet_paths.add(Path(path).resolve())
    figure_count = len(list(output_dir.rglob("*.png")))
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
    parser = argparse.ArgumentParser(description="Rebuild mode Excel workbooks from saved single parquet files.")
    parser.add_argument("--run-dir", help="Run directory whose mode workbooks should be rebuilt.")
    parser.add_argument("--config", default="configs/global_config.yaml", help="Path to the global YAML config.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if not args.run_dir:
        raise SystemExit("Use this CLI with --run-dir <run_dir> [--config <path>] to rebuild mode Excel workbooks.")
    cfg = load_pipeline_config(args.config)
    cfg.setdefault("runtime", {})
    cfg["runtime"]["output_dir"] = str(Path(args.run_dir))
    prepare_runtime_paths(cfg, repo_root=Path.cwd())
    export_from_parquet(Path(args.run_dir).resolve(), cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
