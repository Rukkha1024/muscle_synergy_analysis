"""Create per-trial EMG slices and aligned time axes."""

from __future__ import annotations

from src.emg_pipeline import build_trial_records
from src.emg_pipeline.log_utils import compact_list, log_kv_section


def _format_subjects(subjects: list[str]) -> str:
    if not subjects:
        return "0"
    return f"{len(subjects)} ({compact_list(subjects)})"


def _format_velocities(velocities: list[float]) -> str:
    if not velocities:
        return "n/a"
    return compact_list([f"{value:g}" for value in velocities], limit=8)


def run(context: dict) -> dict:
    trial_records = build_trial_records(context["emg_df"], context["config"])
    context["trial_records"] = trial_records
    durations = [
        int(trial.metadata.get("analysis_window_duration_device_frames", trial.offset_device - trial.onset_device))
        for trial in trial_records
    ]
    subjects = sorted({str(trial.key[0]) for trial in trial_records})
    velocities = sorted({float(trial.key[1]) for trial in trial_records})
    log_kv_section(
        "Trial Extraction",
        [
            ("Trials", len(trial_records)),
            ("Duration min", min(durations) if durations else "n/a"),
            ("Duration max", max(durations) if durations else "n/a"),
            ("Subjects", _format_subjects(subjects)),
            ("Velocities", _format_velocities(velocities)),
        ],
    )
    return context
