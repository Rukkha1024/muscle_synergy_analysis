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
  - CNN early stopping now uses an **inner subject-wise validation split** created only inside the outer training fold
  - the outer held-out fold is reserved for final evaluation and is not reused for checkpoint selection
- **Models**:
  - baseline = logistic regression on flattened trial tensors
  - CNN = small 1D CNN with two early convolution blocks and global average pooling
- **Figure outputs**:
  - the full run now saves ten PNG figures under `analysis/260312-0026-cnn_step_vs_nonstep/figures/`
  - figures now cover dataset shape, resampling, representative fold behavior, multi-seed robustness, attribution, and training curves
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

The first prototype was useful because it showed that the subject-wise `step` vs `nonstep` question was learnable at all. The enhancement run changes the emphasis. The more important question now is not "Did one lucky CNN run beat logistic regression?" but "What happens when the training loop is instrumented more carefully and repeated across several seeds without leaking outer test information into model selection?"

### Legacy prototype snapshot

The original single-run prototype produced the following mean fold metrics:

| Model | Accuracy | Balanced Accuracy | F1 | ROC AUC |
|------|----------|-------------------|----|---------|
| Logistic regression | 0.720 | 0.742 | 0.689 | 0.847 |
| Small 1D CNN | 0.752 | 0.767 | 0.712 | 0.863 |

That snapshot was useful as a feasibility signal, but it did not yet show repeated seeds, training curves, or a leakage-free early-stopping path.

### Leakage-free enhancement summary

The enhancement run used `5` seeds (`42, 123, 456, 789, 1024`) and an inner subject-wise validation split for CNN early stopping. The table below reports the **mean of seed-level mean metrics**, not a p-value-based significance claim.

| Model | Accuracy | Balanced Accuracy | F1 | ROC AUC |
|------|----------|-------------------|----|---------|
| Logistic regression | 0.720 ± 0.000 | 0.742 ± 0.000 | 0.689 ± 0.000 | 0.847 ± 0.000 |
| Small 1D CNN | 0.594 ± 0.053 | 0.633 ± 0.039 | 0.558 ± 0.069 | 0.762 ± 0.027 |

### Reading the updated result

Both models remain above chance, so the filtered `step` vs `nonstep` question is still learnable from the current normalized EMG tensor. What changes after the enhancement is the comparative story. Once the outer test fold is kept clean and the CNN is repeated across multiple seeds, the previous small CNN advantage does not hold up. In this leakage-free setting, logistic regression is more stable and better on all four tracked metrics.

This does not prove that "CNN is bad" in general. It means that **this specific small 1D CNN setup is not yet robustly better than the logistic baseline under the current data size, current input contract, and current early-stopping rule**. That is a meaningful research result because it is safer than relying on one favorable run.

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

This figure is now best read as a **representative single-seed view** rather than as the final conclusion. In the enhanced workflow it still helps show fold-level behavior, but the stronger comparison now comes from the new multi-seed figure.

### 5. `05_confusion_matrices.png`

This figure pools all held-out predictions and shows where each model tends to be correct or wrong. The cell text includes both raw counts and row-wise percentages, so it is easier to compare `step` and `nonstep` performance even though the class counts differ.

For a beginner, this figure is more concrete than accuracy alone. It answers questions like "Is the model missing many step trials?" or "Is it overcalling one class?" in one glance.

### 6. `06_pooled_roc_curves.png`

This figure compares the pooled held-out ROC curves for logistic regression and the small 1D CNN. The ROC AUC values in the legend summarize how well each model ranks `step` above `nonstep` across many possible thresholds, not just at the default `0.5` cutoff.

This figure remains useful as a representative held-out view, but it should now be interpreted together with the multi-seed robustness summary instead of on its own.

### 7. `07_multi_seed_metric_distribution.png`

This figure shows the distribution of **seed-level mean metrics** for logistic regression and the CNN. Each point is one seed after averaging across the five outer folds.

This is the most important new comparison figure because it answers the question that the first prototype could not answer: does the CNN stay competitive when the random seed changes? In the current enhancement run, the answer is no. Logistic regression stays above the CNN across all tracked seed-level means.

### 8. `08_gradcam_time_saliency.png`

This figure shows class-wise **time attribution** from Grad-CAM at the last convolution layer. The values are averaged within each class and then upsampled back to the `100`-step timeline used elsewhere in the report.

This figure is intentionally limited to the time axis. It does not claim that the model has identified a causal biomechanical event. It only shows which parts of the resampled trial timeline most affected the classifier output for `step` and `nonstep`.

### 9. `09_channel_importance.png`

This figure shows class-wise **channel attribution** from `input x gradient`, averaged across time. Each bar corresponds to one EMG channel.

This figure should be read as a rough ranking of which input channels the current model reacted to most strongly. It is an explanation tool, not proof that those muscles are the true biomechanical drivers of stepping.

### 10. `10_training_curves.png`

This figure shows the CNN training curves from a representative seed. Each panel is one outer fold, with train loss and inner-validation loss plotted across epochs and the stopping point marked.

This figure matters because it makes the optimization behavior visible. In the representative seed shown here, all five folds found usable inner validation splits. Across the full five-seed enhancement run, the average best epoch was about `11.3` and the average stopping epoch was about `16.3`.

## Interpretation

The filtered trial count still matters more than any one score. If the selected trial count drifts far from `125`, the model is no longer answering the intended research question because the experimental population has changed.

With that population fixed, the enhancement run changes the scientific reading of the prototype. The safer conclusion is now: **the current logistic baseline is more robust than the current small CNN under leakage-free subject-wise evaluation**. The earlier CNN advantage looks more like a favorable prototype snapshot than a stable modeling result.

That is still a useful outcome. It means the current repository now has better evaluation instrumentation, a robustness view across seeds, and first-pass attribution figures, even though the CNN itself is not yet the better classifier. The next useful steps would be architecture changes, raw-EMG comparisons, or feature designs that preserve the same evaluation discipline.

## Reproduction

```bash
conda run --no-capture-output -n cuda python analysis/260312-0026-cnn_step_vs_nonstep/analyze_cnn_step_nonstep.py --dry-run
conda run --no-capture-output -n cuda python analysis/260312-0026-cnn_step_vs_nonstep/analyze_cnn_step_nonstep.py --seed 42 --patience 5 --cnn-epochs 50
conda run --no-capture-output -n cuda python analysis/260312-0026-cnn_step_vs_nonstep/analyze_cnn_step_nonstep.py --seeds 42,123,456,789,1024 --patience 5 --cnn-epochs 50
```

**Input**

- normalized EMG parquet configured in `configs/global_config.yaml`
- event workbook configured in `configs/global_config.yaml`

**Output**

- stdout summary for dry-run and full-run metrics
- ten PNG figures under `analysis/260312-0026-cnn_step_vs_nonstep/figures/`
- no Excel or CSV files
