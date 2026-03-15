# BOS+COM XY PNG/GIF: Design Notes (replace_V3D)

This reference explains the *design intent* and key implementation points of:

- `scripts/plot_bos_com_xy_sample.py`

Use this when you need to:

- confirm what the plot is actually showing (and what it is not showing)
- adjust coordinate view/labels
- understand step vs nonstep behaviors (BOS freeze at step_onset)
- produce consistent outputs across repeated runs

## What The Plot Represents

The visualization overlays, on a 2D plane:

- `BOS` as an axis-aligned rectangle per frame using bounds:
  - `BOS_minX`, `BOS_maxX`, `BOS_minY`, `BOS_maxY`
- `COM` as a point per frame:
  - `COM_X`, `COM_Y`

The output is intended as a fast "sanity/interpretation" plot:

- where COM is relative to BOS (inside vs outside)
- how BOS and COM evolve over time
- where key events occur (platform onset/offset, step onset)

It is not a force-plate COP plot, and it is not a polygonal BOS (hull) plot.

## Data Requirements / Contract

The script expects a "long" time-series CSV, typically:

- `output/all_trials_timeseries.csv`

### Trial keys

Trial identity is fixed by:

- `subject` (string)
- `velocity` (float)
- `trial` (int)

### Time index

The per-row time index is:

- `MocapFrame` (int, expected monotonic after sorting)

### Event columns

Required:

- `platform_onset_local` (int)
- `platform_offset_local` (int)

Optional:

- `step_onset_local` (int or null)

If `step_onset_local` is null, the trial is treated as nonstep for BOS-freeze logic.

### Optional "time" for info panel

If present:

- `time_from_platform_onset_s` is used to display `t=... s` in the GIF info panel.

## Valid Frames Filtering

The script constructs a `valid_mask` to avoid plotting unusable frames.

### Invalid conditions

Frames are excluded when:

1) any of COM or BOS bounds are non-finite (NaN/Inf)
2) BOS bounds are inverted (`min > max`) in either axis

These conditions are enforced before inside/outside classification and before rendering.

If no valid frames remain, the script raises an error early.

## Inside vs Outside Classification

For each frame, inside is computed from the *original* BOS bounds and COM coordinates:

- inside iff:
  - `BOS_minX <= COM_X <= BOS_maxX`
  - `BOS_minY <= COM_Y <= BOS_maxY`

This produces `inside_mask` (bool per row), and:

- GIF current-point color:
  - inside: green
  - outside: red
- Static plot scatters inside and outside frames separately

## Display Rotation (View)

The script separates:

- `TrialSeries`: raw per-frame series from CSV
- `DisplaySeries`: rotated (display) series used only for plotting

### CCW rotation

Rotation degrees allowed:

- `0`, `90`, `180`, `270`

Rotation is applied to:

- COM coordinates directly
- BOS bounds by rotating the four corners of the rectangle and recomputing bounds in rotated coordinates

Rotation mapping for points:

- 0 deg: `(x, y)`
- 90 deg: `(-y, x)`
- 180 deg: `(-x, -y)`
- 270 deg: `(y, -x)`

### Axis limits

Axis limits are derived from:

- rotated COM x/y
- rotated BOS bounds
- only valid frames

Then a margin is added:

- 5% of data span per axis (at least `1e-3`)
- if span is near zero, a larger minimum margin is enforced

### Axis labels

Axis labels are hard-coded to express user-facing directions:

- X: `[- Left / + Right]`
- Y: `[+ Anterior / - Posterior]`

This is intentionally tied to the *display* coordinate after rotation.

If your experiment coordinate definitions differ, change either:

- `--rotate_ccw_deg`
- or the axis label strings in the script

## Static PNG Rendering

The PNG is a summary view (one figure per trial):

- overlay all BOS outlines (valid frames) as thin, low-alpha grey lines
- plot full COM trajectory (line)
- scatter inside points (green) and outside points (red)
- highlight event frames (if present in valid rows):
  - platform onset: marker `o`
  - platform offset: marker `s`
  - step onset: marker `^` (skipped if null or if the exact frame is not present in valid rows)
- show a summary box with:
  - valid/total frames
  - inside/outside counts and inside ratio
- title and (optional) subtitle

## GIF Rendering

The GIF shows a frame-by-frame animation:

- BOS rectangle patch (fill + edge)
- COM cumulative trail line (up to current frame)
- current COM point (inside/outside color)
- info panel with frame/time/status

### Frame sampling

Frames are taken from valid indices:

- `frame_indices = valid_indices[::frame_step]`
- ensure the last valid frame is included even if it is not aligned to `frame_step`

### BOS freeze at step_onset (step trials)

Rule:

- if `step_onset_local` exists:
  - find the exact `MocapFrame == step_onset_local` among valid rows
  - if not found, fall back to the first valid frame where `MocapFrame >= step_onset_local`
  - from that point on, BOS is rendered using the frozen BOS bounds
- if `step_onset_local` is null:
  - BOS remains live (updated every frame)

Important nuance:

- COM continues to update to the end regardless of BOS freeze.

This matches the requirement: "BOS 멈추고, COM은 끝까지 보여주기".

### Info panel content

The info panel includes:

- current frame number and animation frame counter
- optional time (seconds from platform onset) if available
- status: inside/outside
- event state: platform_onset / platform_offset / step_onset (exact-frame match)
- BOS state: `live` or `frozen@step_onset`
- inside ratio and counts

## Trial State Subtitle (step_R/step_L/nonstep)

The subtitle is derived from:

- `data/perturb_inform.xlsm`
- sheet: `platform`
- columns: `subject, velocity, trial, state`

### Matching logic

The lookup matches:

- `subject` string (stripped)
- `velocity` using `np.isclose(..., atol=1e-9)` (exact-ish float)
- `trial` numeric

If no match exists or the sheet is missing columns:

- print a warning
- use `trial_type=unknown` subtitle

### Canonicalization and labels

The state is canonicalized to:

- `step_R`, `step_L`, `nonstep`, `footlift`, or `unknown` / raw text

Then formatted as:

- `trial_type=step (R foot)`
- `trial_type=step (L foot)`
- `trial_type=nonstep`
- `trial_type=footlift (nonstep)`

### Relationship to BOS-freeze logic

The BOS-freeze logic depends on:

- CSV `step_onset_local`

The subtitle depends on:

- workbook `platform.state`

They are intentionally separate:

- The workbook is treated as metadata for labeling.
- The CSV event is treated as authoritative for animation behavior.

If you need behavior to be driven by the workbook state (instead of step_onset_local), refactor accordingly.

## Extension Points / Common Tweaks

### Stop the animation at step_onset (instead of BOS freeze)

Currently, the script freezes BOS and keeps COM going.

To stop the animation early, you would modify:

- the `frame_indices` construction to cut off at `bos_freeze_idx` (or at step frame)

### Make BOS a polygon (not a rectangle)

The current BOS is a min/max rectangle per frame.

If you have BOS vertices/hull points, replace:

- rectangle patch + outline drawing

with a polygon patch and update inside/outside logic accordingly.

### Change axis semantics or labels

If the experiment uses a different coordinate convention, adjust:

- `--rotate_ccw_deg`
- axis label strings

Keep the title `view=CCW...` to avoid ambiguity in exported figures.

## Reproducibility Notes

Within the same environment (same conda env and matplotlib/pillow stack), the script is expected to be deterministic because:

- frames are processed in fixed order
- no random sampling is used
- output filenames are deterministic

Across different machines / matplotlib versions / fonts, byte-level output may differ even if the plot looks identical.
