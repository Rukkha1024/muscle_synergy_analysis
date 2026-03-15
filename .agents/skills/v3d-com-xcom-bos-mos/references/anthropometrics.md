# Anthropometrics requirements

This project requires subject anthropometrics. Do not run the pipeline without them.

## Minimum required fields

Provide (per subject):

- leg_length_m (meters)
- foot_length_m (meters)
- foot_width_m (meters)
- ankle_width_m (meters)
- knee_width_m (meters)

## How each measure is used

### Leg length -> XCoM

Leg length sets the inverted-pendulum scaling used in XCoM:

- omega0 = sqrt(g / leg_length)
- XCoM = COM + COM_velocity / omega0

### Foot width and ankle width -> BoS polygon

When you only measure one forefoot marker (e.g., TOE) and one heel marker (HEE), you still need medial and lateral edges to build a BoS polygon.

This pipeline builds virtual landmarks by offsetting the TOE and HEE markers along the foot's local mediolateral axis:

- Forefoot medial/lateral: use foot_width_m
- Rearfoot medial/lateral: use ankle_width_m as a rearfoot width proxy

### Foot length -> sanity and scaling

Foot length is mainly used for sanity checks and for optional landmark placement rules when toe markers are not located at the intended metatarsal position.

### Knee width -> optional model refinement

Knee width can be used to build better joint centers and segment coordinate systems if you implement a full Plug-in-Gait-like model. For MoS, it is not strictly required, but this project collects it and expects it to be present.

## Unit conversion reminders

- cm to m: divide by 100
- mm to m: divide by 1000

## Example file

See:

- assets/example_anthro_kimwooyeon.yaml
