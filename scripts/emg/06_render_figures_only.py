"""Rerender saved EMG figures from one existing run directory.

This CLI reloads the figure source parquet artifacts already
saved under outputs/runs/<run_id> and rebuilds the figures tree in place.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.emg_pipeline.config import load_pipeline_config, prepare_runtime_paths
from src.synergy_stats.figure_rerender import render_figures_from_run_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rerender EMG figures from an existing run directory.")
    parser.add_argument("--run-dir", required=True, help="Existing run directory whose figures tree should be rebuilt.")
    parser.add_argument("--config", default="configs/global_config.yaml", help="Path to the global YAML config.")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        cfg = load_pipeline_config(args.config)
        cfg.setdefault("runtime", {})
        cfg["runtime"]["output_dir"] = str(Path(args.run_dir))
        prepare_runtime_paths(cfg, repo_root=Path.cwd())
        run_dir = Path(cfg["runtime"]["output_dir"]).resolve()
        rendered = render_figures_from_run_dir(run_dir, cfg)
    except Exception as exc:
        print(f"Figure rerender failed: {exc}", file=sys.stderr)
        return 1

    figure_count = sum(len(paths) for paths in rendered.values())
    print(f"Rerendered {figure_count} figure(s) in {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
