# CNN Step vs Nonstep Prototype Report

## Research Question

**"Can a simple subject-wise classifier distinguish `step` and `nonstep` trials from normalized EMG time series while preserving the same trial meaning used by the current synergy workflow?"**

This prototype stays inside `analysis/260312-0026-cnn_step_vs_nonstep/` so the official synergy pipeline remains untouched. The goal is not to prove that CNN is universally better than synergy, but to establish a clean first benchmark under the same step-vs-nonstep trial definition.

## Data Summary

- **125 trials** after the current filtering logic (`step` = 53, `nonstep` = 72)
- **24 subjects** in the filtered comparison set
- Data source:
  - normalized EMG parquet from `configs/global_config.yaml`
  - event workbook from `configs/global_config.yaml`
- EMG channels: `TA`, `EHL`, `MG`, `SOL`, `PL`, `RF`, `VL`, `ST`, `RA`, `EO`, `IO`, `SCM`, `GM`, `ESC`, `EST`, `ESL`

## Analysis Methodology

- **Analysis workspace**: `analysis/260312-0026-cnn_step_vs_nonstep/`
- **Analysis window**:
  - start = `platform_onset`
  - end = `analysis_window_end`
  - filtering/labeling follows the repository helper flow that produces `analysis_selected_group`, `analysis_is_step`, and `analysis_is_nonstep`
- **Input representation**:
  - source = min-max normalized EMG
  - each selected trial is resampled to `100` time steps
  - final tensor shape = `(trial, 16 channels, 100 time steps)`
- **Validation rule**:
  - subject-wise `GroupKFold`
  - same subject never appears in both train and test within the same fold
- **Models**:
  - baseline = logistic regression on flattened trial tensors
  - CNN = small 1D CNN with two early convolution blocks and global average pooling
- **Figure outputs**:
  - the full run saves six PNG figures under `analysis/260312-0026-cnn_step_vs_nonstep/figures/`
  - figures are intended to explain dataset shape, resampling, fold variability, and pooled held-out behavior
- **Sanity check**:
  - filtered trial count should be close to `125`
  - the current prototype treats `125 ± 5` as the acceptable range
- **Coordinate & sign conventions**:
  - Axis & Direction Sign

    | Axis | Positive (+) | Negative (-) | 대표 변수 |
    |------|---------------|---------------|-----------|
    | Time | later samples in the trial window | earlier samples in the trial window | resampled EMG timeline |
    | Channel amplitude | larger normalized activation | smaller normalized activation | all 16 EMG channels |
    | Spatial axis | not used in this classifier | not used in this classifier | N/A |

  - Signed Metrics Interpretation

    | Metric | (+) meaning | (-) meaning | 판정 기준/참조 |
    |--------|--------------|--------------|----------------|
    | classifier logit | model leans toward `step` | model leans toward `nonstep` | sigmoid threshold = `0.5` |
    | resampled EMG value | higher normalized activation | lower normalized activation | min-max normalized input |
    | biomechanical signed metric | not used | not used | this prototype only uses EMG channels |

  - Joint/Force/Torque Sign Conventions

    | Variable group | (+)/(-) meaning | 추가 규칙 |
    |----------------|------------------|-----------|
    | EMG channels | larger or smaller normalized magnitude | all channels remain non-directional amplitudes |
    | Joint angles | not used | not used | excluded from this prototype |
    | Force/Torque/COP | not used | not used | excluded from this prototype |

## Results

The first prototype is intended as a feasibility check. The important question is whether a subject-wise split remains learnable at all after the trial filtering is applied, not whether the first score is already publication-ready.

### Full-run summary

| Model | Accuracy | Balanced Accuracy | F1 | ROC AUC |
|------|----------|-------------------|----|---------|
| Logistic regression | 0.720 | 0.742 | 0.689 | 0.847 |
| Small 1D CNN | 0.752 | 0.767 | 0.712 | 0.863 |

### Reading the result

Both models remain above chance under subject-wise evaluation, which means the filtered `step` vs `nonstep` question is learnable from the current normalized EMG tensor. The small 1D CNN is not dramatically better than the baseline, but it is consistently slightly higher on the four mean metrics that were tracked in this prototype.

