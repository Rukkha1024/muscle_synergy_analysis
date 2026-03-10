"""NMF extraction contract scaffolds."""

from __future__ import annotations

import numpy as np
import pytest

from tests.helpers import resolve_callable


def _synthetic_trial_matrix() -> np.ndarray:
    """Create an exact nonnegative rank-2 matrix for NMF checks."""
    h_time = np.array(
        [
            [1.0, 0.2],
            [0.9, 0.3],
            [0.7, 0.5],
            [0.5, 0.7],
            [0.3, 0.9],
            [0.2, 1.0],
        ],
        dtype=np.float32,
    )
    w_muscle = np.array(
        [
            [0.9, 0.1],
            [0.7, 0.2],
            [0.1, 0.8],
            [0.2, 0.9],
        ],
        dtype=np.float32,
    )
    return h_time @ w_muscle.T


def test_nmf_returns_normalized_weights_and_vaf() -> None:
    """NMF output should keep W columns unit-normalized and fit the input well."""
    try:
        nmf_func, module_name, attr_name = resolve_callable(
            [
                "src.synergy_stats",
                "src.synergy_stats.nmf",
                "src.synergy_stats.pipeline",
            ],
            [
                "run_trial_nmf",
                "trial_nmf",
                "_trial_nmf",
            ],
        )
    except LookupError as exc:
        pytest.xfail(f"NMF callable is not implemented yet: {exc}")

    x_trial = _synthetic_trial_matrix()
    cfg = {
        "vaf_threshold": 0.9,
        "max_components_to_try": 4,
        "fit_params": {"max_iter": 1000, "tol": 1e-4},
    }
    result = nmf_func(x_trial.copy(), cfg)
    if not isinstance(result, tuple) or len(result) < 3:
        raise AssertionError(f"{module_name}.{attr_name} should return (W, H, meta).")
    w_muscle, h_time, meta = result[:3]

    assert w_muscle.shape[0] == x_trial.shape[1]
    assert h_time.shape[0] == x_trial.shape[0]
    norms = np.linalg.norm(np.asarray(w_muscle), axis=0)
    assert np.allclose(norms, np.ones_like(norms), atol=1e-3)
    assert float(meta["vaf"]) >= 0.9


def test_nmf_rejects_nonpositive_max_iter_for_sklearn_backend() -> None:
    """Non-positive max_iter should raise a clear error (sklearn backend)."""
    try:
        nmf_func, _, _ = resolve_callable(
            [
                "src.synergy_stats",
                "src.synergy_stats.nmf",
                "src.synergy_stats.pipeline",
            ],
            [
                "run_trial_nmf",
                "trial_nmf",
                "_trial_nmf",
            ],
        )
    except LookupError as exc:
        pytest.xfail(f"NMF callable is not implemented yet: {exc}")

    x_trial = _synthetic_trial_matrix()
    cfg = {
        "backend": "sklearn_nmf",
        "vaf_threshold": 0.9,
        "max_components_to_try": 2,
        "fit_params": {"max_iter": 0, "tol": 1e-4},
    }
    with pytest.raises(ValueError, match="max_iter must be >= 1"):
        nmf_func(x_trial.copy(), cfg)


def test_nmf_rejects_nonpositive_max_iter_for_torchnmf_backend() -> None:
    """Non-positive max_iter should raise a clear error (torchnmf backend)."""
    try:
        import torchnmf  # noqa: F401
    except Exception:
        pytest.skip("torchnmf is not available in this environment.")

    try:
        nmf_func, _, _ = resolve_callable(
            [
                "src.synergy_stats",
                "src.synergy_stats.nmf",
                "src.synergy_stats.pipeline",
            ],
            [
                "run_trial_nmf",
                "trial_nmf",
                "_trial_nmf",
            ],
        )
    except LookupError as exc:
        pytest.xfail(f"NMF callable is not implemented yet: {exc}")

    x_trial = _synthetic_trial_matrix()
    cfg = {
        "backend": "torchnmf",
        "vaf_threshold": 0.9,
        "max_components_to_try": 2,
        "fit_params": {"max_iter": 0, "tol": 1e-4},
    }
    with pytest.raises(ValueError, match="max_iter must be >= 1"):
        nmf_func(x_trial.copy(), cfg)
