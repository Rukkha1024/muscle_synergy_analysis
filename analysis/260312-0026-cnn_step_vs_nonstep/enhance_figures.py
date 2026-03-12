"""기존 CNN figure에 한국어 개념 주석을 오버레이하고 아키텍처 다이어그램을 생성한다.

Usage:
    conda run -n module python analysis/260312-0026-cnn_step_vs_nonstep/enhance_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import numpy as np

# ---------------------------------------------------------------------------
# Font setup
# ---------------------------------------------------------------------------
_FONT_PATH = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
_FONT_BOLD_PATH = Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")
_FONT_PROP = fm.FontProperties(fname=str(_FONT_PATH), size=11)
_FONT_BOLD = fm.FontProperties(fname=str(_FONT_BOLD_PATH), size=12)
_FONT_SMALL = fm.FontProperties(fname=str(_FONT_PATH), size=9)
_FONT_TITLE = fm.FontProperties(fname=str(_FONT_BOLD_PATH), size=14)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DIR = Path(__file__).resolve().parent
_FIG_DIR = _DIR / "figures"

# ---------------------------------------------------------------------------
# Annotation style
# ---------------------------------------------------------------------------
_BOX_STYLE = dict(
    boxstyle="round,pad=0.5",
    facecolor="#FFFDE7",
    edgecolor="#F57F17",
    alpha=0.92,
    linewidth=1.5,
)

_DPI = 300


def _annotate_figure(src_name: str, annotation: str, position: str = "bottom") -> None:
    """Load an existing PNG, add a Korean annotation box, and overwrite it."""
    src = _FIG_DIR / src_name
    if not src.exists():
        print(f"  [SKIP] {src_name} not found")
        return

    img = mpimg.imread(str(src))
    h, w = img.shape[:2]

    # figure size to match original resolution at target DPI
    fig_w = w / _DPI
    fig_h = h / _DPI
    # add extra space for annotation
    extra_h = 0.7  # inches for annotation area
    fig, ax = plt.subplots(figsize=(fig_w, fig_h + extra_h))

    if position == "bottom":
        ax.set_position([0, extra_h / (fig_h + extra_h), 1, fig_h / (fig_h + extra_h)])
    else:  # top
        ax.set_position([0, 0, 1, fig_h / (fig_h + extra_h)])

    ax.imshow(img)
    ax.set_axis_off()

    # annotation text at bottom/top of figure
    if position == "bottom":
        fig.text(
            0.5, 0.02,
            annotation,
            fontproperties=_FONT_PROP,
            ha="center", va="bottom",
            bbox=_BOX_STYLE,
            wrap=True,
        )
    else:
        fig.text(
            0.5, 0.98,
            annotation,
            fontproperties=_FONT_PROP,
            ha="center", va="top",
            bbox=_BOX_STYLE,
            wrap=True,
        )

    fig.savefig(str(src), dpi=_DPI, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print(f"  [OK] {src_name}")


def _create_architecture_diagram() -> None:
    """Generate 00_model_architecture.png — full model architecture + concept mapping."""
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.set_axis_off()

    # Title
    fig.text(
        0.5, 0.97,
        "CNN 모델 아키텍처 — CNN_정리.md 개념 매핑",
        fontproperties=_FONT_TITLE,
        ha="center", va="top",
        fontsize=16,
    )

    # Layer definitions: (x, y, width, height, label, color, concept_note)
    layers = [
        (0.5, 5.0, 2.0, 1.2, "입력 텐서\n16ch × 100t", "#E3F2FD",
         "Channel 개념:\nEMG 16채널 = 입력 채널"),
        (3.0, 5.0, 2.0, 1.2, "Conv1d\n16→32, k=5\npad=2", "#E8F5E9",
         "Convolution:\n커널이 시간축 스캔\nPadding: same"),
        (3.0, 3.3, 0.8, 0.6, "ReLU", "#FFF3E0", ""),
        (5.5, 5.0, 2.0, 1.2, "Conv1d\n32→32, k=5\npad=2", "#E8F5E9",
         "같은 구조 반복\n→ 더 깊은 특징 추출"),
        (5.5, 3.3, 0.8, 0.6, "ReLU", "#FFF3E0", ""),
        (5.5, 2.2, 1.5, 0.6, "MaxPool1d(2)", "#FCE4EC",
         "Pooling:\n시간 해상도 ½로 압축"),
        (8.0, 5.0, 2.0, 1.2, "Conv1d\n32→64, k=3\npad=1", "#E8F5E9",
         "채널 수 증가\n= feature map 확장"),
        (8.0, 3.3, 0.8, 0.6, "ReLU", "#FFF3E0", ""),
        (8.0, 2.2, 1.8, 0.6, "AdaptiveAvgPool1d(1)", "#F3E5F5",
         "GAP:\n각 채널의 평균값만 남김\n→ Flatten 대체"),
        (10.5, 5.0, 1.5, 1.0, "FC\n64→32", "#FFF9C4",
         "FC Layer:\n최종 분류기"),
        (10.5, 3.5, 0.8, 0.6, "ReLU", "#FFF3E0", ""),
        (10.5, 2.5, 1.2, 0.6, "Dropout\n(0.20)", "#FFEBEE",
         "Dropout:\n과적합 방지"),
        (12.5, 5.0, 1.2, 1.0, "FC\n32→1", "#FFF9C4", ""),
        (12.5, 3.5, 1.2, 0.6, "Sigmoid", "#E0F7FA",
         "※ Softmax 아님!\n이진 분류 → Sigmoid"),
    ]

    for x, y, w, h, label, color, note in layers:
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.15",
            facecolor=color,
            edgecolor="#424242",
            linewidth=1.2,
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2, y + h / 2,
            label,
            fontproperties=_FONT_SMALL,
            ha="center", va="center",
            fontsize=8,
        )

        # Concept annotation below (if present)
        if note:
            ax.text(
                x + w / 2, y - 0.15,
                note,
                fontproperties=_FONT_SMALL,
                ha="center", va="top",
                fontsize=7,
                color="#E65100",
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="#FFFDE7",
                    edgecolor="#F57F17",
                    alpha=0.85,
                    linewidth=0.8,
                ),
            )

    # Arrows between major blocks (simplified horizontal flow)
    arrow_style = "Simple,tail_width=1.5,head_width=6,head_length=4"
    arrow_pairs = [
        (2.5, 5.6, 3.0, 5.6),    # input → conv1
        (5.0, 5.6, 5.5, 5.6),    # conv1 → conv2
        (7.5, 5.6, 8.0, 5.6),    # conv2 → conv3
        (10.0, 5.6, 10.5, 5.6),  # conv3 → fc1
        (12.0, 5.5, 12.5, 5.5),  # fc1 → fc2
        # vertical arrows for activation/pooling
        (3.4, 5.0, 3.4, 3.9),    # conv1 → relu
        (5.9, 5.0, 5.9, 3.9),    # conv2 → relu
        (5.9, 3.3, 5.9, 2.8),    # relu → maxpool
        (8.4, 5.0, 8.4, 3.9),    # conv3 → relu
        (8.4, 3.3, 8.4, 2.8),    # relu → gap
        (10.9, 5.0, 10.9, 4.1),  # fc1 → relu
        (10.9, 3.5, 10.9, 3.1),  # relu → dropout
        (13.1, 5.0, 13.1, 4.1),  # fc2 → sigmoid
    ]

    for x1, y1, x2, y2 in arrow_pairs:
        ax.annotate(
            "",
            xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="->",
                color="#616161",
                lw=1.2,
                connectionstyle="arc3,rad=0",
            ),
        )

    # Bottom legend box
    legend_text = (
        "【CNN_정리.md 보완 포인트】\n"
        "• 이 모델은 1D Convolution (이미지 CNN은 2D) — EMG 시간축만 스캔\n"
        "• Softmax가 아닌 Sigmoid 사용 — 이진 분류(step vs nonstep)이므로 출력 1개\n"
        "• Normalization: 입력 데이터 min-max만 사용, BatchNorm은 미적용\n"
        "• ReLU는 Conv 뒤 3번 + FC 뒤 1번 = 총 4번 적용"
    )
    fig.text(
        0.5, 0.03,
        legend_text,
        fontproperties=_FONT_PROP,
        ha="center", va="bottom",
        fontsize=10,
        bbox=dict(
            boxstyle="round,pad=0.6",
            facecolor="#FFF8E1",
            edgecolor="#FF6F00",
            alpha=0.95,
            linewidth=2,
        ),
    )

    out = _FIG_DIR / "00_model_architecture.png"
    fig.savefig(str(out), dpi=_DPI, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"  [OK] 00_model_architecture.png (new)")


# ---------------------------------------------------------------------------
# Annotation map: filename → annotation text
# ---------------------------------------------------------------------------
_ANNOTATIONS: dict[str, tuple[str, str]] = {
    "01_dataset_label_counts.png": (
        "[데이터] CNN 학습 전: 데이터 확인  |  "
        "불균형(step=53 vs nonstep=72) → BCEWithLogitsLoss의 pos_weight로 보정",
        "bottom",
    ),
    "02_emg_class_average_heatmaps.png": (
        "[입력] CNN 입력 텐서: 16채널(행) x 100시간(열)  |  "
        "1D Convolution이 시간축(열 방향)을 커널로 스캔한다",
        "bottom",
    ),
    "03_trial_length_by_class.png": (
        "[전처리] 가변 길이 → 100 timestep 고정 리샘플링  |  "
        "CNN은 고정 크기 입력이 필요하다",
        "bottom",
    ),
    "04_fold_metric_comparison.png": (
        "[검증] Subject-wise 교차검증: 과적합 방지  |  "
        "같은 피험자가 train과 test에 동시 등장하지 않음 (GroupKFold)",
        "bottom",
    ),
    "05_confusion_matrices.png": (
        "[출력] 최종 출력 해석: sigmoid → step/nonstep 판정  |  "
        "이진 분류에서는 softmax 대신 sigmoid를 사용한다 (출력=1개)",
        "bottom",
    ),
    "06_pooled_roc_curves.png": (
        "[평가] ROC 곡선: threshold 변화에 따른 성능  |  "
        "대각선(Chance) 위 = 학습 효과 있음, 위쪽일수록 좋은 모델",
        "bottom",
    ),
    "07_multi_seed_metric_distribution.png": (
        "[초기화] Weight 초기화의 영향  |  "
        "'weight는 랜덤' → seed마다 성능이 변동한다 (CNN_정리.md §1.2)",
        "bottom",
    ),
    "08_gradcam_time_saliency.png": (
        "[해석] Grad-CAM: Conv 층이 시간축에서 집중한 구간  |  "
        "Convolution이 학습한 특징을 시각화 — 어느 시간대가 중요했는가?",
        "bottom",
    ),
    "09_channel_importance.png": (
        "[해석] Input x Gradient: 채널별 기여도  |  "
        "어떤 EMG 채널(=입력 채널)이 step/nonstep 분류에 중요했는지",
        "bottom",
    ),
    "10_training_curves.png": (
        "[학습] 학습 곡선: Loss 감소 = Weight 최적화 과정  |  "
        "Train↓ Val↑ 이면 과적합 → Early Stopping으로 방지",
        "bottom",
    ),
}


def main() -> None:
    print("=== CNN Figure Enhancement ===")
    _FIG_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Architecture diagram (new figure)
    print("\n[1/2] Generating architecture diagram ...")
    _create_architecture_diagram()

    # Step 2: Annotate existing figures
    print("\n[2/2] Adding concept annotations to existing figures ...")
    for fname, (annotation, position) in _ANNOTATIONS.items():
        _annotate_figure(fname, annotation, position)

    # Verify
    expected = [f"{i:02d}_" for i in range(11)]
    found = sorted(p.name for p in _FIG_DIR.glob("*.png"))
    count = sum(1 for f in found if any(f.startswith(e) for e in expected))
    print(f"\n✓ {count}/11 figures present in {_FIG_DIR}")

    if count < 11:
        missing = [e for e in expected if not any(f.startswith(e) for f in found)]
        print(f"  Missing prefixes: {missing}")


if __name__ == "__main__":
    main()
