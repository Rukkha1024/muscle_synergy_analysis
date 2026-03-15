# Visual3D-equivalent logic for COM → XCoM → BoS → MoS

This document summarizes the canonical Visual3D tutorial logic you should mirror in code.

## 1) COM and COM velocity

Visual3D approach (conceptually):

- Build a kinematic model from markers (segments + inertial properties)
- Compute the model’s Center of Gravity (COG = COM)
- Compute COM velocity as a derivative of COM

In many perturbation experiments, whole-body COM motion is dominated by trunk/pelvis; if you are not building a full inertial model, you may use a **validated proxy** (but you must validate against a V3D export when available).

## 2) XCoM (Hof inverted pendulum)

Hof’s definition uses the inverted pendulum eigenfrequency:

- \( \omega_0 = \sqrt{g / l} \)

and defines the Extrapolated Center of Mass (XCoM) in the horizontal plane as:

- \( \text{XCoM} = \text{COM} + \dot{\text{COM}} / \omega_0 \)

Where:

- \(g\) is gravitational acceleration (9.81 m/s²)
- \(l\) is effective pendulum length (commonly approximated with **leg length**)

Visual3D implements this via an expression function commonly referenced as `EXTRAPOLATED_COG(COM, LEG_LENGTH)`.

## 3) Base of Support (BoS)

Without force plates, BoS is built from **foot landmarks**. The tutorial logic is:

- Define per-foot landmarks such as heel and metatarsal heads
- In double support, BoS is the polygon surrounding both feet
- In single support, BoS is the polygon of the stance foot only

If metatarsal head markers are not measured, create **virtual** landmarks using foot width/ankle width and the foot’s local mediolateral axis.

## 4) Margin of Stability (MoS)

Hof defines MoS as the shortest distance between XCoM and the BoS boundary.

Practical implementation:

- Project XCoM to the ground plane
- Compute the convex hull (BoS polygon) from stance foot landmark points
- Compute the shortest distance from XCoM to the polygon edges
- Use a **signed** convention:
  - positive: XCoM inside BoS
  - negative: XCoM outside BoS

