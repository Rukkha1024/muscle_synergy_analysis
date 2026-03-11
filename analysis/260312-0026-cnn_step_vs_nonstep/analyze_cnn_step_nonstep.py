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
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, roc_auc_score, roc_curve
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
MODEL_DISPLAY_NAMES = {
    "logistic_regression": "Logistic regression",
    "small_1d_cnn": "Small 1D CNN",
}
MODEL_COLORS = {
    "logistic_regression": "#4C6EF5",
    "small_1d_cnn": "#2F9E44",
}
LABEL_COLORS = {
    "step": "#D9480F",
    "nonstep": "#1971C2",
}
FIGURE_DPI = 300
_PYPLOT = None


@dataclass
class DatasetBundle:
    """Fixed-length tensors and trial metadata for subject-wise evaluation."""

    X: np.ndarray
    y: np.ndarray
    meta: pd.DataFrame
    muscles: list[str]
    input_path: str
    input_label: str


@dataclass
class EvaluationResult:
    """Metric summaries and held-out predictions from one evaluation path."""

    metrics: pd.DataFrame
    predictions: pd.DataFrame


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


def _pyplot():
    global _PYPLOT
    if _PYPLOT is not None:
        return _PYPLOT
    import matplotlib

    try:
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
    import matplotlib.pyplot as plt

    _PYPLOT = plt
    return plt


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


def prediction_rows(
    *,
    bundle: DatasetBundle,
    model_name: str,
    fold_idx: int,
    test_idx: np.ndarray,
    probabilities: np.ndarray,
) -> list[dict[str, Any]]:
    preds = (probabilities >= 0.5).astype(np.int64)
    fold_meta = bundle.meta.iloc[test_idx].reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for row_idx, meta_row in fold_meta.iterrows():
        rows.append(
            {
                "model": model_name,
                "fold": fold_idx,
                "trial_id": str(meta_row["trial_id"]),
                "subject": str(meta_row["subject"]),
                "label_name": str(meta_row["label_name"]),
                "y_true": int(meta_row["label"]),
                "probability": float(probabilities[row_idx]),
                "y_pred": int(preds[row_idx]),
            }
        )
    return rows


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


def evaluate_logistic(bundle: DatasetBundle, folds: list[tuple[np.ndarray, np.ndarray]], seed: int) -> EvaluationResult:
    metric_rows: list[dict[str, Any]] = []
    prediction_record_rows: list[dict[str, Any]] = []
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
        metric_rows.append(
            fold_metric_row(
                model_name="logistic_regression",
                fold_idx=fold_idx,
                y_true=bundle.y[test_idx],
                probabilities=probabilities,
                test_subjects=bundle.meta.iloc[test_idx]["subject"].to_numpy(),
            )
        )
        prediction_record_rows.extend(
            prediction_rows(
                bundle=bundle,
                model_name="logistic_regression",
                fold_idx=fold_idx,
                test_idx=test_idx,
                probabilities=probabilities,
            )
        )
    return EvaluationResult(
        metrics=pd.DataFrame(metric_rows),
        predictions=pd.DataFrame(prediction_record_rows),
    )


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


def evaluate_cnn(bundle: DatasetBundle, folds: list[tuple[np.ndarray, np.ndarray]], args: argparse.Namespace) -> EvaluationResult:
    metric_rows: list[dict[str, Any]] = []
    prediction_record_rows: list[dict[str, Any]] = []
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
        metric_rows.append(
            fold_metric_row(
                model_name="small_1d_cnn",
                fold_idx=fold_idx,
                y_true=bundle.y[test_idx],
                probabilities=probabilities,
                test_subjects=bundle.meta.iloc[test_idx]["subject"].to_numpy(),
            )
        )
        prediction_record_rows.extend(
            prediction_rows(
                bundle=bundle,
                model_name="small_1d_cnn",
                fold_idx=fold_idx,
                test_idx=test_idx,
                probabilities=probabilities,
            )
        )
    return EvaluationResult(
        metrics=pd.DataFrame(metric_rows),
        predictions=pd.DataFrame(prediction_record_rows),
    )


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


def ensure_figure_dir() -> Path:
    figure_dir = SCRIPT_DIR / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    return figure_dir


def save_dataset_label_counts_figure(bundle: DatasetBundle, output_path: Path) -> None:
    plt = _pyplot()
    counts = (
        pl.from_pandas(bundle.meta)
        .group_by("label_name")
        .len()
        .rename({"len": "count"})
        .to_pandas()
        .set_index("label_name")
    )
    order = ["step", "nonstep"]
    values = [int(counts.loc[label, "count"]) for label in order]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(order, values, color=[LABEL_COLORS[label] for label in order], width=0.55)
    for bar, value in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2.0, value + 1.0, str(value), ha="center", va="bottom", fontsize=11)
    ax.set_ylabel("Trial count")
    ax.set_title(
        "Selected trial counts by class\n"
        f"{bundle.meta.shape[0]} trials across {bundle.meta['subject'].nunique()} subjects",
        fontsize=12,
    )
    ax.set_ylim(0, max(values) + 12)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, facecolor="white")
    plt.close(fig)


