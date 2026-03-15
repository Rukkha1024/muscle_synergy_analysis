# OptiTrack Motive Conventional 39 + project medial markers

## What “Conventional (39)” usually contains

In practice, a Motive “Conventional (39)” export often resembles a Plug-in-Gait-style (PIG-like) naming set, covering:

- **Pelvis**: ASIS/PSIS (e.g., LASI/RASI/LPSI/RPSI)
- **Trunk**: clavicle/sternum/spine landmarks (e.g., CLAV/STRN/C7/T10)
- **Head**: front/back head markers (LFHD/RFHD/LBHD/RBHD)
- **Upper limbs**: shoulder, elbow, wrist, hand
- **Lower limbs**: thigh, knee, shank, ankle, toe, heel

### Why it matters

- Pelvis and trunk markers dominate whole-body COM estimation.
- Foot/toe/heel markers are the minimum required for a marker-based BoS.

## This project’s extra medial markers

This project adds medial counterparts (medial epicondyles / malleoli) as **custom labels**:

- `RUArm_3`, `LUArm_3`  → medial elbow markers
- `RShin_3`, `LShin_3`  → medial knee markers
- `RFoot_3`, `LFoot_3`  → medial ankle markers

These are described in `assets/optitrack_marker_context.xml`.

## Practical naming normalization

Many exports prepend a trial prefix:

- Example label: `251112_KUO_LASI`

Recommended normalization rule:

- `base_label = label.split('_')[-1]` **only if** you know the prefix never contains underscores inside the base marker name.
- Otherwise, detect a *common prefix* across all labels and strip it.

The computation skill `v3d-com-xcom-bos-mos` implements a safe prefix-strip strategy.
