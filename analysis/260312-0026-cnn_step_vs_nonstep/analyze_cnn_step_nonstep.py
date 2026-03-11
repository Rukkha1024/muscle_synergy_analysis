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
from dataclasses import dataclass, field
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
DEFAULT_EPOCHS = 50
DEFAULT_BATCH_SIZE = 16
DEFAULT_LR = 1e-3
DEFAULT_SEED = 42
DEFAULT_PATIENCE = 5
DEFAULT_VAL_FRACTION = 0.20
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
    histories: list["FoldHistory"] = field(default_factory=list)
    attribution_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FoldHistory:
    """Per-fold training traces and early-stopping metadata."""

    seed: int
    fold_idx: int
    epoch_train_loss: list[float]
    epoch_val_loss: list[float]
    best_epoch: int
    stopped_epoch: int
    used_early_stopping: bool
    val_subjects: list[str]


@dataclass
class AttributionSummary:
    """Class-wise attribution summary for time and channel views."""

    label_name: str
    gradcam_time_mean: np.ndarray
    channel_importance_mean: np.ndarray
    sample_count: int


@dataclass
class CnnFoldResult:
    """CNN fold outputs needed for scoring and interpretation."""

    probabilities: np.ndarray
    history: FoldHistory
    attribution_rows: list[dict[str, Any]]


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
        "--seeds",
        type=str,
        default=None,
        help="Optional comma-separated seed list. If omitted, the script uses --seed only.",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=DEFAULT_PATIENCE,
        help="Early-stopping patience for the CNN when inner validation is available.",
    )
    parser.add_argument(
        "--val-fraction",
        type=float,
        default=DEFAULT_VAL_FRACTION,
        help="Approximate fraction of outer-train subjects reserved for inner validation.",
    )
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


def parse_seed_list(args: argparse.Namespace) -> list[int]:
    if args.seeds is None or not args.seeds.strip():
        return [int(args.seed)]
    values = [chunk.strip() for chunk in args.seeds.split(",")]
    seeds = [int(chunk) for chunk in values if chunk]
    if not seeds:
        raise ValueError("Parsed an empty seed list from --seeds.")
    return seeds


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    cfg = copy.deepcopy(load_pipeline_config(str(args.config)))
    if args.emg_path is not None:
        cfg.setdefault("input", {})
        cfg["input"]["emg_parquet_path"] = str(args.emg_path)
    if args.event_xlsm is not None:
        cfg.setdefault("input", {})
        cfg["input"]["event_xlsm_path"] = str(args.event_xlsm)
    return cfg


def build_inner_subject_split(
    train_subjects: np.ndarray,
    train_y: np.ndarray,
    *,
    seed: int,
    val_fraction: float,
    max_attempts: int = 16,
) -> tuple[np.ndarray, np.ndarray] | None:
    unique_subjects = np.unique(train_subjects)
    if unique_subjects.size < 4:
        return None

    val_subject_count = int(math.ceil(unique_subjects.size * val_fraction))
    val_subject_count = min(max(2, val_subject_count), unique_subjects.size - 2)
    rng = np.random.default_rng(seed)

    for _ in range(max_attempts):
        shuffled = rng.permutation(unique_subjects)
        val_subjects = shuffled[:val_subject_count]
        val_mask = np.isin(train_subjects, val_subjects)
        train_mask = ~val_mask
        if not val_mask.any() or not train_mask.any():
            continue
        if np.unique(train_y[val_mask]).size < 2:
            continue
        if np.unique(train_y[train_mask]).size < 2:
            continue
        return np.flatnonzero(train_mask), np.flatnonzero(val_mask)
    return None


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


