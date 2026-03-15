# <Analysis Title>

## Research Question

**"<core question in quotes>"**

Background context in 1-2 sentences.

## Data Summary

- **N trials** (step=X, nonstep=Y)
- Data source: `output/all_trials_timeseries.csv` (N frames, 100Hz)
- Trial classification: `data/perturb_inform.xlsm` (platform sheet → step_TF)
- Key variables: <list dependent variables>

## Analysis Methodology

- **Analysis window**: <e.g., [platform_onset, step_onset] per trial>
  - Step trials: <actual step_onset_local>
  - Nonstep trials: <mean step_onset of same (subject, velocity) step trials>
- **Statistical model**: <e.g., LMM: DV ~ step_TF + (1|subject), REML>
- **Multiple comparison correction**: <e.g., Benjamini-Hochberg FDR per variable family>
- **Significance reporting**: `p < 0.05` 기준(`alpha=0.05`), `Sig` only (significant = `< 0.05`, non-significant = `n.s.`), hide numeric `p` and `df` in user-facing tables
- **Coordinate & sign conventions**:
  - Axis & Direction Sign

    | Axis | Positive (+) | Negative (-) | 대표 변수 |
    |------|---------------|---------------|-----------|
    | AP (X) | `+X = Anterior` | `-X = Posterior` | `COM_X`, `vCOM_X`, `xCOM_X`, `COP_X_*`, `MOS_AP_v3d` |
    | ML (Y) | `+Y = Left` | `-Y = Right` | `COM_Y`, `vCOM_Y`, `xCOM_Y`, `COP_Y_*`, `MOS_ML_v3d` |
    | Vertical (Z) | `+Z = Up` | `-Z = Down` | `COM_Z`, `vCOM_Z`, `xCOM_Z`, `GRF_Z` |

  - Signed Metrics Interpretation

    | Metric | (+) meaning | (-) meaning | 판정 기준/참조 |
    |--------|--------------|--------------|----------------|
    | `MOS_minDist_signed` | `inside` | `outside` | convex hull based signed min distance |
    | `MOS_AP_v3d` | AP bound 내부 | AP bound 외부 | closest-bound (AP) |
    | `MOS_ML_v3d` | ML bound 내부 | ML bound 외부 | closest-bound (ML) |

  - Joint/Force/Torque Sign Conventions

    | Variable group | (+)/(-) meaning | 추가 규칙 |
    |----------------|------------------|-----------|
    | Joint angles (X/Y/Z) | X: `+Flex / -Ext` (ankle X: `+Dorsi / -Plantar`), Y: `+Add / -Abd`, Z: `+IR / -ER` | Left Y/Z sign-unification 적용 여부를 명시 |
    | `GRF_*`, `GRM_*`, `AnkleTorque*` | 플랫폼 onset 기준 `Δ`값 해석 여부 | onset-zeroed 기준인지 absolute 기준인지 명시 |
    | `AnkleTorque*_int`, `AnkleTorque*_ext` | 내부토크와 외부토크의 부호 관계 | `AnkleTorque*_int = -AnkleTorque*_ext` 명시 |
    | `COP_*_m`, `COP_*_m_onset0` | absolute 좌표 vs onset-zeroed 변위 | 두 표현을 구분해 해석 |
- **Peak definition**: `*_peak` uses `abs_peak = max(|x|)` within the analysis window
- **Variable families**:
  - <Family 1>: <list variables>
  - <Family 2>: <list variables>
- **Special handling**: <any notable decisions, e.g., exclusion criteria>

---

## Results

### 1. <First analysis>

(tables, statistics, Sig markers, effect sizes)

| Variable | Estimate | SE | t | Sig |
|----------|----------|----|---|-----|
| ... | ... | ... | ... | ... |

### 2. <Second analysis>

...

---

## Interpretation

Directional interpretation statements should follow the Methodology `Coordinate & sign conventions` tables.

### <Interpretation subtitle 1>

...

### Conclusion

1. **Key finding 1**
2. **Key finding 2**
3. **Key finding 3**

---

## Reproduction

```bash
conda run --no-capture-output -n module python analysis/<topic>/analyze_<topic>.py
```

**Input**:
- `output/all_trials_timeseries.csv`
- `data/perturb_inform.xlsm`

**Output**: fig1–figN PNG (generated in this folder)

## Figures

| File | Description |
|------|-------------|
| fig1_xxx.png | ... |
| fig2_xxx.png | ... |
| fig3_xxx.png | ... |
