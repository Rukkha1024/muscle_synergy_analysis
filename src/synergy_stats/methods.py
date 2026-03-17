"""Resolve user-facing synergy analysis modes.

This helper normalizes CLI and YAML mode values,
keeps compatibility aliases internal, and returns
the ordered list of modes executed in one run.
"""

from __future__ import annotations


_MODE_ALIASES = {
    "trialwise": "trialwise",
    "trial_clustered": "trialwise",
    "concatenated": "concatenated",
    "both": "both",
}


def normalize_analysis_mode(value: object) -> str:
    text = str(value or "both").strip().lower() or "both"
    try:
        return _MODE_ALIASES[text]
    except KeyError as exc:
        raise ValueError(
            "Unsupported synergy analysis mode. Expected one of: "
            "`trialwise`, `concatenated`, or `both`."
        ) from exc


def resolve_analysis_modes(value: object) -> list[str]:
    mode = normalize_analysis_mode(value)
    if mode == "both":
        return ["trialwise", "concatenated"]
    return [mode]


def primary_analysis_mode(modes: list[str]) -> str:
    if not modes:
        raise ValueError("Expected at least one resolved analysis mode.")
    return str(modes[0])
