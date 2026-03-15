# Dataset Instance: platform_start_whole_merged.parquet (Repo-Specific)

This file captures the concrete dataset instance used in this repository. The *general* semantics are defined in the parent skill:

- `../SKILL.md` (onset-aligned-merged-parquet)

## Path
- `analysis/meta_merge_0210-0152/platform_start_whole_merged.parquet`

## Summary
- Perturbation task where the platform translates forward during quiet standing.
- Intended usage: step vs non-step comparisons with onset-aligned time axis (`DeviceFrame` where platform onset = 0).
- Contains ForcePlate / COP / COM (zero-corrected) plus normalized EMG time-series, joined with platform and step events.

## Expected grain / keys
- Row grain: (`subject`,`velocity`,`trial_num`,`DeviceFrame`)
- Trial key: (`subject`,`velocity`,`trial_num`)
- Channel key (when working with per-channel metrics): (`subject`,`velocity`,`trial_num`,`emg_channel`)

## Key columns (high-value, not exhaustive)
### Identifiers / labels
- `subject` (str)
- `velocity` (f64)
- `trial_num` (i64)
- `step_TF` (str): `step` or `nonstep`

### Time / events (1000 Hz)
- `DeviceFrame` (i64): relative, platform onset is 0
- `platform_onset` (i64): absolute/original frame
- `platform_offset` (i64): absolute/original frame
- `step_onset` (i64, nullable): absolute/original frame

### Force plate (zero-corrected)
- Forces (N): `Fx_zero`,`Fy_zero`,`Fz_zero`
- Moments (Nm): `Mx_zero`,`My_zero`,`Mz_zero`

### COP (zero-corrected)
- `Cx_zero`,`Cy_zero`,`Cz_zero` (m)

### COM (zero-corrected)
- `COMx_zero`,`COMy_zero`,`COMz_zero` (m)

### EMG (wide, normalized)
Common 16 channels in this repo:
- `TA,EHL,PL,MG,SOL,RF,VL,ST,GM,RA,IO,EO,ESL,EST,ESC,SCM`

### Per-channel metrics (nested)
- `emg_meta: List[Struct]`
  - `emg_channel` (str)
  - `emg_max_amp_value` (f64)
  - `emg_max_amp_timing` (f64)
  - `emg_onset_timing` (f64, nullable)

## Nullability reminders
- `step_onset` can be null for nonstep trials.
- `emg_onset_timing` can be null when onset detection fails or muscle activity is absent.

