"""Write group outputs, aggregate CSVs, and the final parquet."""

from __future__ import annotations

from pathlib import Path

from src.synergy_stats import export_results
from src.emg_pipeline.log_utils import log_kv_section


def run(context: dict) -> dict:
    context = export_results(context)
    output_dir = Path(context["config"]["runtime"]["output_dir"])
    figure_root = output_dir / "figures"
    csv_count = len(list(output_dir.rglob("*.csv")))
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
            ("CSV files", csv_count),
            ("Excel workbooks", workbook_count),
            ("Parquet files", len([path for path in parquet_paths if path.is_file()])),
            ("Figures", figure_count),
        ],
    )
    return context
