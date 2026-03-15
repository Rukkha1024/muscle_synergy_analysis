"""Event table access for perturb_inform.xlsm.

The project stores platform onset/offset and step onset in an Excel macro-enabled workbook.

This module provides utilities to:
- load the platform sheet
- match a row by (subject, velocity, trial)
- interpret stepping side from the 'state' column
- compute frame indices in a potentially trimmed C3D file

Assumptions:
- If the C3D is trimmed, it spans [platform_onset-100, platform_offset+100].
- If the C3D is untrimmed, event frames are assumed to be in the same numbering as the C3D header frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class PerturbEvents:
    subject: str
    velocity: float
    trial: int
    state: str
    platform_onset: int
    platform_offset: int
    step_onset: Optional[int]


def load_platform_sheet(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_excel(path, sheet_name="platform")
    return df


def find_event_row(df: pd.DataFrame, subject: str, velocity: float, trial: int) -> PerturbEvents:
    # Exact match with some tolerance for floats
    sub = df[(df["subject"] == subject) & (df["trial"] == trial) & (np.isclose(df["velocity"], velocity))]
    if len(sub) == 0:
        raise ValueError(f"No event row found for subject={subject}, velocity={velocity}, trial={trial}")
    if len(sub) > 1:
        # Prefer first; user can disambiguate upstream
        sub = sub.iloc[[0]]

    row = sub.iloc[0]

    step_onset = row.get("step_onset")
    step_onset_i = None if pd.isna(step_onset) else int(round(float(step_onset)))

    return PerturbEvents(
        subject=str(row["subject"]),
        velocity=float(row["velocity"]),
        trial=int(row["trial"]),
        state=str(row.get("state", "")),
        platform_onset=int(round(float(row["platform_onset"]))),
        platform_offset=int(round(float(row["platform_offset"]))),
        step_onset=step_onset_i,
    )


def infer_step_side(state: str) -> Optional[str]:
    s = (state or "").lower().strip()
    if "step_l" in s:
        return "L"
    if "step_r" in s:
        return "R"
    return None


def infer_trial_velocity_from_filename(filename: str) -> Tuple[Optional[float], Optional[int]]:
    """Parse velocity and trial from {date}_{initial}_perturb_{velocity}_{trial}.c3d."""
    name = Path(filename).name
    stem = name.rsplit(".", 1)[0]
    parts = stem.split("_")
    # Expect at least: date, initial, perturb, velocity, trial
    if len(parts) < 5:
        return None, None
    # Find 'perturb' token
    try:
        i = parts.index("perturb")
    except ValueError:
        # Some files may have 'perturb' embedded; fall back to fixed indices
        i = 2
    vel = None
    tr = None
    if i + 1 < len(parts):
        try:
            vel = float(parts[i + 1])
        except Exception:
            vel = None
    if i + 2 < len(parts):
        try:
            tr = int(parts[i + 2])
        except Exception:
            tr = None
    return vel, tr


def map_events_into_c3d_frames(
    events_abs: PerturbEvents,
    c3d_first_frame: int,
    n_frames: int,
    assume_trimmed_rule: bool = True,
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Return (platform_onset_frame, platform_offset_frame, step_onset_frame) in C3D frame indices.

    Strategy:
    1) If absolute event frame - c3d_first_frame falls inside the file range, use it.
    2) Else, if assume_trimmed_rule, assume file starts at platform_onset-100.

    Returns None for any event that cannot be mapped into the file range.
    """

    def in_range(idx: int) -> bool:
        return 0 <= idx < n_frames

    # Candidate: direct mapping using c3d_first_frame
    po = events_abs.platform_onset - c3d_first_frame
    pf = events_abs.platform_offset - c3d_first_frame
    so = None if events_abs.step_onset is None else events_abs.step_onset - c3d_first_frame

    if in_range(po) and in_range(pf) and (so is None or in_range(so)):
        return int(po), int(pf), None if so is None else int(so)

    if not assume_trimmed_rule:
        return None, None, None

    # Candidate: trimmed file rule
    start_abs = events_abs.platform_onset - 100
    po2 = events_abs.platform_onset - start_abs
    pf2 = events_abs.platform_offset - start_abs
    so2 = None if events_abs.step_onset is None else events_abs.step_onset - start_abs

    po2_i = int(round(po2))
    pf2_i = int(round(pf2))
    so2_i = None if so2 is None else int(round(so2))

    po_ok = in_range(po2_i)
    pf_ok = in_range(pf2_i)
    so_ok = (so2_i is None) or in_range(so2_i)

    if po_ok and pf_ok and so_ok:
        return po2_i, pf2_i, so2_i

    return None, None, None
