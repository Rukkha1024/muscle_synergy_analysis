---
name: motive-marker-v3d-guideline
description: Interpret OptiTrack Motive marker sets (Conventional 39 + user medial markers) and translate them into Visual3D-style biomechanical workflows; includes this project's user-data conventions (file naming, events, coordinates).
---

## When to use

Use this skill when you need to:

- Understand what markers exist in an OptiTrack Motive **Conventional (39)** full-body skeleton export (and this project’s **extra medial markers**).
- Decide what **Visual3D (V3D)**-style biomechanical analyses are feasible **without force plates**.
- Set up a repeatable analysis recipe for this project’s perturbation trials (platform onset / step onset).
- Provide the marker/coordinate/event assumptions that the computation skill **`v3d-com-xcom-bos-mos`** will rely on.

## What you should check first (fast triage)

1. **Data type & preprocessing**
   - Marker trajectories are labeled and filtered already (Motive labeling + filtering done upstream).
   - Units are meters (verify `POINT:UNITS` in C3D).

2. **Marker set availability**
   - Confirm that the trial contains pelvis (ASIS/PSIS), trunk, head, and lower-limb markers.
   - Confirm whether **medial markers** are present (this project uses them; see `assets/optitrack_marker_context.xml`).

3. **Force plate constraint**
   - If only **one** force plate exists (or force data are unusable), you **must** use marker/kinematics-based BoS and contact logic (no COP-based BoS).

4. **Events**
   - Platform onset/offset and step onset come from an external event table (see “User dataset conventions” below).

## Marker set guide (Motive Conventional 39 + project medial markers)

### Canonical intent of Conventional (39)

- A full-body marker configuration meant to reconstruct a skeleton and joint centers.
- Pelvis markers are the key drivers for downstream segment definitions.

### What this project adds

This project supplements the standard set with **medial counterparts** of key joint markers (elbow, knee, ankle). These support:

- Joint center estimation as **midpoint**(lateral, medial)
- Better knee/ankle axis definition

See the full context XML:

- `assets/optitrack_marker_context.xml`

### Practical mapping notes (common in exported C3D)

Depending on the pipeline, the same physical marker set can appear with different label conventions:

- OptiTrack docs often use `LIAS/RIAS/LIPS/RIPS`, etc.
- Many biomechanics exports use Plug-in-Gait-like names: `LASI/RASI/LPSI/RPSI`, `LHEE/LTOE`, etc.
- Many datasets prepend a trial prefix (e.g., `251112_KUO_`), meaning the *base marker name* is after the final underscore.

**Action:** For computation, always normalize to *base marker names* (strip common prefixes).

## Visual3D-style biomechanical analyses you can do (no force plates)

### Model/kinematics-derived signals (typical V3D workflow)

- Segment coordinate systems (pelvis, thigh, shank, foot, trunk)
- Joint angles (cardan/euler choices must be specified)
- Whole-body COM (model-based) and COM velocity

### Stability metrics feasible without COP

You can still compute **dynamic stability** metrics using marker-based BoS:

- **COM**: from model/segment definitions (or a validated proxy)
- **XCoM** (Hof): COM plus velocity scaled by an inverted-pendulum factor
- **BoS** polygon/bounds: from foot landmarks (measured or virtual)
- **MoS**: shortest distance from XCoM to BoS boundary (signed)

For the actual implementation recipe used in this project, use the computation skill:

- **`v3d-com-xcom-bos-mos`**

## User dataset conventions (THIS PROJECT)

### File naming

C3D trial naming convention:

- `{date}_{name_initial}_perturb_{velocity}_{trial}.c3d`

Example:

- `251112_KUO_perturb_60_001.c3d`

### Event source

Platform onset/offset and step onset are **not** computed from force plates.

- Source file: `perturb_inform.xlsm`
- Sheet: `platform`
- Required columns:
  - `subject`, `velocity`, `trial`
  - `platform_onset`, `platform_offset`
  - `step_onset` (may be blank for non-step)
  - `state` often encodes stepping side (e.g., `step_L`, `step_R`)

### Trial trimming / range assumption

In this project, each exported C3D is trimmed to:

- `[platform_onset - 100 frames, platform_offset + 100 frames]`

So within the trimmed file, **platform onset occurs at ~frame 100** (0-indexing may vary by tool).

### Coordinate sanity checks

Because coordinate conventions can differ across systems, always **verify** by inspection:

- The **vertical axis** is the axis where pelvis/head markers are ~1–2 m above foot markers.
- The **horizontal plane** is the other two axes.

Do not hardcode axes unless you have confirmed them for the dataset.

### Subject anthropometrics (required for this project)

This project’s analysis *must* use anthropometrics.

If the user did not provide anthropometrics, you must request at minimum:

- leg length
- foot length
- foot width
- ankle width
- knee width

(Other measures like elbow/wrist width are useful if building a full Plug-in-Gait-like model.)

#### Example: 김우연 (provided)

Raw measurements provided by the user (units as collected):

- leg length: 86 (cm)
- knee width: 9 (cm)
- ankle width: 6.5 (cm)
- foot width: 8.5 (cm)
- foot length: 240 (mm)
- elbow width: 8 (cm)
- wrist width: 5.5 (cm)

**Conversion reminders**

- cm → m: divide by 100
- mm → m: divide by 1000

## Hand-off to the computation skill

When you move from “guideline” to “compute metrics,” provide the following to `v3d-com-xcom-bos-mos`:

- path(s) to C3D trial(s)
- path to `perturb_inform.xlsm` (or event frames)
- subject anthropometrics (convertible to meters)
- optional: V3D-exported COM file for validation

