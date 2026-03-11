"""CNN prototype for step vs nonstep EMG trials.

Loads the current normalized EMG input, reuses the repository's
trial filtering/windowing helpers, and evaluates subject-wise
step/nonstep classification with a logistic baseline and a small
1D CNN. Use --dry-run to inspect the filtered trial set first.
"""

from __future__ import annotations

import argparse
import copy
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import polars as pl
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from src.emg_pipeline import build_trial_records, load_emg_table, load_event_metadata, load_pipeline_config, merge_event_metadata


DEFAULT_CONFIG = REPO_ROOT / "configs" / "global_config.yaml"
DEFAULT_TIME_STEPS = 100
DEFAULT_EPOCHS = 24
DEFAULT_BATCH_SIZE = 16
DEFAULT_LR = 1e-3
DEFAULT_SEED = 42
DEFAULT_EXPECTED_TRIALS = 125
DEFAULT_TRIAL_TOLERANCE = 5


@dataclass
class DatasetBundle:
    """Fixed-length tensors and trial metadata for subject-wise evaluation."""

    X: np.ndarray
    y: np.ndarray
    meta: pd.DataFrame
    muscles: list[str]
    input_path: str
    input_label: str


class SmallEmgCnn(nn.Module):
    """Compact 1D CNN for trial-level EMG classification."""

    def __init__(self, in_channels: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(32, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2),
            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(p=0.20),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x)).squeeze(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Global config YAML path.")
    parser.add_argument("--emg-path", type=Path, default=None, help="Optional EMG parquet override.")
    parser.add_argument("--event-xlsm", type=Path, default=None, help="Optional event workbook override.")
    parser.add_argument("--input-label", type=str, default="normalized_minmax", help="Human-readable input label.")
    parser.add_argument("--time-steps", type=int, default=DEFAULT_TIME_STEPS, help="Fixed time steps per trial.")
    parser.add_argument("--splits", type=int, default=5, help="GroupKFold subject-wise split count.")
    parser.add_argument("--cnn-epochs", type=int, default=DEFAULT_EPOCHS, help="Epochs for the 1D CNN.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Mini-batch size for the CNN.")
    parser.add_argument("--lr", type=float, default=DEFAULT_LR, help="Learning rate for the CNN.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed.")
    parser.add_argument(
        "--expected-trials",
        type=int,
        default=DEFAULT_EXPECTED_TRIALS,
        help="Sanity-check target for filtered trial count.",
    )
    parser.add_argument(
        "--trial-tolerance",
        type=int,
        default=DEFAULT_TRIAL_TOLERANCE,
        help="Allowed absolute deviation for the trial-count sanity check.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Load data and print summaries without training.")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch, "use_deterministic_algorithms"):
        torch.use_deterministic_algorithms(True, warn_only=True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    cfg = copy.deepcopy(load_pipeline_config(str(args.config)))
    if args.emg_path is not None:
        cfg.setdefault("input", {})
        cfg["input"]["emg_parquet_path"] = str(args.emg_path)
    if args.event_xlsm is not None:
        cfg.setdefault("input", {})
        cfg["input"]["event_xlsm_path"] = str(args.event_xlsm)
    return cfg


def resample_trial_matrix(values: np.ndarray, target_steps: int) -> np.ndarray:
    """Resample a [frames, channels] trial into [channels, target_steps]."""
    if values.ndim != 2:
        raise ValueError(f"Expected a 2D trial matrix, got shape={values.shape}")
    n_frames, n_channels = values.shape
    if n_frames < 2:
        repeated = np.repeat(values.astype(np.float32).T, target_steps, axis=1)
        return repeated
    source_axis = np.linspace(0.0, 1.0, num=n_frames, dtype=np.float64)
    target_axis = np.linspace(0.0, 1.0, num=target_steps, dtype=np.float64)
    resampled = np.empty((n_channels, target_steps), dtype=np.float32)
    for channel_idx in range(n_channels):
        resampled[channel_idx] = np.interp(target_axis, source_axis, values[:, channel_idx]).astype(np.float32)
    return resampled


def build_dataset(cfg: dict[str, Any], args: argparse.Namespace) -> DatasetBundle:
    emg_df = load_emg_table(cfg["input"]["emg_parquet_path"])
    event_df = load_event_metadata(cfg["input"]["event_xlsm_path"], cfg)
    merged = merge_event_metadata(emg_df, event_df)
    trial_records = build_trial_records(merged, cfg)
    muscles = list(cfg["muscles"]["names"])

    tensors: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    for record in trial_records:
        label_step = bool(record.metadata.get("analysis_is_step"))
        label_nonstep = bool(record.metadata.get("analysis_is_nonstep"))
        if not (label_step or label_nonstep):
            continue
        frame = record.frame[muscles]
        tensors.append(resample_trial_matrix(frame.to_numpy(dtype=np.float32), args.time_steps))
        rows.append(
            {
                "subject": record.key[0],
                "velocity": float(record.key[1]),
                "trial_num": int(record.key[2]),
                "label_name": "step" if label_step else "nonstep",
                "label": int(label_step),
                "n_original_frames": int(len(record.frame)),
                "analysis_window_duration_device_frames": int(
                    record.metadata.get("analysis_window_duration_device_frames", len(record.frame))
                ),
            }
        )

    if not tensors:
        raise ValueError("No eligible trials remained after loading and filtering.")

    meta = pd.DataFrame(rows)
    meta["trial_id"] = (
        meta["subject"].astype(str)
        + "_v"
        + meta["velocity"].map(lambda value: f"{value:g}")
        + "_t"
        + meta["trial_num"].astype(str)
    )
    X = np.stack(tensors).astype(np.float32)
    y = meta["label"].to_numpy(dtype=np.int64)
    return DatasetBundle(
        X=X,
        y=y,
        meta=meta,
        muscles=muscles,
        input_path=str(cfg["input"]["emg_parquet_path"]),
        input_label=args.input_label,
    )


def sanity_check_message(n_trials: int, expected: int, tolerance: int) -> str:
    delta = abs(n_trials - expected)
    if delta <= tolerance:
        return f"PASS: selected trial count {n_trials} is within ±{tolerance} of {expected}."
    return f"FAIL: selected trial count {n_trials} is outside ±{tolerance} of {expected}."


def print_dataset_summary(bundle: DatasetBundle, args: argparse.Namespace) -> None:
    meta_pl = pl.from_pandas(bundle.meta)
    label_counts = (
        meta_pl.group_by("label_name")
        .len()
        .sort("label_name")
        .rename({"len": "count"})
    )
    n_trials = bundle.meta.shape[0]
    n_subjects = bundle.meta["subject"].nunique()
    n_step = int((bundle.meta["label_name"] == "step").sum())
    n_nonstep = int((bundle.meta["label_name"] == "nonstep").sum())
    window_min = int(bundle.meta["n_original_frames"].min())
    window_max = int(bundle.meta["n_original_frames"].max())
    window_mean = float(bundle.meta["n_original_frames"].mean())

    print("=" * 72)
    print("CNN Step vs Nonstep Prototype")
    print("=" * 72)
    print(f"Input label: {bundle.input_label}")
    print(f"Input path: {bundle.input_path}")
    print(f"Selected trials: {n_trials}")
    print(f"Subjects: {n_subjects}")
    print(f"Step trials: {n_step}")
    print(f"Nonstep trials: {n_nonstep}")
    print(f"Tensor shape: {tuple(bundle.X.shape)}  # (trials, channels, time_steps)")
    print(f"Original frame lengths: min={window_min}, max={window_max}, mean={window_mean:.2f}")
    print(sanity_check_message(n_trials, args.expected_trials, args.trial_tolerance))
    print("Label counts:")
    print(label_counts)


def build_subject_folds(bundle: DatasetBundle, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    subjects = bundle.meta["subject"].to_numpy()
    unique_subjects = np.unique(subjects)
    if unique_subjects.size < 2:
        raise ValueError("Need at least two subjects for subject-wise evaluation.")
    split_count = min(n_splits, unique_subjects.size)
    splitter = GroupKFold(n_splits=split_count)
    return list(splitter.split(bundle.X, bundle.y, groups=subjects))


def fold_metric_row(
    *,
    model_name: str,
    fold_idx: int,
    y_true: np.ndarray,
    probabilities: np.ndarray,
    test_subjects: np.ndarray,
) -> dict[str, Any]:
    preds = (probabilities >= 0.5).astype(np.int64)
    try:
        auc = float(roc_auc_score(y_true, probabilities))
    except ValueError:
        auc = math.nan
    return {
        "model": model_name,
        "fold": fold_idx,
        "n_test_trials": int(y_true.size),
        "n_test_subjects": int(np.unique(test_subjects).size),
        "accuracy": float(accuracy_score(y_true, preds)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, preds)),
        "f1": float(f1_score(y_true, preds, zero_division=0)),
        "roc_auc": auc,
    }


def evaluate_logistic(bundle: DatasetBundle, folds: list[tuple[np.ndarray, np.ndarray]], seed: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    flattened = bundle.X.reshape(bundle.X.shape[0], -1)
    for fold_idx, (train_idx, test_idx) in enumerate(folds, start=1):
        pipe = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=seed,
                    ),
                ),
            ]
        )
        pipe.fit(flattened[train_idx], bundle.y[train_idx])
        probabilities = pipe.predict_proba(flattened[test_idx])[:, 1]
        rows.append(
            fold_metric_row(
                model_name="logistic_regression",
                fold_idx=fold_idx,
                y_true=bundle.y[test_idx],
                probabilities=probabilities,
                test_subjects=bundle.meta.iloc[test_idx]["subject"].to_numpy(),
            )
        )
    return pd.DataFrame(rows)