def compute_standardization_stats(reference_x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = reference_x.mean(axis=(0, 2), keepdims=True)
    std = reference_x.std(axis=(0, 2), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return mean.astype(np.float32), std.astype(np.float32)


def apply_standardization(values: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((values - mean) / std).astype(np.float32)


def upsample_curve(values: np.ndarray, target_steps: int) -> np.ndarray:
    if values.ndim != 1:
        raise ValueError(f"Expected a 1D curve to upsample, got shape={values.shape}")
    if values.shape[0] == target_steps:
        return values.astype(np.float32, copy=True)
    source_axis = np.linspace(0.0, 1.0, num=values.shape[0], dtype=np.float64)
    target_axis = np.linspace(0.0, 1.0, num=target_steps, dtype=np.float64)
    return np.interp(target_axis, source_axis, values.astype(np.float64)).astype(np.float32)


def compute_loss_on_tensor(
    model: SmallEmgCnn,
    criterion: nn.Module,
    x: np.ndarray,
    y: np.ndarray,
    device: torch.device,
) -> float:
    if x.shape[0] == 0:
        return math.nan
    tensor_x = torch.from_numpy(x).float().to(device)
    tensor_y = torch.from_numpy(y.astype(np.float32)).to(device)
    with torch.no_grad():
        logits = model(tensor_x)
        loss = criterion(logits, tensor_y)
    return float(loss.item())


def compute_gradcam_time(
    model: SmallEmgCnn,
    inputs: torch.Tensor,
    *,
    target_positive: bool,
) -> np.ndarray:
    device = next(model.parameters()).device
    activations: list[torch.Tensor] = []
    gradients: list[torch.Tensor] = []

    def forward_hook(_: nn.Module, __: tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
        activations.append(output.detach())

    def backward_hook(_: nn.Module, __: tuple[torch.Tensor, ...], grad_output: tuple[torch.Tensor, ...]) -> None:
        gradients.append(grad_output[0].detach())

    target_layer = model.features[5]
    forward_handle = target_layer.register_forward_hook(forward_hook)
    backward_handle = target_layer.register_full_backward_hook(backward_hook)
    try:
        model.zero_grad(set_to_none=True)
        eval_inputs = inputs.detach().clone().to(device)
        logits = model(eval_inputs)
        scores = logits if target_positive else -logits
        scores.sum().backward()
        if not activations or not gradients:
            raise RuntimeError("Grad-CAM hooks did not capture activations and gradients.")
        feature_map = activations[-1]
        grads = gradients[-1]
        weights = grads.mean(dim=2, keepdim=True)
        cam = torch.relu((weights * feature_map).sum(dim=1))
        cam = cam / cam.amax(dim=1, keepdim=True).clamp_min(1e-6)
        return cam.detach().cpu().numpy().astype(np.float32)
    finally:
        forward_handle.remove()
        backward_handle.remove()
        model.zero_grad(set_to_none=True)


def compute_input_x_gradient_channel_importance(
    model: SmallEmgCnn,
    inputs: torch.Tensor,
    *,
    target_positive: bool,
) -> np.ndarray:
    device = next(model.parameters()).device
    model.zero_grad(set_to_none=True)
    eval_inputs = inputs.detach().clone().to(device)
    eval_inputs.requires_grad_(True)
    logits = model(eval_inputs)
    scores = logits if target_positive else -logits
    scores.sum().backward()
    gradients = eval_inputs.grad
    if gradients is None:
        raise RuntimeError("Input gradients were not populated for channel attribution.")
    importance = torch.abs(eval_inputs * gradients).mean(dim=2)
    importance = importance / importance.amax(dim=1, keepdim=True).clamp_min(1e-6)
    model.zero_grad(set_to_none=True)
    return importance.detach().cpu().numpy().astype(np.float32)


def train_cnn_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    *,
    in_channels: int,
    device: torch.device,
    batch_size: int,
    lr: float,
    epochs: int,
    seed: int,
) -> SmallEmgCnn:
    train_dataset = TensorDataset(
        torch.from_numpy(train_x).float(),
        torch.from_numpy(train_y.astype(np.float32)),
    )
    loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    model = SmallEmgCnn(in_channels=in_channels).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    positive = float(train_y.sum())
    negative = float(train_y.size - train_y.sum())
    pos_weight_value = negative / positive if positive > 0 else 1.0
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight_value, device=device))
    for _ in range(max(epochs, 1)):
        model.train()
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(features)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
    model.eval()
    return model


def fit_cnn_fold(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    train_subjects: np.ndarray,
    *,
    epochs: int,
    batch_size: int,
    lr: float,
    patience: int,
    val_fraction: float,
    seed: int,
) -> CnnFoldResult:
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    split = build_inner_subject_split(train_subjects, train_y, seed=seed, val_fraction=val_fraction)
    used_early_stopping = split is not None
    if split is None:
        inner_train_idx = np.arange(train_x.shape[0], dtype=np.int64)
        val_idx = None
        val_subjects: list[str] = []
    else:
        inner_train_idx, inner_val_idx = split
        val_idx = inner_val_idx
        val_subjects = sorted(np.unique(train_subjects[val_idx]).astype(str).tolist())

    inner_train_x = train_x[inner_train_idx]
    inner_train_y = train_y[inner_train_idx]
    mean, std = compute_standardization_stats(inner_train_x)
    inner_train_x_std = apply_standardization(inner_train_x, mean, std)
    test_x_std = apply_standardization(test_x, mean, std)
    if val_idx is None:
        val_x_std = None
        val_y = None
    else:
        val_x_std = apply_standardization(train_x[val_idx], mean, std)
        val_y = train_y[val_idx]

    train_dataset = TensorDataset(
        torch.from_numpy(inner_train_x_std).float(),
        torch.from_numpy(inner_train_y.astype(np.float32)),
    )
    loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )

    model = SmallEmgCnn(in_channels=train_x.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    positive = float(inner_train_y.sum())
    negative = float(inner_train_y.size - inner_train_y.sum())
    pos_weight_value = negative / positive if positive > 0 else 1.0
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight_value, device=device))

    epoch_train_loss: list[float] = []
    epoch_val_loss: list[float] = []
    best_epoch = 0
    best_val_loss = math.inf
    patience_count = 0
    best_state = copy.deepcopy(model.state_dict())
    stopped_epoch = epochs

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        n_seen = 0
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(features)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            batch_size_now = int(labels.shape[0])
            running_loss += float(loss.item()) * batch_size_now
            n_seen += batch_size_now
        train_loss = running_loss / max(n_seen, 1)
        epoch_train_loss.append(train_loss)

        if used_early_stopping and val_x_std is not None and val_y is not None:
            model.eval()
            val_loss = compute_loss_on_tensor(model, criterion, val_x_std, val_y, device)
            epoch_val_loss.append(val_loss)
            if val_loss + 1e-8 < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                best_state = copy.deepcopy(model.state_dict())
                patience_count = 0
            else:
                patience_count += 1
                if patience_count >= patience:
                    stopped_epoch = epoch
                    break
        else:
            epoch_val_loss.append(math.nan)
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())

    if not used_early_stopping:
        stopped_epoch = len(epoch_train_loss)
    else:
        stopped_epoch = min(stopped_epoch, len(epoch_train_loss))

    final_mean, final_std = compute_standardization_stats(train_x)
    final_train_x_std = apply_standardization(train_x, final_mean, final_std)
    final_test_x_std = apply_standardization(test_x, final_mean, final_std)
    final_model = train_cnn_model(
        final_train_x_std,
        train_y,
        in_channels=train_x.shape[1],
        device=device,
        batch_size=batch_size,
        lr=lr,
        epochs=best_epoch,
        seed=seed + 1000,
    )

    final_model.eval()
    with torch.no_grad():
        test_tensor = torch.from_numpy(final_test_x_std).float().to(device)
        logits = final_model(test_tensor)
        probabilities = torch.sigmoid(logits).cpu().numpy()

    attribution_rows: list[dict[str, Any]] = []
    label_specs = [
        (1, "step", True),
        (0, "nonstep", False),
    ]
    for label_value, label_name, target_positive in label_specs:
        mask = test_y == label_value
        sample_count = int(mask.sum())
        if sample_count == 0:
            continue
        label_inputs = torch.from_numpy(final_test_x_std[mask]).float().to(device)
        gradcam_values = compute_gradcam_time(final_model, label_inputs, target_positive=target_positive)
        channel_values = compute_input_x_gradient_channel_importance(final_model, label_inputs, target_positive=target_positive)
        mean_time = upsample_curve(gradcam_values.mean(axis=0), test_x.shape[2])
        mean_channel = channel_values.mean(axis=0).astype(np.float32)
        for time_index, importance in enumerate(mean_time):
            attribution_rows.append(
                {
                    "label_name": label_name,
                    "kind": "time",
                    "index": int(time_index),
                    "importance": float(importance),
                    "sample_count": sample_count,
                }
            )
        for channel_index, importance in enumerate(mean_channel):
            attribution_rows.append(
                {
                    "label_name": label_name,
                    "kind": "channel",
                    "index": int(channel_index),
                    "importance": float(importance),
                    "sample_count": sample_count,
                }
            )

    history = FoldHistory(
        seed=seed,
        fold_idx=0,
        epoch_train_loss=epoch_train_loss,
        epoch_val_loss=epoch_val_loss,
        best_epoch=best_epoch,
        stopped_epoch=stopped_epoch,
        used_early_stopping=used_early_stopping,
        val_subjects=val_subjects,
    )
    return CnnFoldResult(
        probabilities=probabilities.astype(np.float64),
        history=history,
        attribution_rows=attribution_rows,
    )


