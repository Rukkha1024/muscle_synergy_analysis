"""Public helpers for EMG table loading and trial preparation."""

from .config import apply_cli_overrides, load_pipeline_config, prepare_runtime_paths, write_run_manifest
from .io import load_emg_table, load_event_metadata, merge_event_metadata
from .trials import build_trial_records

__all__ = [
    "apply_cli_overrides",
    "build_trial_records",
    "load_emg_table",
    "load_event_metadata",
    "load_pipeline_config",
    "merge_event_metadata",
    "prepare_runtime_paths",
    "write_run_manifest",
]
