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

## Interpretation

The filtered trial count matters more than the first score. If the count is far from `125`, the classifier is not answering the intended research question because the trial population no longer matches the expected step-vs-nonstep comparison set.

In the current run, the small 1D CNN is modestly ahead of logistic regression on accuracy, balanced accuracy, F1, and ROC AUC. This suggests that a simple temporal model can recover a little more useful structure from the EMG sequence than a flattened baseline, even before any deeper architecture tuning.

The margin is still small enough that it should be treated as a prototype signal, not as a settled modeling conclusion. The next useful comparisons would be repeated runs, explicit raw-EMG support, and ablations on resampling length or channel subsets.

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
- no Excel or CSV files

## Figures

This first prototype does not generate figures. The immediate focus is validating the filtered trial population, the fixed-length tensor conversion, and the subject-wise baseline/CNN comparison.
