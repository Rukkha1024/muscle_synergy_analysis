# Default marker mapping (PIG-like labels)

The scripts default to a Plug-in-Gait-like naming set commonly seen in Motive Conventional exports.

## Required lower-limb markers

Left:

- LASI, RASI, LPSI, RPSI (pelvis)
- LKNE (lateral knee)
- LShin_3 (medial knee; project-added)
- LANK (lateral ankle)
- LFoot_3 (medial ankle; project-added)
- LHEE (heel)
- LTOE (toe / forefoot)

Right:

- RKNE, RShin_3, RANK, RFoot_3, RHEE, RTOE

## Trunk/head markers (COM proxy)

- C7, CLAV, STRN, T10, RBAK
- LFHD, RFHD, LBHD, RBHD

## Prefix handling

Many C3D labels are prefixed (example: 251112_KUO_LASI).

The scripts detect a common prefix and strip it, so the base name becomes LASI, etc.

If your dataset uses a different naming convention, create your own mapping file and modify scripts/marker_mapping.py.
