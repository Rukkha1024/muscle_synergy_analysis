# Cheung 2021 Step vs Nonstep Synergy Comparison

## Research Question

This analysis asks whether the repository's perturbation `step` and `nonstep` trials show paper-style differences in muscle-synergy structure when we re-extract trial synergies with a Cheung 2021-inspired NMF rule. The workflow keeps the repository's trial selection and analysis windows fixed, then compares the resulting paper-style centroids, cross-fit behavior, and merging patterns against each other and against the baseline run `default_run`.

## Prior Studies

### Cheung et al. (2020) — Plasticity of muscle synergies through fractionation and merging during development and training of human runners

**Methodology:** The paper used non-negative matrix factorization on running EMG and selected the smallest rank that reached an EMG reconstruction `R²` of about `0.80`. It clustered subject synergies with k-means, used the gap statistic to choose the number of clusters, defined relatively subject-invariant clusters as those contributed by at least one-third of the subjects, matched cluster centroids with scalar products, and treated pairs with `SP < 0.8` as unmatched. The paper also used cross-fit, sparseness, and NNLS-based merging or fractionation logic.

**Experimental design:** The study analyzed `63` subjects over `100` sessions across preschoolers, sedentary adults, novice runners, experienced runners, and elite runners. It used `15` right-sided lower-limb running muscles.

**Key results:** The paper reported that preschooler data required about `6` synergies while sedentary adults required about `7` synergies at `R² ≈ 0.80`. It identified `9` clusters in preschoolers and `12` in sedentary adults, with `7` and `11` subject-invariant clusters respectively. Between those two groups, `6` centroid pairs matched at moderate-to-excellent similarity (`SP ≥ 0.87`), while `5` sedentary clusters remained unmatched (`SP < 0.8`). It further reported fractionation examples with reconstruction similarity `SP ≥ 0.93`, decreasing sparseness with running expertise, and a Merging Index that increased from sedentary to elite groups.

**Conclusions:** The paper argued that early running synergies become fractionated during development and that training later promotes merging of specific pre-existing synergies. The authors framed fractionation and merging as complementary mechanisms for adapting motor modules to biomechanics and training demands.

## Methodological Adaptation

| Prior Method | Current Implementation | Deviation Rationale |
| --- | --- | --- |
| Raw EMG preprocessing | Filter, rectify, and normalize raw running EMG | Reuse repository normalized parquet and do not replay raw preprocessing | The current repository only exposes the post-processed perturbation EMG input. |
| Muscle set | 15 right-sided running muscles | 16-channel perturbation EMG muscle list from the repository config | The project has a fixed 16-channel input and the user asked to keep it. |
| Comparison design | Cross-sectional and longitudinal running groups | Pooled step vs nonstep perturbation trials | The scientific question in this repository is strategy difference under the same perturbation condition. |
| Clustering assignment | Plain pooled k-means over candidate K values | Plain pooled k-means over candidate K values | This revision removes the earlier project-specific duplicate-free reassignment path. |
| Activation analysis | The paper also analyzes temporal activation coefficients | Focus on structure-level comparison plus cross-fit and structural merging | Temporal activation replication would not be comparable after the project-specific adaptation. |
| Gap-statistic runtime | 500 reference sets and 100 restarts per reference | Script defaults are 500 reference sets and 100 restarts per reference; this run used 5 and 3 | The checked-in script defaults are paper-aligned, but local validation may still use explicit CLI overrides for tractable runtime. |

This analysis adopts the paper's structure-comparison logic but modifies the input source, the muscle set, and the comparison design because this repository is organized around perturbation `step` versus `nonstep` trials rather than running expertise groups.

## Data Summary

The validated selected-trial set contains `step=53` trials and `nonstep=72` trials from `N=24` unique subjects. The paper-style NMF threshold was missed by `0` trial(s). The repository's 16-channel muscle list was reused exactly: `TA, EHL, MG, SOL, PL, RF, VL, ST, RA, EO, IO, SCM, GM, ESC, EST, ESL`.

Baseline run `default_run` metadata provided the canonical trial list and analysis windows. The normalized EMG parquet referenced by `configs/global_config.yaml` supplied the time-series input for re-analysis.

## Analysis Methodology

The script rebuilt each selected trial from the normalized EMG input, validated that the rebuilt windows matched baseline run `default_run`, and then ran a multiplicative-update NMF search over ranks `1..16` with `20` random restarts per rank. The selected rank was the smallest rank whose centered-variance reconstruction reached `R² >= 0.80`; if a trial never reached the threshold, the script kept the best-`R²` rank and marked the trial as a threshold miss.

The step and nonstep synergy vectors were clustered separately with plain pooled k-means. For each candidate `k` in `2..20`, the algorithm ran k-means with random data-point centroid initialization `10` times in this run and kept the smallest squared-Euclidean objective. The script defaults remain paper-aligned at `1000` observed repeats, `500` reference datasets, and `100` repeats per reference dataset, even though local validation can still override those counts explicitly. Common clusters were defined as clusters contributed by at least `ceil(N/3)` subjects in the corresponding step class.

The analysis then computed centroid matching, Hoyer sparseness, pooled all-by-all cross-fit, centroid-level merging or fractionation, individual-level merging indices, and within-group comparisons against the baseline representative synergies. All centroid matching used scalar products, and any match with `SP < 0.8` remained unmatched.

## Results

