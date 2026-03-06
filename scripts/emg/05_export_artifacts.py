"""Write group outputs, aggregate CSVs, and the final parquet."""

from __future__ import annotations

import logging

from src.synergy_stats import export_results


def run(context: dict) -> dict:
    context = export_results(context)
    logging.info("Exported final artifacts to %s", context["config"]["runtime"]["output_dir"])
    return context
