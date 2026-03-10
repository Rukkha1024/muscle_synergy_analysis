"""Ensure synergy cluster figures render without GUI/Qt backends.

This regression test protects WSL/headless runs from Qt platform plugin
warnings by asserting the figures module forces a non-interactive backend
and can save a representative cluster figure in a fresh Python process.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_figures_module_forces_agg_backend_and_saves(tmp_path: Path) -> None:
    output_path = tmp_path / "cluster.png"
    output_path_str = str(output_path)
    code = f"""
import json
from pathlib import Path

import pandas as pd

from src.synergy_stats.figures import save_group_cluster_figure

rep_w = pd.DataFrame({{
    "cluster_id": [0, 0],
    "muscle": ["TA", "MG"],
    "W_value": [0.3, 0.7],
}})
rep_h = pd.DataFrame({{
    "cluster_id": [0, 0, 0],
    "frame_idx": [0, 1, 2],
    "h_value": [0.1, 0.2, 0.3],
}})

cfg = {{"figures": {{"format": "png", "dpi": 72}}}}
output_path = Path({output_path_str!r})
save_group_cluster_figure(
    group_id="global_step",
    rep_w=rep_w,
    rep_h=rep_h,
    muscle_names=["TA", "MG"],
    cfg=cfg,
    output_path=output_path,
)

import matplotlib
print(json.dumps({{"backend": matplotlib.get_backend(), "exists": output_path.exists()}}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "qt.qpa.plugin" not in (result.stdout + result.stderr).lower()
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert "\"backend\": \"Agg\"" in result.stdout or "\"backend\": \"agg\"" in result.stdout
