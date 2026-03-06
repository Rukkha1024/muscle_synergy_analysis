# Scenario Journal

- `S01_fixture_bundle`: synthetic parquet/csv/xlsm plus YAML configs for fixture-driven EMG pipeline checks.
- `S02_trial_alignment`: validates that sliced trials preserve `original_DeviceFrame` and align the relative frame origin to platform onset.
- `S03_nmf_contract`: validates NMF output shapes, unit-norm `W` columns, and `vaf >= 0.9` on an exact nonnegative matrix.
- `S04_cluster_duplicates`: validates strict clustering avoids within-trial duplicate assignments on separable synergy vectors.
- `S05_fixture_run_artifacts`: validates the end-to-end fixture run produces `outputs/final.parquet` and per-run metadata once `main.py` exists.
