"""Run the EMG synergy pipeline in an explicit step order.

This orchestrator loads YAML configs, applies CLI overrides,
executes thin `scripts/emg/NN_*.py` wrappers, and writes
run-level artifacts such as logs, manifests, and final outputs.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from src.emg_pipeline.config import (
    apply_cli_overrides,
    load_pipeline_config,
    prepare_runtime_paths,
    write_run_manifest,
)
from src.emg_pipeline.log_utils import log_step_banner
from src.synergy_stats.methods import normalize_analysis_mode, resolve_analysis_modes


STEP_FILES = [
    "scripts/emg/01_load_emg_table.py",
    "scripts/emg/02_extract_trials.py",
    "scripts/emg/03_extract_synergy_nmf.py",
    "scripts/emg/04_cluster_synergies.py",
    "scripts/emg/05_export_artifacts.py",
]

STEP_TITLES = {
    "scripts/emg/01_load_emg_table.py": "Load EMG Table",
    "scripts/emg/02_extract_trials.py": "Extract Trials",
    "scripts/emg/03_extract_synergy_nmf.py": "Extract Synergy (NMF)",
    "scripts/emg/04_cluster_synergies.py": "Cluster Synergies",
    "scripts/emg/05_export_artifacts.py": "Export Artifacts",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EMG synergy extraction pipeline")
    parser.add_argument("--config", default="configs/global_config.yaml", help="Path to the global YAML config.")
    parser.add_argument("--parquet", default=None, help="Override `input.emg_parquet_path`.")
    parser.add_argument("--meta-xlsm", default=None, help="Override `input.event_xlsm_path`.")
    parser.add_argument("--out", default=None, help="Override `runtime.output_dir`.")
    parser.add_argument(
        "--mode",
        choices=("trialwise", "concatenated", "both"),
        default=None,
        help="Override `synergy_analysis.mode`.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate config and inputs without running the full pipeline.")
    parser.add_argument("--overwrite", action="store_true", help="Remove an existing run directory before writing new outputs.")
    return parser


def _configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8-sig"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def _load_step(step_path: Path):
    spec = importlib.util.spec_from_file_location(step_path.stem.replace(".", "_"), step_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load pipeline step: {step_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise RuntimeError(f"Pipeline step does not expose run(context): {step_path}")
    return module.run


def _ensure_clean_output(runtime_cfg: dict[str, Any]) -> None:
    output_dir = Path(runtime_cfg["output_dir"])
    if output_dir.exists() and runtime_cfg.get("overwrite", False):
        shutil.rmtree(output_dir)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    cfg = load_pipeline_config(args.config)
    cfg = apply_cli_overrides(
        cfg,
        parquet_path=args.parquet,
        meta_xlsm_path=args.meta_xlsm,
        output_dir=args.out,
        mode=args.mode,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )
    prepare_runtime_paths(cfg, repo_root=Path.cwd())
    selected_mode = normalize_analysis_mode(cfg.get("synergy_analysis", {}).get("mode", "both"))
    cfg.setdefault("synergy_analysis", {})["mode"] = selected_mode
    cfg["runtime"]["analysis_modes"] = resolve_analysis_modes(selected_mode)
    _ensure_clean_output(cfg["runtime"])
    _configure_logging(Path(cfg["runtime"]["log_path"]))

    logging.info("Loaded config from %s", args.config)
    logging.info("Run output directory: %s", cfg["runtime"]["output_dir"])
    logging.info("Analysis mode: %s -> %s", selected_mode, ", ".join(cfg["runtime"]["analysis_modes"]))
    write_run_manifest(cfg)

    context: dict[str, Any] = {
        "config": cfg,
        "artifacts": {"steps": []},
    }
    total_steps = len(STEP_FILES)
    for step_index, step_file in enumerate(STEP_FILES, start=1):
        step_path = Path(step_file)
        run_step = _load_step(step_path)
        step_title = STEP_TITLES.get(step_file, step_path.stem)
        log_step_banner(step_index, total_steps, step_title)
        started_at = time.perf_counter()
        context = run_step(context)
        elapsed_sec = time.perf_counter() - started_at
        context["artifacts"]["steps"].append(step_file)
        logging.info("Step %s done (%.2fs)", step_index, elapsed_sec)
        if cfg["runtime"].get("dry_run") and step_file == STEP_FILES[0]:
            logging.info("Dry run requested; stopping after input validation.")
            break

    logging.info("Pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
