"""Compare curated stable output files by filename and MD5 hash."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


STABLE_SUFFIXES = {
    "all_cluster_labels.csv",
    "all_cluster_members.csv",
    "all_clustering_metadata.csv",
    "all_minimal_units_H_long.csv",
    "all_minimal_units_W.csv",
    "all_representative_H_posthoc_long.csv",
    "all_representative_W_posthoc.csv",
    "final_summary.csv",
}


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _stable_files(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name in STABLE_SUFFIXES:
            files[str(path.relative_to(root))] = _md5(path)
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
