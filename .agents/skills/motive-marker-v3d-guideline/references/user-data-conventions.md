# User data conventions (perturbation project)

## Trial file naming

Pattern:

- `{date}_{name_initial}_perturb_{velocity}_{trial}.c3d`

Example:

- `251112_KUO_perturb_60_001.c3d`

Recommended parsing:

- `date` : first token
- `name_initial` : second token
- `velocity` : token after `perturb` (numeric)
- `trial` : last token before `.c3d` (numeric)

## Event table

All key events come from:

- `perturb_inform.xlsm` → `platform` sheet

Required columns:

- `subject` (Korean name)
- `velocity` (numeric)
- `trial` (integer)
- `platform_onset`, `platform_offset` (frame indices in the *original* capture)
- `step_onset` (may be blank)
- `state` (often encodes stepping foot: `step_L`, `step_R`, or `nonstep`/`footlift`)

Matching rule (recommended):

- Match by `(subject, velocity, trial)`.

If the C3D filename contains only an initial (e.g., `KUO`), the analysis must be told which `subject` row to use.

## Trial range / trimming

Project rule:

- Exported C3D is trimmed to `[platform_onset − 100, platform_offset + 100]` frames.

Implication:

- In the trimmed C3D, `platform_onset` will appear at ~`frame = 100`.

## Coordinate note

A note provided for this dataset:

- X axis uses **negative X** as A/P
- Y axis uses **positive Z** as R/L
- Z axis uses **positive Y** as UP/DOWN

In practice, always verify the *actual* vertical axis from the marker trajectories:

- Pelvis/head markers should be ~1–2 m above toe/heel markers.
- The axis that best matches this “height” behavior is the vertical axis.

Do not assume axis ordering until verified.

## Anthropometrics (김우연 example)

Provided by the user (raw):

- 다리길이: 86 (cm)
- 무릎넓이: 9 (cm)
- 발목넓이: 6.5 (cm)
- 발넓이: 8.5 (cm)
- 발길이: 240 (mm)

These are required inputs for XCoM and marker-based BoS landmark generation.