def save_emg_class_average_heatmaps(bundle: DatasetBundle, output_path: Path) -> None:
    plt = _pyplot()
    masks = {
        "step": bundle.meta["label_name"].to_numpy() == "step",
        "nonstep": bundle.meta["label_name"].to_numpy() == "nonstep",
    }
    averaged = {label: bundle.X[mask].mean(axis=0) for label, mask in masks.items()}

    fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharey=True, constrained_layout=True)
    image = None
    for ax, label in zip(axes, ["step", "nonstep"], strict=True):
        image = ax.imshow(
            averaged[label],
            aspect="auto",
            cmap="viridis",
            vmin=0.0,
            vmax=1.0,
            interpolation="nearest",
        )
        ax.set_title(f"{label.title()} class average")
        ax.set_xlabel("Normalized trial time (%)")
        ax.set_xticks(np.linspace(0, bundle.X.shape[2] - 1, num=6))
        ax.set_xticklabels(["0", "20", "40", "60", "80", "100"])
    axes[0].set_ylabel("EMG channel")
    axes[0].set_yticks(np.arange(len(bundle.muscles)))
    axes[0].set_yticklabels(bundle.muscles)
    axes[1].set_yticks(np.arange(len(bundle.muscles)))
    axes[1].set_yticklabels(bundle.muscles)
    colorbar = fig.colorbar(image, ax=axes, shrink=0.92, pad=0.02)
    colorbar.set_label("Mean normalized activation")
    fig.suptitle("What the CNN sees after trial resampling", fontsize=13)
    fig.savefig(output_path, dpi=FIGURE_DPI, facecolor="white")
    plt.close(fig)


def save_trial_length_figure(bundle: DatasetBundle, output_path: Path, seed: int) -> None:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(8, 5))
    label_order = ["step", "nonstep"]
    data = [
        bundle.meta.loc[bundle.meta["label_name"] == label, "n_original_frames"].to_numpy(dtype=np.float64)
        for label in label_order
    ]
    positions = np.arange(1, len(label_order) + 1)
    boxplot = ax.boxplot(
        data,
        positions=positions,
        widths=0.5,
        patch_artist=True,
        tick_labels=[label.title() for label in label_order],
    )
    for patch, label in zip(boxplot["boxes"], label_order, strict=True):
        patch.set_facecolor(LABEL_COLORS[label])
        patch.set_alpha(0.35)
    rng = np.random.default_rng(seed)
    for pos, values, label in zip(positions, data, label_order, strict=True):
        jitter = rng.uniform(-0.08, 0.08, size=values.shape[0])
        ax.scatter(
            np.full(values.shape[0], pos) + jitter,
            values,
            s=22,
            alpha=0.75,
            color=LABEL_COLORS[label],
            edgecolors="none",
        )
    ax.set_ylabel("Original window length (frames)")
    ax.set_title("Trial length varies before fixed-length resampling", fontsize=12)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_fold_metric_figure(metric_df: pd.DataFrame, output_path: Path, seed: int) -> None:
    plt = _pyplot()
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    metric_specs = [
        ("accuracy", "Accuracy"),
        ("balanced_accuracy", "Balanced Accuracy"),
        ("f1", "F1"),
        ("roc_auc", "ROC AUC"),
    ]
    model_order = ["logistic_regression", "small_1d_cnn"]
    rng = np.random.default_rng(seed)
    for ax, (metric_key, metric_label) in zip(axes.flat, metric_specs, strict=True):
        for pos, model_name in enumerate(model_order):
            model_rows = metric_df.loc[metric_df["model"] == model_name, metric_key].to_numpy(dtype=np.float64)
            jitter = rng.uniform(-0.07, 0.07, size=model_rows.shape[0])
            ax.scatter(
                np.full(model_rows.shape[0], pos) + jitter,
                model_rows,
                color=MODEL_COLORS[model_name],
                alpha=0.85,
                s=34,
                label=MODEL_DISPLAY_NAMES[model_name] if metric_key == "accuracy" else None,
            )
            ax.hlines(
                y=float(model_rows.mean()),
                xmin=pos - 0.23,
                xmax=pos + 0.23,
                color=MODEL_COLORS[model_name],
                linewidth=2.5,
            )
        ax.set_title(metric_label)
        ax.set_ylim(0.0, 1.02)
        ax.set_xticks(range(len(model_order)))
        ax.set_xticklabels([MODEL_DISPLAY_NAMES[name] for name in model_order], rotation=8)
        ax.grid(axis="y", alpha=0.25)
    axes[0, 0].legend(loc="lower left")
    fig.suptitle("Fold-by-fold metric comparison", fontsize=13)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def confusion_matrix_annotations(matrix_counts: np.ndarray) -> list[list[str]]:
    row_totals = matrix_counts.sum(axis=1, keepdims=True)
    row_norm = np.divide(matrix_counts, row_totals, out=np.zeros_like(matrix_counts, dtype=np.float64), where=row_totals > 0)
    annotations: list[list[str]] = []
    for row_idx in range(matrix_counts.shape[0]):
        row_annotations: list[str] = []
        for col_idx in range(matrix_counts.shape[1]):
            count = int(matrix_counts[row_idx, col_idx])
            pct = 100.0 * row_norm[row_idx, col_idx]
            row_annotations.append(f"{count}\n{pct:.1f}%")
        annotations.append(row_annotations)
    return annotations