def standardize_tensors(train_x: np.ndarray, test_x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = train_x.mean(axis=(0, 2), keepdims=True)
    std = train_x.std(axis=(0, 2), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (train_x - mean) / std, (test_x - mean) / std


def fit_cnn_fold(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    *,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
) -> np.ndarray:
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_x_std, test_x_std = standardize_tensors(train_x, test_x)
    train_dataset = TensorDataset(
        torch.from_numpy(train_x_std).float(),
        torch.from_numpy(train_y.astype(np.float32)),
    )
    loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    model = SmallEmgCnn(in_channels=train_x.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    positive = float(train_y.sum())
    negative = float(train_y.size - train_y.sum())
    pos_weight_value = negative / positive if positive > 0 else 1.0
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight_value, device=device))

    model.train()
    for _ in range(epochs):
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(features)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

    model.eval()
    with torch.no_grad():
        test_tensor = torch.from_numpy(test_x_std).float().to(device)
        logits = model(test_tensor)
        probabilities = torch.sigmoid(logits).cpu().numpy()
    return probabilities.astype(np.float64)


def evaluate_cnn(bundle: DatasetBundle, folds: list[tuple[np.ndarray, np.ndarray]], args: argparse.Namespace) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for fold_idx, (train_idx, test_idx) in enumerate(folds, start=1):
        probabilities = fit_cnn_fold(
            bundle.X[train_idx],
            bundle.y[train_idx],
            bundle.X[test_idx],
            epochs=args.cnn_epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            seed=args.seed + fold_idx,
        )
        rows.append(
            fold_metric_row(
                model_name="small_1d_cnn",
                fold_idx=fold_idx,
                y_true=bundle.y[test_idx],
                probabilities=probabilities,
                test_subjects=bundle.meta.iloc[test_idx]["subject"].to_numpy(),
            )
        )
    return pd.DataFrame(rows)


def summarize_metrics(metric_df: pd.DataFrame) -> pl.DataFrame:
    summary = (
        pl.from_pandas(metric_df)
        .group_by("model")
        .agg(
            pl.len().alias("folds"),
            pl.mean("accuracy").alias("accuracy_mean"),
            pl.std("accuracy").fill_null(0.0).alias("accuracy_std"),
            pl.mean("balanced_accuracy").alias("balanced_accuracy_mean"),
            pl.std("balanced_accuracy").fill_null(0.0).alias("balanced_accuracy_std"),
            pl.mean("f1").alias("f1_mean"),
            pl.std("f1").fill_null(0.0).alias("f1_std"),
            pl.mean("roc_auc").alias("roc_auc_mean"),
            pl.std("roc_auc").fill_null(0.0).alias("roc_auc_std"),
        )
        .sort("model")
    )
    return summary


def print_fold_details(metric_df: pd.DataFrame) -> None:
    detail = pl.from_pandas(metric_df).sort(["model", "fold"])
    print("\nPer-fold metrics:")
    print(detail)


def print_metric_summary(summary: pl.DataFrame) -> None:
    print("\nMean subject-wise metrics:")
    print(summary)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    cfg = resolve_config(args)
    dataset = build_dataset(cfg, args)
    print_dataset_summary(dataset, args)

    if args.dry_run:
        print("\nDry run complete. No model training was executed.")
        return

    folds = build_subject_folds(dataset, args.splits)
    print(f"\nSubject-wise evaluation folds: {len(folds)}")
    logistic_metrics = evaluate_logistic(dataset, folds, args.seed)
    cnn_metrics = evaluate_cnn(dataset, folds, args)
    metric_df = pd.concat([logistic_metrics, cnn_metrics], ignore_index=True)

    print_fold_details(metric_df)
    print_metric_summary(summarize_metrics(metric_df))


if __name__ == "__main__":
    main()
