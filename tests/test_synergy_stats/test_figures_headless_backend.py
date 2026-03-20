"""Ensure synergy figures render without GUI/Qt backends.

This regression test protects WSL/headless runs from Qt platform plugin
warnings by asserting the figures module forces a non-interactive backend
and can save both group-level and trial-level figures in a fresh process.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_figures_module_forces_agg_backend_and_saves(tmp_path: Path) -> None:
    group_output_path = tmp_path / "cluster.png"
    trial_output_path = tmp_path / "trial_김철수_v30_T2_step_nmf.png"
    code = f"""
import json
from pathlib import Path

import pandas as pd

from src.synergy_stats.figures import save_group_cluster_figure, save_trial_nmf_figure

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
trial_w = pd.DataFrame({{
    "component_index": [0, 0],
    "assigned_cluster_id": [4, 4],
    "muscle": ["TA", "MG"],
    "W_value": [0.3, 0.7],
}})
trial_h = pd.DataFrame({{
    "component_index": [0, 0, 0],
    "assigned_cluster_id": [4, 4, 4],
    "frame_idx": [0, 1, 2],
    "h_value": [0.1, 0.2, 0.3],
}})

cfg = {{"figures": {{"format": "png", "dpi": 72}}}}
group_output_path = Path({str(group_output_path)!r})
trial_output_path = Path({str(trial_output_path)!r})
save_group_cluster_figure(
    group_id="global_step",
    rep_w=rep_w,
    rep_h=rep_h,
    muscle_names=["TA", "MG"],
    cfg=cfg,
    output_path=group_output_path,
)
save_trial_nmf_figure(
    subject="김철수",
    velocity=30,
    trial_num=2,
    step_class="step",
    trial_w=trial_w,
    trial_h=trial_h,
    muscle_names=["TA", "MG"],
    cfg=cfg,
    output_path=trial_output_path,
)

import matplotlib
print(json.dumps({{
    "backend": matplotlib.get_backend(),
    "group_exists": group_output_path.exists(),
    "trial_exists": trial_output_path.exists(),
}}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "qt.qpa.plugin" not in (result.stdout + result.stderr).lower()
    assert "glyph" not in (result.stdout + result.stderr).lower()
    assert group_output_path.exists()
    assert group_output_path.stat().st_size > 0
    assert trial_output_path.exists()
    assert trial_output_path.stat().st_size > 0
    assert "\"backend\": \"Agg\"" in result.stdout or "\"backend\": \"agg\"" in result.stdout