def evaluate_cnn(
    bundle: DatasetBundle,
    folds: list[tuple[np.ndarray, np.ndarray]],
    args: argparse.Namespace,
    seed: int,
) -> EvaluationResult:
    metric_rows: list[dict[str, Any]] = []
    prediction_record_rows: list[dict[str, Any]] = []
    histories: list[FoldHistory] = []
    attribution_rows: list[dict[str, Any]] = []
    for fold_idx, (train_idx, test_idx) in enumerate(folds, start=1):
        fold_result = fit_cnn_fold(
            bundle.X[train_idx],
            bundle.y[train_idx],
            bundle.X[test_idx],
            bundle.y[test_idx],
            bundle.meta.iloc[train_idx]["subject"].to_numpy(),
            epochs=args.cnn_epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            patience=args.patience,
            val_fraction=args.val_fraction,
            seed=seed * 100 + fold_idx,
        )
        history = fold_result.history
        history.fold_idx = fold_idx
        history.seed = seed
        histories.append(history)
        probabilities = fold_result.probabilities
        metric_rows.append(
            {
                **fold_metric_row(
                    model_name="small_1d_cnn",
                    fold_idx=fold_idx,
                    y_true=bundle.y[test_idx],
                    probabilities=probabilities,
                    test_subjects=bundle.meta.iloc[test_idx]["subject"].to_numpy(),
                ),
                "used_early_stopping": history.used_early_stopping,
                "best_epoch": history.best_epoch,
                "stopped_epoch": history.stopped_epoch,
            }
        )
        prediction_record_rows.extend(
            prediction_rows(
                model_name="small_1d_cnn",
                fold_idx=fold_idx,
                bundle=bundle,
                test_idx=test_idx,
                probabilities=probabilities,
            )
        )
        for row in fold_result.attribution_rows:
            attribution_rows.append({"fold": fold_idx, "seed": seed, **row})
    return EvaluationResult(
        metrics=pd.DataFrame(metric_rows),
        predictions=pd.DataFrame(prediction_record_rows),
        histories=histories,
        attribution_rows=attribution_rows,
    )


