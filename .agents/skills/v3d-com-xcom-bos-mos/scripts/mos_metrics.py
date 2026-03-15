"""XCoM, BoS and MoS computations.

Implements:
- XCoM (Extrapolated CoM) using Hof inverted-pendulum scaling
- Foot landmark generation (virtual medial/lateral edges)
- BoS convex hull polygon (single/double support)
- Signed MoS = signed minimal distance from XCoM to BoS boundary

The intent is to mirror the logic used in Visual3D tutorials:
(1) COM -> (2) XCoM -> (3) BoS landmarks -> (4) distance-to-boundary MoS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


def normalize(v: np.ndarray, axis: int = -1, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(v, axis=axis, keepdims=True)
    n = np.maximum(n, eps)
    return v / n


def compute_xcom(com: np.ndarray, fs_hz: float, leg_length_m: float, g: float = 9.81) -> Tuple[np.ndarray, np.ndarray, float]:
    """Compute XCoM and COM velocity.

    Returns:
        xcom: (n_frames,3)
        com_vel: (n_frames,3)
        omega0: float
    """
    dt = 1.0 / fs_hz
    com_vel = np.gradient(com, dt, axis=0)
    omega0 = math.sqrt(g / leg_length_m)
    xcom = com + com_vel / omega0
    return xcom, com_vel, omega0


@dataclass
class FootLandmarks:
    """Four-point foot support polygon in 3D."""

    # Order: heel_med, heel_lat, toe_lat, toe_med
    vertices_3d: np.ndarray  # (n_frames,4,3)


def compute_foot_landmarks(
    heel: np.ndarray,
    toe: np.ndarray,
    lat_ankle: np.ndarray,
    med_ankle: np.ndarray,
    forefoot_width_m: float,
    rearfoot_width_m: float,
    up_axis: np.ndarray,
) -> FootLandmarks:
    """Create 4 support landmarks for a foot.

    Landmarks are synthesized as medial/lateral offsets from the toe and heel markers.

    Args:
        heel, toe, lat_ankle, med_ankle: arrays (n_frames,3)
        forefoot_width_m: used at toe (forefoot)
        rearfoot_width_m: used at heel (rearfoot)
        up_axis: 3D unit vector for the global 'up' direction
    """

    # Foot mediolateral axis: from medial to lateral ankle
    lat_axis = normalize(lat_ankle - med_ankle)

    # Foot longitudinal axis: heel -> toe
    long_axis = normalize(toe - heel)

    # Provisional vertical axis
    vert_axis = normalize(np.cross(long_axis, lat_axis))

    # Flip if not aligned with global up
    dot_up = np.sum(vert_axis * up_axis, axis=1)
    flip = dot_up < 0
    vert_axis[flip] *= -1

    # Re-orthogonalize lat_axis in the foot plane
    lat_axis = normalize(np.cross(vert_axis, long_axis))

    # Build 4 landmarks
    toe_lat = toe + lat_axis * (forefoot_width_m / 2.0)
    toe_med = toe - lat_axis * (forefoot_width_m / 2.0)
    heel_lat = heel + lat_axis * (rearfoot_width_m / 2.0)
    heel_med = heel - lat_axis * (rearfoot_width_m / 2.0)

    verts = np.stack([heel_med, heel_lat, toe_lat, toe_med], axis=1)
    return FootLandmarks(vertices_3d=verts)


def convex_hull(points: np.ndarray) -> np.ndarray:
    """Convex hull for 2D points (Andrew monotone chain).

    Returns vertices in CCW order, not repeating the first vertex.
    """
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError("convex_hull expects shape (N,2)")

    pts_unique = np.unique(pts, axis=0)
    if len(pts_unique) <= 1:
        return pts_unique

    pts_sorted = pts_unique[np.lexsort((pts_unique[:, 1], pts_unique[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts_sorted:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(tuple(p))

    upper = []
    for p in reversed(pts_sorted):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(tuple(p))

    hull = lower[:-1] + upper[:-1]
    return np.array(hull, dtype=float)


def point_in_polygon(point: np.ndarray, poly: np.ndarray) -> bool:
    """Ray casting point-in-polygon test."""
    x, y = float(point[0]), float(point[1])
    poly = np.asarray(poly, dtype=float)
    n = len(poly)
    if n < 3:
        return False

    inside = False
    x0, y0 = poly[0]
    for i in range(1, n + 1):
        x1, y1 = poly[i % n]
        if (y0 > y) != (y1 > y):
            x_intersect = (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0
            if x < x_intersect:
                inside = not inside
        x0, y0 = x1, y1

    return inside


def distance_point_to_segment(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    p = np.asarray(p, dtype=float)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ab = b - a
    ap = p - a
    ab_len2 = float(np.dot(ab, ab))
    if ab_len2 < 1e-12:
        return float(np.linalg.norm(p - a))
    t = float(np.dot(ap, ab) / ab_len2)
    t = max(0.0, min(1.0, t))
    proj = a + t * ab
    return float(np.linalg.norm(p - proj))


def signed_distance_to_polygon(point: np.ndarray, poly: np.ndarray) -> float:
    poly = np.asarray(poly, dtype=float)
    if len(poly) < 3:
        return float('nan')

    dists = []
    for i in range(len(poly)):
        a = poly[i]
        b = poly[(i + 1) % len(poly)]
        dists.append(distance_point_to_segment(point, a, b))

    min_d = float(np.min(dists))
    inside = point_in_polygon(point, poly)
    return min_d if inside else -min_d


@dataclass
class MoSResult:
    xcom: np.ndarray  # (n_frames,3)
    com_vel: np.ndarray  # (n_frames,3)
    omega0: float
    mos: np.ndarray  # (n_frames,)
    bos_hulls_2d: List[Optional[np.ndarray]]  # per-frame hull in 2D


def compute_mos(
    com: np.ndarray,
    fs_hz: float,
    leg_length_m: float,
    left_foot: FootLandmarks,
    right_foot: FootLandmarks,
    plane_axes: Tuple[int, int] = (0, 1),
    step_onset_frame: Optional[int] = None,
    step_side: Optional[str] = None,
) -> MoSResult:
    """Compute signed MoS time series.

    Args:
        com: (n_frames,3)
        plane_axes: which axes define the ground plane (default (0,1) => X-Y)
        step_onset_frame: if provided, use it to switch from double to single support
        step_side: 'L' or 'R' to indicate which foot steps (becomes non-contact)
    """

    xcom, com_vel, omega0 = compute_xcom(com, fs_hz, leg_length_m)

    xcom_2d = xcom[:, list(plane_axes)]

    mos = np.full((len(com),), np.nan)
    hulls: List[Optional[np.ndarray]] = []

    for i in range(len(com)):
        left_contact = True
        right_contact = True

        if step_onset_frame is not None and step_side is not None:
            if i >= step_onset_frame:
                if step_side.lower().startswith('l'):
                    left_contact = False
                elif step_side.lower().startswith('r'):
                    right_contact = False

        pts = []
        if left_contact:
            pts.append(left_foot.vertices_3d[i][:, list(plane_axes)])
        if right_contact:
            pts.append(right_foot.vertices_3d[i][:, list(plane_axes)])

        if not pts:
            hulls.append(None)
            continue

        all_pts = np.vstack(pts)
        hull = convex_hull(all_pts)
        mos[i] = signed_distance_to_polygon(xcom_2d[i], hull)
        hulls.append(hull)

    return MoSResult(
        xcom=xcom,
        com_vel=com_vel,
        omega0=omega0,
        mos=mos,
        bos_hulls_2d=hulls,
    )