The fold-level spread still matters. One fold remains noticeably harder than the others, so a single average metric line should not be read as "CNN has solved the problem." The more accurate reading is that a simple temporal model shows a modest but real advantage while still depending on which subjects are held out.

## Figures

The figures are arranged in a beginner-friendly order. The easiest reading path is: first confirm which trials entered the analysis, then look at what the resampled EMG tensor looks like, then compare model performance, and finally check the pooled held-out classification behavior.

### 1. `01_dataset_label_counts.png`

This figure shows how many `step` and `nonstep` trials survive the current filtering logic. It is the quickest way to confirm that the classifier is learning from the intended comparison set rather than from a heavily imbalanced subset.

When reading this figure, the first question is simple: are both classes meaningfully represented? In the current run, the answer is yes, although `nonstep` still has more trials than `step`.

### 2. `02_emg_class_average_heatmaps.png`

This figure shows the class-average EMG tensor after every trial has been resampled to `100` time steps. Each row is one muscle channel, and each column is normalized time from the start to the end of the analysis window.

This is the most important beginner figure because it turns the abstract phrase "CNN input" into something visible. The CNN is not reading synergy weights here. It is reading a `16 x 100` pattern, and the two panels show how that average pattern differs between `nonstep` and `step`.

### 3. `03_trial_length_by_class.png`

This figure shows the original frame-length distribution before resampling. The point is not that one class is always longer. The point is that trial durations vary enough that a fixed-length representation has to be created before the CNN can use the data consistently.

If this distribution were already very tight, the resampling step would be less important. In the current dataset, the spread is wide enough that resampling is a practical requirement.

### 4. `04_fold_metric_comparison.png`

This figure compares logistic regression and the small 1D CNN on each held-out fold for `accuracy`, `balanced accuracy`, `F1`, and `ROC AUC`. The dashed horizontal lines mark each model's mean value for that metric.

This is the best figure for seeing the real tradeoff in the current prototype. The CNN is usually a little better, but it does not dominate every fold by a large margin. That pattern supports the interpretation that the CNN adds useful temporal structure without yet producing a dramatic modeling jump.

### 5. `05_confusion_matrices.png`

This figure pools all held-out predictions and shows where each model tends to be correct or wrong. The cell text includes both raw counts and row-wise percentages, so it is easier to compare `step` and `nonstep` performance even though the class counts differ.

For a beginner, this figure is more concrete than accuracy alone. It answers questions like "Is the model missing many step trials?" or "Is it overcalling one class?" in one glance.

### 6. `06_pooled_roc_curves.png`

This figure compares the pooled held-out ROC curves for logistic regression and the small 1D CNN. The ROC AUC values in the legend summarize how well each model ranks `step` above `nonstep` across many possible thresholds, not just at the default `0.5` cutoff.

This is useful because it shows that the CNN's advantage is not only a threshold artifact. In the current run, the CNN curve stays slightly above the logistic baseline across most of the operating range.

## Interpretation

The filtered trial count matters more than the first score. If the count is far from `125`, the classifier is not answering the intended research question because the trial population no longer matches the expected step-vs-nonstep comparison set.

In the current run, the small 1D CNN is modestly ahead of logistic regression on accuracy, balanced accuracy, F1, and ROC AUC. The new figures make that result easier to read in context: the class-average heatmaps show that the model is seeing structured multichannel time series, the fold-comparison figure shows that the gain is small but consistent, and the confusion-matrix/ROC figures show that the gain is not coming from only one lucky threshold.

The margin is still small enough that it should be treated as a prototype signal, not as a settled modeling conclusion. The next useful comparisons would be repeated runs, explicit raw-EMG support, and more explicit explanation tools such as channel-level attribution or saliency maps.

## Reproduction

```bash
conda run --no-capture-output -n cuda python analysis/260312-0026-cnn_step_vs_nonstep/analyze_cnn_step_nonstep.py --dry-run
conda run --no-capture-output -n cuda python analysis/260312-0026-cnn_step_vs_nonstep/analyze_cnn_step_nonstep.py
```

**Input**

- normalized EMG parquet configured in `configs/global_config.yaml`
- event workbook configured in `configs/global_config.yaml`

**Output**

- stdout summary for dry-run and full-run metrics
- six PNG figures under `analysis/260312-0026-cnn_step_vs_nonstep/figures/`
- no Excel or CSV files
