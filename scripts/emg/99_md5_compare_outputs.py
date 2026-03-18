"""Compare curated pooled-clustering output files by relative path and MD5."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


STABLE_RELATIVE_PATHS = {
    "final.parquet",
    "final_trialwise.parquet",
    "final_concatenated.parquet",
}


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _files_for_paths(root: Path, relative_paths: set[str]) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative_path = str(path.relative_to(root))
        if path.is_file() and relative_path in relative_paths:
            files[relative_path] = _md5(path)
    return files


def _stable_files(root: Path) -> dict[str, str]:
    return _files_for_paths(root, STABLE_RELATIVE_PATHS)


def _figure_relative_paths(root: Path) -> set[str]:
    return {
        str(path.relative_to(root))
        for path in sorted(root.rglob("*"))
        if path.is_file() and "figures" in path.relative_to(root).parts
    }


def _missing_paths(file_map: dict[str, str], required_paths: set[str]) -> list[str]:
    return sorted(required_paths - set(file_map))


def main() -> int:
    parser = argparse.ArgumentParser(description="Curated MD5 comparison for stable EMG outputs.")
    parser.add_argument("--base", required=True, help="Reference output directory.")
    parser.add_argument("--new", required=True, help="New output directory.")
    parser.add_argument(
        "--include-figures",
        action="store_true",
        help="Also compare figure files under figures/ by relative path and MD5.",
    )
    args = parser.parse_args()
    base_root = Path(args.base)
    new_root = Path(args.new)
    required_paths = set(STABLE_RELATIVE_PATHS)
    if args.include_figures:
        required_paths.update(_figure_relative_paths(base_root))
        required_paths.update(_figure_relative_paths(new_root))
    base_map = _files_for_paths(base_root, required_paths)
    new_map = _files_for_paths(new_root, required_paths)
    base_missing = _missing_paths(base_map, required_paths)
    new_missing = _missing_paths(new_map, required_paths)
    if base_missing or new_missing:
        for key in base_missing:
            print(f"MISSING {key}: base=absent new={new_map.get(key, 'absent')}")
        for key in new_missing:
            if key in base_missing:
                continue
            print(f"MISSING {key}: base={base_map.get(key, 'absent')} new=absent")
        return 1
    all_keys = sorted(set(base_map) | set(new_map))
    diffs = [key for key in all_keys if base_map.get(key) != new_map.get(key)]
    if diffs:
        for key in diffs:
            print(f"DIFF {key}: base={base_map.get(key)} new={new_map.get(key)}")
        return 1
    if args.include_figures:
        print("MD5 comparison passed for curated stable files and figures.")
    else:
        print("MD5 comparison passed for curated stable files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