def summarize_metrics(metric_df: pd.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    return (
        pl.from_pandas(metric_df)
        .group_by(group_cols)
        .agg(
            pl.len().alias("rows"),
            pl.mean("accuracy").alias("accuracy_mean"),
            pl.std("accuracy").fill_null(0.0).alias("accuracy_std"),
            pl.mean("balanced_accuracy").alias("balanced_accuracy_mean"),
            pl.std("balanced_accuracy").fill_null(0.0).alias("balanced_accuracy_std"),
            pl.mean("f1").alias("f1_mean"),
            pl.std("f1").fill_null(0.0).alias("f1_std"),
            pl.mean("roc_auc").alias("roc_auc_mean"),
            pl.std("roc_auc").fill_null(0.0).alias("roc_auc_std"),
        )
        .sort(group_cols)
    )


def compute_seed_level_metric_df(metric_df: pd.DataFrame) -> pd.DataFrame:
    if "seed" not in metric_df.columns:
        return metric_df.copy()
    return (
        metric_df.groupby(["seed", "model"], as_index=False)[["accuracy", "balanced_accuracy", "f1", "roc_auc"]]
        .mean()
        .sort_values(["seed", "model"])
        .reset_index(drop=True)
    )


def summarize_seed_metrics(metric_df: pd.DataFrame) -> pl.DataFrame:
    seed_means = compute_seed_level_metric_df(metric_df)
    return summarize_metrics(seed_means, ["model"])


def summarize_histories(histories: list[FoldHistory]) -> pl.DataFrame:
    if not histories:
        return pl.DataFrame()
    rows = [
        {
            "seed": history.seed,
            "fold": history.fold_idx,
            "used_early_stopping": history.used_early_stopping,
            "best_epoch": history.best_epoch,
            "stopped_epoch": history.stopped_epoch,
            "val_subject_count": len(history.val_subjects),
        }
        for history in histories
    ]
    return (
        pl.from_dicts(rows)
        .group_by("used_early_stopping")
        .agg(
            pl.len().alias("folds"),
            pl.mean("best_epoch").alias("best_epoch_mean"),
            pl.mean("stopped_epoch").alias("stopped_epoch_mean"),
        )
        .sort("used_early_stopping")
    )


def summarize_robustness_wins(metric_df: pd.DataFrame) -> pd.DataFrame:
    seed_df = compute_seed_level_metric_df(metric_df)
    if "seed" not in seed_df.columns or seed_df.empty:
        return pd.DataFrame()
    pivot = seed_df.pivot(index="seed", columns="model", values=["accuracy", "balanced_accuracy", "f1", "roc_auc"])
    rows: list[dict[str, Any]] = []
    for metric_name in ["accuracy", "balanced_accuracy", "f1", "roc_auc"]:
        logistic = pivot[(metric_name, "logistic_regression")]
        cnn = pivot[(metric_name, "small_1d_cnn")]
        rows.append(
            {
                "metric": metric_name,
                "cnn_better_seed_count": int((cnn > logistic).sum()),
                "logistic_better_seed_count": int((logistic > cnn).sum()),
                "tie_seed_count": int((cnn == logistic).sum()),
            }
        )
    return pd.DataFrame(rows)


def print_fold_details(metric_df: pd.DataFrame) -> None:
    sort_cols = ["model", "fold"]
    if "seed" in metric_df.columns:
        sort_cols = ["seed", "model", "fold"]
    detail = pl.from_pandas(metric_df).sort(sort_cols)
    print("\nPer-fold metrics:")
    print(detail)


def print_metric_summary(metric_df: pd.DataFrame) -> None:
    if metric_df["seed"].nunique() <= 1:
        print("\nMean subject-wise metrics:")
        print(summarize_metrics(metric_df, ["model"]))
        return

    seed_level = pl.from_pandas(compute_seed_level_metric_df(metric_df))
    print("\nSeed-level mean metrics:")
    print(seed_level.sort(["seed", "model"]))
    print("\nMean of seed-level metrics:")
    print(summarize_seed_metrics(metric_df))
    wins = summarize_robustness_wins(metric_df)
    print("\nRobustness summary (seed-level winners):")
    print(pl.from_pandas(wins))


def print_history_summary(histories: list[FoldHistory]) -> None:
    summary = summarize_histories(histories)
    if summary.height == 0:
        return
    print("\nCNN training-history summary:")
    print(summary)


def ensure_figure_dir() -> Path:
    figure_dir = SCRIPT_DIR / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    return figure_dir


def build_attribution_summaries(
    attribution_rows: list[dict[str, Any]],
    *,
    time_steps: int,
    channel_count: int,
) -> list[AttributionSummary]:
    if not attribution_rows:
        return []
    df = pd.DataFrame(attribution_rows)
    summaries: list[AttributionSummary] = []
    for label_name in ["step", "nonstep"]:
        label_df = df.loc[df["label_name"] == label_name].copy()
        if label_df.empty:
            continue
        time_df = label_df.loc[label_df["kind"] == "time"]
        channel_df = label_df.loc[label_df["kind"] == "channel"]
        if time_df.empty or channel_df.empty:
            continue
        sample_count = int(time_df[["seed", "fold", "sample_count"]].drop_duplicates()["sample_count"].sum())
        time_values = np.zeros(time_steps, dtype=np.float32)
        channel_values = np.zeros(channel_count, dtype=np.float32)
        for index in range(time_steps):
            rows = time_df.loc[time_df["index"] == index]
            if rows.empty:
                continue
            time_values[index] = np.average(rows["importance"], weights=rows["sample_count"]).astype(np.float32)
        for index in range(channel_count):
            rows = channel_df.loc[channel_df["index"] == index]
            if rows.empty:
                continue
            channel_values[index] = np.average(rows["importance"], weights=rows["sample_count"]).astype(np.float32)
        summaries.append(
            AttributionSummary(
                label_name=label_name,
                gradcam_time_mean=time_values,
                channel_importance_mean=channel_values,
                sample_count=sample_count,
            )
        )
    return summaries


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


def save_multi_seed_figure(metric_df: pd.DataFrame, output_path: Path, seed: int) -> None:
    plt = _pyplot()
    seed_metric_df = compute_seed_level_metric_df(metric_df)
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
        data = [
            seed_metric_df.loc[seed_metric_df["model"] == model_name, metric_key].to_numpy(dtype=np.float64)
            for model_name in model_order
        ]
        ax.boxplot(
            data,
            positions=np.arange(len(model_order)),
            widths=0.45,
            patch_artist=True,
            tick_labels=[MODEL_DISPLAY_NAMES[name] for name in model_order],
        )
        for patch, model_name in zip(ax.patches, model_order, strict=True):
            patch.set_facecolor(MODEL_COLORS[model_name])
            patch.set_alpha(0.22)
        for pos, values, model_name in zip(range(len(model_order)), data, model_order, strict=True):
            jitter = rng.uniform(-0.06, 0.06, size=values.shape[0])
            ax.scatter(
                np.full(values.shape[0], pos) + jitter,
                values,
                color=MODEL_COLORS[model_name],
                alpha=0.85,
                s=34,
            )
            if values.size:
                ax.hlines(values.mean(), pos - 0.22, pos + 0.22, color=MODEL_COLORS[model_name], linewidth=2.2)
        ax.set_title(metric_label)
        ax.set_ylim(0.0, 1.02)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Seed-level mean metric distributions", fontsize=13)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_gradcam_time_figure(
    summaries: list[AttributionSummary],
    output_path: Path,
) -> None:
    plt = _pyplot()
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)
    summary_map = {summary.label_name: summary for summary in summaries}
    time_axis = np.linspace(0.0, 100.0, num=DEFAULT_TIME_STEPS)
    for ax, label_name in zip(axes, ["step", "nonstep"], strict=True):
        summary = summary_map.get(label_name)
        if summary is None:
            ax.text(0.5, 0.5, f"No attribution available for {label_name}", ha="center", va="center")
            ax.set_axis_off()
            continue
        color = LABEL_COLORS[label_name]
        ax.plot(time_axis, summary.gradcam_time_mean, color=color, linewidth=2.2)
        ax.fill_between(time_axis, 0.0, summary.gradcam_time_mean, color=color, alpha=0.18)
        ax.set_ylabel("Relative importance")
        ax.set_ylim(0.0, max(1.0, float(summary.gradcam_time_mean.max()) * 1.1))
        ax.set_title(f"{label_name.title()} time attribution (n={summary.sample_count})")
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel("Normalized trial time (%)")
    fig.suptitle("Grad-CAM time attribution by class", fontsize=13)
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_channel_importance_figure(
    summaries: list[AttributionSummary],
    muscles: list[str],
    output_path: Path,
) -> None:
    plt = _pyplot()
    summary_map = {summary.label_name: summary for summary in summaries}
    fig, ax = plt.subplots(figsize=(14, 6))
    positions = np.arange(len(muscles))
    width = 0.38
    for offset, label_name in [(-width / 2.0, "step"), (width / 2.0, "nonstep")]:
        summary = summary_map.get(label_name)
        values = np.zeros(len(muscles), dtype=np.float32) if summary is None else summary.channel_importance_mean
        ax.bar(
            positions + offset,
            values,
            width=width,
            color=LABEL_COLORS[label_name],
            alpha=0.78,
            label=f"{label_name.title()} (n={0 if summary is None else summary.sample_count})",
        )
    ax.set_xticks(positions)
    ax.set_xticklabels(muscles, rotation=45, ha="right")
    ax.set_ylabel("Relative importance")
    ax.set_title("Input x gradient channel importance by class", fontsize=12)
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_training_curves_figure(histories: list[FoldHistory], output_path: Path) -> None:
    plt = _pyplot()
    if not histories:
        raise ValueError("No CNN histories were provided for the training-curve figure.")
    available_seeds = sorted({history.seed for history in histories})
    representative_seed = available_seeds[0]
    representative_histories = [history for history in histories if history.seed == representative_seed]
    representative_histories.sort(key=lambda history: history.fold_idx)
    n_plots = len(representative_histories)
    n_cols = 2
    n_rows = int(math.ceil(n_plots / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 3.8 * n_rows), squeeze=False)
    for ax in axes.flat[n_plots:]:
        ax.set_axis_off()
    for ax, history in zip(axes.flat, representative_histories):
        epochs = np.arange(1, len(history.epoch_train_loss) + 1)
        ax.plot(epochs, history.epoch_train_loss, color="#1C7ED6", linewidth=2.0, label="Train loss")
        val_loss = np.asarray(history.epoch_val_loss, dtype=np.float64)
        if np.isfinite(val_loss).any():
            ax.plot(epochs, val_loss, color="#E8590C", linewidth=2.0, label="Val loss")
            ax.scatter(history.best_epoch, val_loss[history.best_epoch - 1], color="#E03131", s=40, zorder=4, label="Best epoch")
        ax.axvline(history.stopped_epoch, color="#495057", linestyle="--", linewidth=1.2, label="Stop epoch")
        suffix = "inner val" if history.used_early_stopping else "full outer train"
        ax.set_title(f"Fold {history.fold_idx} ({suffix})")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Loss")
        ax.grid(alpha=0.25)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=min(4, len(labels)))
    title = "CNN training curves"
    if len(available_seeds) > 1:
        title += f" (representative seed {representative_seed})"
    fig.suptitle(title, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_figures(
    bundle: DatasetBundle,
    metric_df: pd.DataFrame,
    prediction_df: pd.DataFrame,
    histories: list[FoldHistory],
    attribution_rows: list[dict[str, Any]],
    seed: int,
) -> list[Path]:
    figure_dir = ensure_figure_dir()
    representative_metric_df = metric_df.loc[metric_df["seed"] == seed].copy() if "seed" in metric_df.columns else metric_df
    representative_prediction_df = prediction_df.loc[prediction_df["seed"] == seed].copy() if "seed" in prediction_df.columns else prediction_df
    attribution_summaries = build_attribution_summaries(
        attribution_rows,
        time_steps=bundle.X.shape[2],
        channel_count=bundle.X.shape[1],
    )
    output_paths = [
        figure_dir / "01_dataset_label_counts.png",
        figure_dir / "02_emg_class_average_heatmaps.png",
        figure_dir / "03_trial_length_by_class.png",
        figure_dir / "04_fold_metric_comparison.png",
        figure_dir / "05_confusion_matrices.png",
        figure_dir / "06_pooled_roc_curves.png",
        figure_dir / "07_multi_seed_metric_distribution.png",
        figure_dir / "08_gradcam_time_saliency.png",
        figure_dir / "09_channel_importance.png",
        figure_dir / "10_training_curves.png",
    ]
    save_dataset_label_counts_figure(bundle, output_paths[0])
    save_emg_class_average_heatmaps(bundle, output_paths[1])
    save_trial_length_figure(bundle, output_paths[2], seed)
    save_fold_metric_figure(representative_metric_df, output_paths[3], seed)
    save_confusion_matrix_figure(representative_prediction_df, output_paths[4])
    save_pooled_roc_figure(representative_prediction_df, output_paths[5])
    save_multi_seed_figure(metric_df, output_paths[6], seed)
    save_gradcam_time_figure(attribution_summaries, output_paths[7])
    save_channel_importance_figure(attribution_summaries, bundle.muscles, output_paths[8])
    save_training_curves_figure(histories, output_paths[9])
    return output_paths


def main() -> None:
    args = parse_args()
    seeds = parse_seed_list(args)
    set_seed(seeds[0])
    cfg = resolve_config(args)
    dataset = build_dataset(cfg, args)
    print_dataset_summary(dataset, args)

    if args.dry_run:
        print("\nDry run complete. No model training was executed.")
        return

    folds = build_subject_folds(dataset, args.splits)
    print(f"\nSubject-wise evaluation folds: {len(folds)}")
    all_metrics: list[pd.DataFrame] = []
    all_predictions: list[pd.DataFrame] = []
    all_histories: list[FoldHistory] = []
    all_attribution_rows: list[dict[str, Any]] = []
    for current_seed in seeds:
        print(f"\n=== Running seed {current_seed} ===")
        logistic_result = evaluate_logistic(dataset, folds, current_seed)
        cnn_result = evaluate_cnn(dataset, folds, args, current_seed)

        logistic_metrics = logistic_result.metrics.copy()
        logistic_metrics["seed"] = current_seed
        cnn_metrics = cnn_result.metrics.copy()
        cnn_metrics["seed"] = current_seed
        all_metrics.extend([logistic_metrics, cnn_metrics])

        logistic_predictions = logistic_result.predictions.copy()
        logistic_predictions["seed"] = current_seed
        cnn_predictions = cnn_result.predictions.copy()
        cnn_predictions["seed"] = current_seed
        all_predictions.extend([logistic_predictions, cnn_predictions])

        all_histories.extend(cnn_result.histories)
        all_attribution_rows.extend(cnn_result.attribution_rows)

    metric_df = pd.concat(all_metrics, ignore_index=True)
    prediction_df = pd.concat(all_predictions, ignore_index=True)

    print_fold_details(metric_df)
    print_metric_summary(metric_df)
    print_history_summary(all_histories)
    figure_paths = save_figures(dataset, metric_df, prediction_df, all_histories, all_attribution_rows, seeds[0])
    print("\nSaved figures:")
    for figure_path in figure_paths:
        print(f"- {figure_path}")


if __name__ == "__main__":
    main()
