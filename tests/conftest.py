"""Pytest session fixtures for EMG scaffold verification."""

from pathlib import Path
import sys

import pytest

from tests.fixtures.generate_fixtures import ensure_fixture_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]


if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository root for test helpers."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixture_bundle(repo_root: Path) -> dict[str, Path]:
    """Create reusable synthetic EMG fixture files once per session."""
    return ensure_fixture_bundle(repo_root / "tests" / "fixtures")