The paper-style rank distributions differed only modestly from the baseline rank distribution. The current rank distribution was `{2: 11, 3: 35, 4: 36, 5: 30, 6: 10, 7: 2, 8: 1}`, while the baseline distribution was `{1: 1, 2: 6, 3: 37, 4: 50, 5: 26, 6: 4, 7: 1}`. The rank-delta summary relative to baseline was `{-1: 20, 0: 70, 1: 32, 2: 3}`.

The plain-k-means gap-statistic search produced `step` common clusters `[0, 1, 2, 3, 5, 6, 7, 8, 9, 10]` and `nonstep` common clusters `[0, 1, 2, 3, 4, 5]`. Step-to-nonstep centroid matching found `6` valid pair(s), with unmatched step centroids `[4, 7, 8, 9]` and unmatched nonstep centroids `[]`.

Cross-fit showed the following mean differences between across-group and within-group benchmark fits:

| Direction | Pairs | Across mean R² | Across median R² | Within mean R² | Delta mean R² |
| --- | --- | --- | --- | --- | --- |
| step→nonstep | 3816 | 0.330 | 0.427 | 0.351 | -0.021 |
| nonstep→step | 3816 | 0.300 | 0.335 | 0.312 | -0.013 |

At the centroid level, merging or fractionation detection returned:

- `step <- nonstep` centroid merging detections: `0/10`
- `nonstep <- step` centroid merging detections: `4/6`

At the individual-synergy level, the mean MI values were:

- `step <- nonstep`: `0.895`
- `nonstep <- step`: `0.976`

Baseline representative correspondence stayed group-specific:

| Group | Matched pairs | Mean SP | Matched details | Unmatched paper centroids |
| --- | --- | --- | --- | --- |
| Step | 7 | 0.974 | P0↔B5 (0.992), P1↔B3 (0.941), P2↔B6 (0.992), P6↔B2 (0.985), P7↔B1 (0.965), P8↔B4 (0.960), P10↔B0 (0.984) | 3, 5, 9 |
| Nonstep | 5 | 0.967 | P0↔B2 (0.984), P1↔B0 (0.999), P2↔B4 (0.989), P3↔B1 (0.988), P4↔B3 (0.875) | 5 |

## Comparison with Prior Studies

| Comparison Item | Prior Study Result | Current Result | Verdict |
| --- | --- | --- | --- |
| Rank rule | ~6 vs. ~7 synergies at R²≈0.80 | Step median=4.0; Nonstep median=4.0 | Partially consistent |
| Common-cluster rule | >=1/3 subject contribution | Step common=10, Nonstep common=6 | Consistent |
| Centroid matching | Use scalar product with SP<0.8 unmatched | Matched=6, unmatched step=4, unmatched nonstep=0 | Consistent |
| Cross-fit | Across-group fit compared with within-group benchmark | Across-group deltas: step→nonstep=-0.021, nonstep→step=-0.013 | Consistent |
| Developmental/training conclusion | Fractionation in development, merging in training | Current analysis compares perturbation step vs nonstep rather than age/training groups. | Not tested |

## Interpretation & Conclusion

The current perturbation dataset supports a meaningful paper-style re-analysis, but it does not replicate the paper's developmental and training claims directly. Instead, the workflow shows how the repository's `step` and `nonstep` strategies organize their 16-channel perturbation EMG into paper-style synergy structures while preserving the repository's trial windows and selection rules.

The most important take-away is the separation between preserved logic and adapted logic. The preserved logic now includes the `R²`-based rank rule, the paper-aligned plain-k-means gap-statistic search, the subject-invariant cluster definition, scalar-product matching, cross-fit framing, and NNLS-based merging criteria. The adapted logic includes the perturbation-specific trial pool, the 16-channel muscle set, and the fact that the repository starts from post-processed EMG rather than the paper's raw running signals. Users should therefore read the current figures as a structural comparison tool for this repository, not as a literal reproduction of the running-expertise paper.

## Limitations

This analysis does not replay the paper's raw EMG preprocessing and does not compare developmental or training groups. The repository uses a 16-channel perturbation EMG set rather than the paper's 15-muscle running set. The clustering and NMF defaults are paper-aligned within that 16-channel adaptation, but the scientific context remains a perturbation step-vs-nonstep comparison rather than a running-expertise study.

## Reproduction

This checked-in report was generated with explicit runtime overrides for tractable local validation: `--kmeans-restarts 10 --gap-ref-n 5 --gap-ref-restarts 3`. Running the default command uses the paper-aligned counts and may therefore regenerate different artifacts.

Run the dry-run first:

```bash
conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py --dry-run
```

Run the full analysis with the paper-aligned defaults:

```bash
conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py
```

## Figures

| File | Description |
| --- | --- |
| `figures/figure01_rank_sparseness.png` | Paper-style rank distribution and vector sparseness by step class. |
| `figures/global_step_clusters.png` | Paper step common clusters rendered with the same two-column W/H layout as the pipeline. |
| `figures/global_nonstep_clusters.png` | Paper nonstep common clusters rendered with the same two-column W/H layout as the pipeline. |
| `figures/figure03_step_nonstep_matching.png` | Scalar-product heatmap between step and nonstep common centroids. |
| `figures/figure04_baseline_correspondence_step.png` | Paper step common centroids matched against baseline step representatives. |
| `figures/figure04_baseline_correspondence_nonstep.png` | Paper nonstep common centroids matched against baseline nonstep representatives. |
| `figures/figure05_crossfit_mi.png` | Cross-fit generalizability and individual-level MI summary. |
