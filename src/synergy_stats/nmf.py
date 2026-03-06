"""Extract synergy matrices from trial EMG segments."""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class FeatureBundle:
    """Feature matrices and metadata for one trial."""

    W_muscle: np.ndarray
    H_time: np.ndarray
    meta: dict[str, Any]


def _fit_rank_sklearn(X_trial: np.ndarray, rank: int, cfg: dict[str, Any]):
    from sklearn.decomposition import NMF
    from sklearn.exceptions import ConvergenceWarning

    max_iter = max(int(cfg.get("fit_params", {}).get("max_iter", 1000)), 5000)
    model = NMF(
        n_components=rank,
        init="nndsvda",
        random_state=int(cfg.get("random_state", 42)),
        max_iter=max_iter,
        tol=float(cfg.get("fit_params", {}).get("tol", 1e-4)),
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        H_time = model.fit_transform(X_trial)
    W_muscle = model.components_.T
    return W_muscle.astype(np.float32), H_time.astype(np.float32)


def _fit_rank_torchnmf(X_trial: np.ndarray, rank: int, cfg: dict[str, Any]):
    import torch
    import torchnmf

    X = torch.from_numpy(X_trial.astype(np.float32))
    model = torchnmf.nmf.NMF(X.shape, rank=rank)
    fit_kwargs = {
        "max_iter": int(cfg.get("fit_params", {}).get("max_iter", 1000)),
        "tol": float(cfg.get("fit_params", {}).get("tol", 1e-4)),
    }
    beta = cfg.get("fit_params", {}).get("beta")
    if beta is not None:
        fit_kwargs["beta"] = beta
    model.fit(X, **fit_kwargs)
    left, right = model.W, model.H
    frames, channels = X.shape
    if left.shape[0] == frames and right.shape[0] == channels:
        H_time, W_muscle = left, right
    else:
        H_time, W_muscle = right, left
    return W_muscle.detach().cpu().numpy(), H_time.detach().cpu().numpy()


def _fit_rank(X_trial: np.ndarray, rank: int, cfg: dict[str, Any]):
    backend = str(cfg.get("backend", "auto")).strip().lower()
    if backend not in {"auto", "torchnmf", "sklearn_nmf"}:
        raise ValueError(f"Unsupported feature_extractor backend: {backend}")
    if backend in {"auto", "torchnmf"}:
        try:
            return _fit_rank_torchnmf(X_trial, rank, cfg), "torchnmf"
        except Exception:
            if backend == "torchnmf":
                raise
    return _fit_rank_sklearn(X_trial, rank, cfg), "sklearn_nmf"


def _normalize_components(W_muscle: np.ndarray, H_time: np.ndarray):
    norms = np.linalg.norm(W_muscle, axis=0)
    norms = np.where(norms <= 0, 1.0, norms)
    return W_muscle / norms, H_time * norms


def _compute_vaf(X_trial: np.ndarray, W_muscle: np.ndarray, H_time: np.ndarray) -> float:
    reconstructed = H_time @ W_muscle.T
    total_ss = float(np.sum(X_trial**2))
    if total_ss <= 0:
        return 0.0
    residual_ss = float(np.sum((X_trial - reconstructed) ** 2))
    return 1.0 - (residual_ss / total_ss)


def extract_trial_features(X_trial: np.ndarray, cfg: dict[str, Any]) -> FeatureBundle:
    trial = np.maximum(np.asarray(X_trial, dtype=np.float32), 0.0)
    nmf_cfg = cfg.get("feature_extractor", {}).get("nmf", {})
    vaf_threshold = float(nmf_cfg.get("vaf_threshold", 0.90))
    max_components = int(nmf_cfg.get("max_components_to_try", min(trial.shape)))
    if trial.ndim != 2 or trial.shape[0] == 0 or trial.shape[1] == 0:
        raise ValueError("X_trial must have shape (frames, channels) with non-zero sizes.")

    start = time.perf_counter()
    best = None
    best_backend = None
    for rank in range(1, max_components + 1):
        (W_muscle, H_time), backend = _fit_rank(trial, rank, nmf_cfg)
        W_norm, H_scaled = _normalize_components(W_muscle, H_time)
        vaf = _compute_vaf(trial, W_norm, H_scaled)
        if best is None or vaf > best["vaf"]:
            best = {"rank": rank, "W": W_norm, "H": H_scaled, "vaf": vaf}
            best_backend = backend
        if vaf >= vaf_threshold:
            break
    elapsed = time.perf_counter() - start
    if best is None:
        raise RuntimeError("NMF failed to produce any candidate solution.")
    return FeatureBundle(
        W_muscle=best["W"],
        H_time=best["H"],
        meta={
            "status": "ok",
            "n_components": best["rank"],
            "vaf": float(best["vaf"]),
            "extractor_type": "nmf",
            "extractor_backend": best_backend,
            "extractor_metric_elapsed_sec": elapsed,
        },
    )


def _trial_nmf(X_trial: np.ndarray, nmf_cfg: dict[str, Any]):
    """Compatibility wrapper returning the reference tuple contract."""
    bundle = extract_trial_features(X_trial, {"feature_extractor": {"nmf": nmf_cfg}})
    return bundle.W_muscle, bundle.H_time, bundle.meta


def trial_nmf(X_trial: np.ndarray, nmf_cfg: dict[str, Any]):
    """Public alias for contract-style tests and wrappers."""
    return _trial_nmf(X_trial, nmf_cfg)
