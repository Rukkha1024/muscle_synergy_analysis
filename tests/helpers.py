"""Shared test helpers for fixture-driven contract checks."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import polars as pl
import pytest


def resolve_callable(
    module_candidates: Iterable[str],
    name_candidates: Iterable[str],
) -> tuple[Any, str, str]:
    """Return the first matching callable across candidate modules and names."""
    missing: list[str] = []
    for module_name in module_candidates:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
            continue
        for attr_name in name_candidates:
            func = getattr(module, attr_name, None)
            if callable(func):
                return func, module_name, attr_name
    raise LookupError(
        "No callable found for "
        f"modules={list(module_candidates)} names={list(name_candidates)} missing={missing}"
    )


def repo_python(repo_root: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run a repository command with the current Python interpreter."""
    cmd = [sys.executable, *args]
    return subprocess.run(
        cmd,
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def read_final_parquet(path: Path) -> pl.DataFrame:
    """Load a parquet artifact with Polars for schema assertions."""
    if not path.exists():
        pytest.fail(f"Expected parquet artifact was not written: {path}")
    return pl.read_parquet(path)
