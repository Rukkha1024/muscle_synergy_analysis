"""Whole-body COM estimation.

Goal: provide a COM signal that is close to Visual3D's link-model COM for the
OptiTrack/Motive conventional marker set.

This module implements a pragmatic "model proxy":
- Compute centroids for coarse body segments from their marker groups
- Combine segment centroids using standard segment mass fractions

This is not a full inertial model, but it is often sufficient for perturbation
standing tasks and can be validated directly against a Visual3D COM export.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np


def _normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n = np.maximum(n, eps)
    return v / n


@dataclass
class COMProxyInfo:
    prefix: str
    weights_sum: float
    missing_segments: List[str]


DEFAULT_SEGMENT_MARKERS: Dict[str, List[str]] = {
    # Axial
    "pelvis": ["LASI", "RASI", "LPSI", "RPSI"],
    "trunk": ["C7", "CLAV", "T10", "STRN", "RBAK"],
    "head": ["LFHD", "RFHD", "LBHD", "RBHD"],
    # Upper limbs
    "l_upperarm": ["LSHO", "LUPA", "LELB", "LUArm_3"],
    "r_upperarm": ["RSHO", "RUPA", "RELB", "RUArm_3"],
    "l_forearm": ["LELB", "LFRM", "LWRA", "LWRB", "LFIN"],
    "r_forearm": ["RELB", "RFRM", "RWRA", "RWRB", "RFIN"],
    "l_hand": ["LFIN", "LWRA", "LWRB"],
    "r_hand": ["RFIN", "RWRA", "RWRB"],
    # Lower limbs
    "l_thigh": ["LTHI", "LKNE", "LShin_3"],
    "r_thigh": ["RTHI", "RKNE", "RShin_3"],
    "l_shank": ["LTIB", "LANK", "LFoot_3"],
    "r_shank": ["RTIB", "RANK", "RFoot_3"],
    "l_foot": ["LHEE", "LTOE", "LANK", "LFoot_3"],
    "r_foot": ["RHEE", "RTOE", "RANK", "RFoot_3"],
}

# Standard segment mass fractions (Dempster/Winter-style). These are approximate.
DEFAULT_SEGMENT_MASS_FRACTIONS: Dict[str, float] = {
    "head": 0.0826,
    "trunk": 0.497,
    "pelvis": 0.142,
    "l_upperarm": 0.0271,
    "r_upperarm": 0.0271,
    "l_forearm": 0.0162,
    "r_forearm": 0.0162,
    "l_hand": 0.0061,
    "r_hand": 0.0061,
    "l_thigh": 0.10,
    "r_thigh": 0.10,
    "l_shank": 0.0465,
    "r_shank": 0.0465,
    "l_foot": 0.0145,
    "r_foot": 0.0145,
}


def _segment_centroid(
    xyz: np.ndarray,
    label_to_index: Dict[str, int],
    prefix: str,
    marker_names: List[str],
) -> Optional[np.ndarray]:
    coords = []
    for m in marker_names:
        lab = prefix + m if prefix else m
        idx = label_to_index.get(lab)
        if idx is None:
            continue
        coords.append(xyz[:, idx, :])
    if not coords:
        return None
    return np.mean(np.stack(coords, axis=0), axis=0)


def compute_com_proxy(
    xyz: np.ndarray,
    labels: List[str],
    prefix: str = "",
    segment_markers: Dict[str, List[str]] = DEFAULT_SEGMENT_MARKERS,
    segment_mass_fractions: Dict[str, float] = DEFAULT_SEGMENT_MASS_FRACTIONS,
) -> Tuple[np.ndarray, COMProxyInfo]:
    """Compute whole-body COM as weighted average of coarse segment centroids."""

    label_to_index = {lab: i for i, lab in enumerate(labels)}

    centroids: Dict[str, np.ndarray] = {}
    for seg, markers in segment_markers.items():
        c = _segment_centroid(xyz, label_to_index, prefix, markers)
        if c is not None:
            centroids[seg] = c

    com = np.zeros((xyz.shape[0], 3), dtype=float)
    total_w = 0.0
    missing: List[str] = []

    for seg, w in segment_mass_fractions.items():
        if seg not in centroids:
            missing.append(seg)
            continue
        com += w * centroids[seg]
        total_w += w

    if total_w <= 0:
        raise ValueError("No segments were available to compute COM")

    com /= total_w

    return com, COMProxyInfo(prefix=prefix, weights_sum=total_w, missing_segments=missing)
