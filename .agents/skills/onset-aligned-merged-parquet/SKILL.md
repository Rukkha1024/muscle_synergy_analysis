---
name: onset-aligned-merged-parquet
description: Technical spec for perturbation-task onset-aligned merged parquet datasets (typically 1000 Hz) used for step vs non-step analyses; keys, time axes, nullability, and emg_meta semantics.
---

# Perturbation Onset-Aligned Merged Parquet (Typically 1000 Hz)

## 1) What this dataset represents
- A merged time-series table for a perturbation task where signals are aligned to platform onset (time 0).
- Primary use: step vs non-step comparisons using ForcePlate / COP / COM + normalized EMG, joined with platform/step events.
- This skill describes the *semantics* (keys, time axes, nullability) that downstream scripts must respect.
- For the concrete dataset instance used in this repo (path, full column listing), see:
  - `references/platform_start_whole_merged_dataset.md`

## 2) Sampling and indexing
- Sampling rate: typically 1000 Hz (1 `DeviceFrame` = 1 ms).
- Row grain: one row per (`subject`,`velocity`,`trial_num`,`DeviceFrame`).

## 3) Key units (do not mix)
- Base unit (cache/filename/group): `subject-velocity-trial`.
- EMG event/feature unit (when using per-channel events/metrics): `subject-velocity-trial-emg_channel`.
- Recommended primary keys:
  - Trial key: (`subject`,`velocity`,`trial_num`)
  - Time key: trial key + (`DeviceFrame`)
  - Channel key: trial key + (`emg_channel`)

## 4) Time axes and event semantics (1000 Hz)
- `DeviceFrame` (i64): *relative* time axis where platform onset is set to 0.
- `platform_onset` (i64): *absolute/original* frame when platform motion starts.
- `platform_offset` (i64): *absolute/original* frame when platform motion ends.
- `step_onset` (i64, nullable): *absolute/original* frame when the foot begins to leave the ground.
- `step_TF` (str): `'step'` or `'nonstep'`.
  - For `nonstep`, `step_onset` is expected to be null in many trials.
- Important: event columns (`platform_*`, `step_onset`) are provenance in the *absolute/original* domain.
  - Do not reinterpret them as relative time unless you explicitly transform them.

## 5) Column groups (typical)
### 5.1 Identifiers / metadata
- `subject` (str): subject identifier.
- `velocity` (f64): platform speed condition (units defined upstream pipeline).
- `trial_num` (i64): trial number within subject x velocity.
- `step_TF` (str): step label.
- Optional cohort flags may exist (e.g., `age_group`, `mixed`); do not hardcode specific values.

### 5.2 Force plate (zero-corrected)
- Forces (N): e.g., `Fx_zero`,`Fy_zero`,`Fz_zero`
- Moments (Nm): e.g., `Mx_zero`,`My_zero`,`Mz_zero`

### 5.3 COP (Center of Pressure, zero-corrected)
- COP coordinates (m): e.g., `Cx_zero`,`Cy_zero`,`Cz_zero`

### 5.4 Whole-body COM (Center of Mass, zero-corrected)
- COM coordinates (m): e.g., `COMx_zero`,`COMy_zero`,`COMz_zero`

### 5.5 EMG signals (wide, normalized)
- EMG is typically stored as wide numeric columns (one per channel), time-series values per `DeviceFrame`.
- This repo commonly uses 16 channels (examples):
  - `TA,EHL,PL,MG,SOL,RF,VL,ST,GM,RA,IO,EO,ESL,EST,ESC,SCM`

## 6) `emg_meta` (List[Struct]) per-channel metrics (optional but common)
- Type: `emg_meta: List[Struct]` with one element per EMG channel, repeated per time sample.
- Common struct fields:
  - `emg_channel` (str): channel name (matches EMG wide names).
  - `emg_max_amp_value` (f64): maximum amplitude within the analysis interval.
  - `emg_max_amp_timing` (f64): timing of the maximum amplitude (units defined upstream).
  - `emg_onset_timing` (f64, nullable): onset timing; null when onset cannot be extracted.

## 7) Nullability and edge cases (expected, not errors)
- `step_onset` can be null, especially when `step_TF == 'nonstep'`.
- `emg_onset_timing` can be null for any channel/trial when detection fails or activity is absent.
- Never coerce null onsets to 0; keep nulls to preserve "missing vs. early onset" semantics.

## 8) `emg_meta` duplication caveat (important)
- Because the row grain includes `DeviceFrame`, the `emg_meta` list may be stored repeatedly across many frames.
- Exploding `emg_meta` can multiply rows by ~Nchannels per time sample; plan memory and runtime accordingly.
- For one record per trial x channel, deduplicate on (`subject`,`velocity`,`trial_num`,`emg_channel`) after exploding.
- For time-resolved EMG analyses, use the wide EMG columns keyed by `DeviceFrame` (not `emg_meta`).

## 9) Common safe checks (minimum validation per run)
- `subject`,`velocity`,`trial_num` are non-null.
- Within each trial, `DeviceFrame` is monotonic and covers the expected window.
- Event frames (`platform_onset`,`platform_offset`,`step_onset`) are within the trial's absolute/original range (when present).
- `step_TF` is consistent with `step_onset` nullability expectations.

## 10) Join/aggregation guidance
- Trial-level joins: join on (`subject`,`velocity`,`trial_num`) only.
- Time-series joins: join on trial key + `DeviceFrame`; do not join by row order.
- Channel-level joins: join on trial key + `emg_channel`; avoid implicit mapping between `emg_meta` and wide EMG.
- Prefer `polars` for IO/transforms, and use `pandas` only when required by downstream APIs.

## 11) What this dataset is NOT
- Not a long-format EMG table; EMG is stored as wide columns + a list-of-struct metrics column.
- Not guaranteed to include every provenance column used elsewhere (e.g., `original_DeviceFrame` may be absent).
- Not a visualization configuration source (plot styling belongs in visualization code, not in skills/config).

