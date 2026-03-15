---
name: data-context
description: Repository-wide experiment context for "주제 2" (platform translation perturbation) where step vs non-step trials coexist under the same perturbation condition; use when writing code/analysis in this repo so outputs align with the paper goals and performance variable comparisons.
---

# data-context: 주제 2 (Step vs Non-step) 실험/분석 컨텍스트

## 1) One-liner purpose
This repository is treated as the data + code for the paper note:
- `종합) 주제 2 -  동일 조건 섭동 시 균형 회복 전략(step vs. non-step) 차이에 따른 수행력(performance) 변인 비교 분석.md`

When writing code here, default to the assumption that the user's intent is:
- Compare balance-recovery strategy differences (`step` vs `nonstep`) under the *same perturbation condition*.
- Quantify differences using performance variables across domains (EMG / COM / BOS / kinematics / kinetics).

## 2) Core research idea (what must not get lost)
- Same perturbation condition can yield both step and non-step outcomes.
- The analysis goal is to isolate strategy differences from perturbation-intensity differences.

Implication for coding:
- Do not accidentally change the grouping/conditioning so that "step vs non-step" becomes confounded with different perturbation intensities or different windows.

## 3) Default modeling / stats stance (paper-aligned)
Unless the user requests otherwise:
- Use raw-trial data (do not pre-average to subject means unless asked).
- Use LMM per dependent variable:
  - Fixed effect: strategy (`step_TF` as step vs nonstep)
  - Random effect: subject random intercept
  - Estimation: REML
- Multiple comparison correction:
  - Benjamini-Hochberg FDR
  - Apply within variable families (e.g., EMG / kinematics / kinetics) when reporting many dependent variables.

If you need an analysis scaffold, use:
- `analysis-report` for new analysis folders under `analysis/`
- `pingouin-excel-stat-analysis` only when the user explicitly wants Excel outputs

## 4) Data semantics you should reuse instead of reinventing
For onset-aligned merged parquet semantics (keys, time axes, nullability, `emg_meta`):
- Use the `onset-aligned-merged-parquet` skill.

## 5) Repo conventions (non-negotiable)
- Prefer `polars` first, then `pandas` only when required by downstream APIs.
- Keep scripts separated by biomechanical variable categories:
  - EMG
  - COM
  - torque
  - joint
  - GRF & COP
- When exporting CSV that may include Korean text, default to UTF-8 with BOM (`utf-8-sig`).