def save_confusion_matrix_figure(prediction_df: pd.DataFrame, output_path: Path) -> None:
    plt = _pyplot()
    labels = [0, 1]
    tick_labels = ["Nonstep", "Step"]
    model_order = ["logistic_regression", "small_1d_cnn"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True, constrained_layout=True)
    image = None
    for ax, model_name in zip(axes, model_order, strict=True):
        model_rows = prediction_df.loc[prediction_df["model"] == model_name]
        counts = confusion_matrix(model_rows["y_true"], model_rows["y_pred"], labels=labels)
        row_totals = counts.sum(axis=1, keepdims=True)
        normalized = np.divide(counts, row_totals, out=np.zeros_like(counts, dtype=np.float64), where=row_totals > 0)
        image = ax.imshow(normalized, cmap="Blues", vmin=0.0, vmax=1.0)
        for row_idx, row in enumerate(confusion_matrix_annotations(counts)):
            for col_idx, text in enumerate(row):
                ax.text(col_idx, row_idx, text, ha="center", va="center", color="#0B1F33", fontsize=10)
        ax.set_title(MODEL_DISPLAY_NAMES[model_name])
        ax.set_xticks([0, 1])
        ax.set_xticklabels(tick_labels)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(tick_labels)
        ax.set_xlabel("Predicted class")
    axes[0].set_ylabel("True class")
    colorbar = fig.colorbar(image, ax=axes, shrink=0.9, pad=0.02)
    colorbar.set_label("Row-normalized proportion")
    fig.suptitle("Pooled confusion matrices across held-out folds", fontsize=13)
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_pooled_roc_figure(prediction_df: pd.DataFrame, output_path: Path) -> None:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(7, 6))
    model_order = ["logistic_regression", "small_1d_cnn"]
    for model_name in model_order:
        model_rows = prediction_df.loc[prediction_df["model"] == model_name]
        fpr, tpr, _ = roc_curve(model_rows["y_true"], model_rows["probability"])
        auc = roc_auc_score(model_rows["y_true"], model_rows["probability"])
        ax.plot(
            fpr,
            tpr,
            color=MODEL_COLORS[model_name],
            linewidth=2.0,
            label=f"{MODEL_DISPLAY_NAMES[model_name]} (AUC={auc:.3f})",
        )
    ax.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", color="#868E96", linewidth=1.2, label="Chance")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Pooled ROC curves from held-out trials", fontsize=12)
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_figures(bundle: DatasetBundle, metric_df: pd.DataFrame, prediction_df: pd.DataFrame, seed: int) -> list[Path]:
    figure_dir = ensure_figure_dir()
    output_paths = [
        figure_dir / "01_dataset_label_counts.png",
        figure_dir / "02_emg_class_average_heatmaps.png",
        figure_dir / "03_trial_length_by_class.png",
        figure_dir / "04_fold_metric_comparison.png",
        figure_dir / "05_confusion_matrices.png",
        figure_dir / "06_pooled_roc_curves.png",
    ]
    save_dataset_label_counts_figure(bundle, output_paths[0])
    save_emg_class_average_heatmaps(bundle, output_paths[1])
    save_trial_length_figure(bundle, output_paths[2], seed)
    save_fold_metric_figure(metric_df, output_paths[3], seed)
    save_confusion_matrix_figure(prediction_df, output_paths[4])
    save_pooled_roc_figure(prediction_df, output_paths[5])
    return output_paths


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
    logistic_result = evaluate_logistic(dataset, folds, args.seed)
    cnn_result = evaluate_cnn(dataset, folds, args)
    metric_df = pd.concat([logistic_result.metrics, cnn_result.metrics], ignore_index=True)
    prediction_df = pd.concat([logistic_result.predictions, cnn_result.predictions], ignore_index=True)

    print_fold_details(metric_df)
    print_metric_summary(summarize_metrics(metric_df))
    figure_paths = save_figures(dataset, metric_df, prediction_df, args.seed)
    print("\nSaved figures:")
    for figure_path in figure_paths:
        print(f"- {figure_path}")


if __name__ == "__main__":
    main()
