"""Compare stable global step/nonstep output files by relative path and MD5."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


STABLE_RELATIVE_PATHS = {
    "all_cluster_labels.csv",
    "all_cluster_members.csv",
    "all_clustering_metadata.csv",
    "all_minimal_units_H_long.csv",
    "all_minimal_units_W.csv",
    "all_representative_H_posthoc_long.csv",
    "all_representative_W_posthoc.csv",
    "all_trial_window_metadata.csv",
    "final_summary.csv",
    "global_step/clustering_metadata.csv",
    "global_step/cluster_labels.csv",
    "global_step/cluster_members.csv",
    "global_step/minimal_units_H_long.csv",
    "global_step/minimal_units_W.csv",
    "global_step/representative_H_posthoc_long.csv",
    "global_step/representative_W_posthoc.csv",
    "global_step/trial_window_metadata.csv",
    "global_nonstep/clustering_metadata.csv",
    "global_nonstep/cluster_labels.csv",
    "global_nonstep/cluster_members.csv",
    "global_nonstep/minimal_units_H_long.csv",
    "global_nonstep/minimal_units_W.csv",
    "global_nonstep/representative_H_posthoc_long.csv",
    "global_nonstep/representative_W_posthoc.csv",
    "global_nonstep/trial_window_metadata.csv",
}


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _stable_files(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative_path = str(path.relative_to(root))
        if path.is_file() and relative_path in STABLE_RELATIVE_PATHS:
            files[relative_path] = _md5(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Curated MD5 comparison for stable EMG outputs.")
    parser.add_argument("--base", required=True, help="Reference output directory.")
    parser.add_argument("--new", required=True, help="New output directory.")
    args = parser.parse_args()
    base_map = _stable_files(Path(args.base))
    new_map = _stable_files(Path(args.new))
    all_keys = sorted(set(base_map) | set(new_map))
    diffs = [key for key in all_keys if base_map.get(key) != new_map.get(key)]
    if diffs:
        for key in diffs:
            print(f"DIFF {key}: base={base_map.get(key)} new={new_map.get(key)}")
        return 1
    print("MD5 comparison passed for curated stable files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
