"""Load merged YAML configs and normalize runtime paths."""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_pipeline_config(global_config_path: str | os.PathLike[str]) -> dict[str, Any]:
    root_path = Path(global_config_path)
    global_cfg = _load_yaml(root_path)
    config_paths = global_cfg.get("config_paths") or global_cfg.get("configs", {})
    if not config_paths:
        raise ValueError("`config_paths` or `configs` is required in the global config.")

    merged = deepcopy(global_cfg)
    for key in ("emg_pipeline", "synergy_stats"):
        if key not in config_paths:
            raise ValueError(f"`config_paths.{key}` or `configs.{key}` is required in the global config.")
        domain_path = (root_path.parent / config_paths[key]).resolve() if not Path(config_paths[key]).is_absolute() else Path(config_paths[key])
        merged = _deep_merge(merged, _load_yaml(domain_path))
    return merged


def apply_cli_overrides(
    cfg: dict[str, Any],
    *,
    parquet_path: str | None,
    meta_xlsm_path: str | None,
    output_dir: str | None,
    mode: str | None,
    dry_run: bool,
    overwrite: bool,
) -> dict[str, Any]:
    updated = deepcopy(cfg)
    updated.setdefault("input", {})
    updated.setdefault("runtime", {})
    updated.setdefault("synergy_analysis", {})
    if parquet_path:
        updated["input"]["emg_parquet_path"] = parquet_path
    if meta_xlsm_path:
        updated["input"]["event_xlsm_path"] = meta_xlsm_path
    if output_dir:
        updated["runtime"]["output_dir"] = output_dir
    if mode:
        updated["synergy_analysis"]["mode"] = mode
    if dry_run:
        updated["runtime"]["dry_run"] = True
    if overwrite:
        updated["runtime"]["overwrite"] = True
    return updated


def prepare_runtime_paths(cfg: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    runtime_cfg = cfg.setdefault("runtime", {})
    output_dir = Path(runtime_cfg.get("output_dir", "outputs/runs/default_run"))
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    outputs_dir = repo_root / "outputs"
    run_id = output_dir.name
    runtime_cfg["run_id"] = run_id
    runtime_cfg["output_dir"] = str(output_dir)
    runtime_cfg["manifest_path"] = str(output_dir / "run_manifest.json")
    runtime_cfg["log_path"] = str(output_dir / "logs" / "run.log")
    runtime_cfg["combined_final_parquet_path"] = str(output_dir / "final.parquet")
    runtime_cfg["final_parquet_path"] = str(outputs_dir / "final.parquet")
    runtime_cfg["final_parquet_alias_paths"] = {
        "trialwise": str(outputs_dir / "final_trialwise.parquet"),
        "concatenated": str(outputs_dir / "final_concatenated.parquet"),
    }
    runtime_cfg["analysis_methods_manifest_path"] = str(output_dir / "analysis_methods_manifest.json")
    return cfg


def stable_config_hash(cfg: dict[str, Any]) -> str:
    encoded = json.dumps(cfg, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def initialize_random_state(cfg: dict[str, Any]) -> int:
    seed = int(cfg.get("runtime", {}).get("seed", 42))
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass
    return seed


def write_run_manifest(cfg: dict[str, Any]) -> Path:
    initialize_random_state(cfg)
    manifest_path = Path(cfg["runtime"]["manifest_path"])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "config_sha256": stable_config_hash(cfg),
        "runtime_seed": int(cfg.get("runtime", {}).get("seed", 42)),
        "run_id": cfg["runtime"]["run_id"],
        "selected_mode": cfg.get("synergy_analysis", {}).get("mode", "trialwise"),
        "analysis_modes": list(cfg.get("runtime", {}).get("analysis_modes", [])),
        "combined_final_parquet_path": cfg.get("runtime", {}).get("combined_final_parquet_path", ""),
        "final_parquet_path": cfg.get("runtime", {}).get("final_parquet_path", ""),
        "final_parquet_alias_paths": cfg.get("runtime", {}).get("final_parquet_alias_paths", {}),
    }
    with manifest_path.open("w", encoding="utf-8-sig") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    return manifest_path
