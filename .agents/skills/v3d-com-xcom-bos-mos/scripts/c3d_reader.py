"""Minimal C3D reader focused on point (marker) trajectories.

Design goals:
- Pure-Python + NumPy (no external C3D libs required)
- Robust enough for OptiTrack/Motive exports with float point data
- Provides: sampling rate, point labels, point XYZ trajectories

Supported:
- C3D with point data stored as float32 (POINT:SCALE < 0)
- Analog data may be present; it is skipped/ignored

Not supported (by design):
- Complex non-standard parameter encodings
- Integer point data with scaling (can be added if needed)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import numpy as np


@dataclass
class C3DHeader:
    param_start_block: int
    num_points: int
    num_analog_total_samples_per_frame: int
    first_frame: int
    last_frame: int
    scale_factor: float
    data_start_block: int
    analog_samples_per_frame_per_channel: int
    frame_rate_hz: float


def _read_header(f) -> C3DHeader:
    f.seek(0)
    hdr = f.read(512)
    if len(hdr) != 512:
        raise ValueError("File too small for C3D header")

    param_start_block = hdr[0]
    num_points = struct.unpack('<H', hdr[2:4])[0]
    num_analog = struct.unpack('<H', hdr[4:6])[0]
    first_frame = struct.unpack('<H', hdr[6:8])[0]
    last_frame = struct.unpack('<H', hdr[8:10])[0]
    scale_factor = struct.unpack('<f', hdr[12:16])[0]
    data_start_block = struct.unpack('<H', hdr[16:18])[0]
    analog_per_frame = struct.unpack('<H', hdr[18:20])[0]
    frame_rate = struct.unpack('<f', hdr[20:24])[0]

    return C3DHeader(
        param_start_block=param_start_block,
        num_points=num_points,
        num_analog_total_samples_per_frame=num_analog,
        first_frame=first_frame,
        last_frame=last_frame,
        scale_factor=scale_factor,
        data_start_block=data_start_block,
        analog_samples_per_frame_per_channel=analog_per_frame,
        frame_rate_hz=frame_rate,
    )


def _parse_char_array(raw_bytes: bytes, dims: List[int]) -> List[str]:
    """Convert C3D char array bytes to list of strings."""
    if not dims:
        return [raw_bytes.decode('latin-1').rstrip('\x00').rstrip()]

    # Typical shapes:
    # - [nchar] single string
    # - [nchar, nstr] list of nstr fixed-width strings
    if len(dims) == 1:
        nchar = dims[0]
        return [
            raw_bytes[i:i + nchar].decode('latin-1').rstrip('\x00').rstrip()
            for i in range(0, len(raw_bytes), nchar)
        ]

    nchar = dims[0]
    nstr = dims[1]
    out: List[str] = []
    for i in range(nstr):
        chunk = raw_bytes[i * nchar:(i + 1) * nchar]
        out.append(chunk.decode('latin-1').rstrip('\x00').rstrip())
    return out


def _parse_parameters_sequential(f, param_start_block: int) -> Dict[str, Any]:
    """Parse parameter section sequentially (ignores offset fields).

    Works for typical Motive exports.
    """
    f.seek((param_start_block - 1) * 512)
    header4 = f.read(4)
    if len(header4) < 4:
        raise ValueError("Unable to read parameter header")

    # Observed layout for many files: [0, 0, num_blocks, processor]
    num_param_blocks = header4[2]
    processor_type = header4[3]

    little = processor_type in (84, 85)  # Intel or DEC
    endian = '<' if little else '>'

    groups: Dict[int, Dict[str, Any]] = {}

    while True:
        b = f.read(2)
        if len(b) < 2:
            raise ValueError("Unexpected EOF in parameter section")

        name_len = struct.unpack('b', b[0:1])[0]
        group_id = struct.unpack('b', b[1:2])[0]

        if name_len == 0:
            break

        name = f.read(abs(name_len)).decode('latin-1')
        _offset = struct.unpack(endian + 'h', f.read(2))[0]  # ignored

        if group_id < 0:
            gid = -group_id
            desc_len = struct.unpack('B', f.read(1))[0]
            desc = f.read(desc_len).decode('latin-1') if desc_len else ''
            groups.setdefault(gid, {"name": name, "desc": desc, "params": {}})
            groups[gid]["name"] = name
            groups[gid]["desc"] = desc
            continue

        gid = group_id
        data_type = struct.unpack('b', f.read(1))[0]
        dim_count = struct.unpack('B', f.read(1))[0]
        dims = [struct.unpack('B', f.read(1))[0] for _ in range(dim_count)]

        n_elems = 1
        for d in dims:
            n_elems *= d
        if dim_count == 0:
            n_elems = 1

        if data_type == -1:
            data = f.read(n_elems)
        elif data_type == 1:
            data = list(struct.unpack(endian + 'b' * n_elems, f.read(n_elems)))
        elif data_type == 2:
            data = list(struct.unpack(endian + 'h' * n_elems, f.read(2 * n_elems)))
        elif data_type == 4:
            data = list(struct.unpack(endian + 'f' * n_elems, f.read(4 * n_elems)))
        else:
            raise ValueError(f"Unsupported parameter data type {data_type} for {name}")

        desc_len = struct.unpack('B', f.read(1))[0]
        desc = f.read(desc_len).decode('latin-1') if desc_len else ''

        groups.setdefault(gid, {"name": f"GROUP_{gid}", "desc": "", "params": {}})
        groups[gid]["params"][name] = {
            "type": data_type,
            "dims": dims,
            "data": data,
            "desc": desc,
        }

    # Build name-keyed group dict
    by_name: Dict[str, Dict[str, Any]] = {}
    for gid, g in groups.items():
        by_name[g["name"]] = g

    return {
        "num_param_blocks": num_param_blocks,
        "processor_type": processor_type,
        "groups": groups,
        "by_name": by_name,
        "endian": endian,
    }


def read_c3d_points(path: str | Path) -> Tuple[C3DHeader, List[str], np.ndarray]:
    """Read marker trajectories from a C3D.

    Returns:
        header: C3DHeader
        labels: list of POINT:LABELS (strings)
        xyz: ndarray float64 of shape (n_frames, n_points, 3)
    """
    path = Path(path)
    with path.open('rb') as f:
        header = _read_header(f)
        params = _parse_parameters_sequential(f, header.param_start_block)

        if "POINT" not in params["by_name"]:
            raise ValueError("Missing POINT group in C3D parameters")

        point_group = params["by_name"]["POINT"]
        point_params = point_group["params"]

        labels_param = point_params.get("LABELS")
        if labels_param is None:
            raise ValueError("Missing POINT:LABELS")

        if labels_param["type"] != -1:
            raise ValueError("POINT:LABELS expected char array")

        labels = _parse_char_array(labels_param["data"], labels_param["dims"])

        n_frames = header.last_frame - header.first_frame + 1
        n_points = header.num_points

        if header.scale_factor >= 0:
            raise ValueError(
                "This reader currently supports float point data (POINT:SCALE < 0). "
                "If your file stores integer point data, extend this reader."
            )

        # Data start is 1-indexed block
        data_start = (header.data_start_block - 1) * 512
        f.seek(data_start)

        # Each point has 4 float values: X, Y, Z, residual
        n_point_vals = n_points * 4
        n_analog_vals = header.num_analog_total_samples_per_frame
        frame_vals = n_point_vals + n_analog_vals

        total_vals = n_frames * frame_vals
        data = np.fromfile(f, dtype=np.float32, count=total_vals)
        if data.size != total_vals:
            raise ValueError(f"Expected {total_vals} float32 values, got {data.size}")

        data = data.reshape((n_frames, frame_vals))
        point_data = data[:, :n_point_vals].reshape((n_frames, n_points, 4))
        xyz = point_data[..., :3].astype(np.float64)

        return header, labels, xyz


def detect_common_prefix(labels: List[str]) -> str:
    """Detect a common prefix across labels.

    Strategy:
    - Find the longest common prefix.
    - Trim back to the last underscore to avoid cutting a base name.

    If no underscore exists, returns the raw common prefix.
    """
    if not labels:
        return ""

    # Longest common prefix
    prefix = labels[0]
    for lab in labels[1:]:
        i = 0
        n = min(len(prefix), len(lab))
        while i < n and prefix[i] == lab[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break

    if '_' in prefix:
        prefix = prefix[:prefix.rfind('_') + 1]

    return prefix


def strip_prefix(labels: List[str], prefix: str) -> List[str]:
    if not prefix:
        return labels
    out: List[str] = []
    for lab in labels:
        out.append(lab[len(prefix):] if lab.startswith(prefix) else lab)
    return out
