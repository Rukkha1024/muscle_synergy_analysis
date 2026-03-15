# <Analysis Title>

## Research Question

**"<core question in quotes>"**

<Upper context: why this analysis is needed, what prompted it. 1-2 sentences.>

## Prior Studies

> Methodology, results, and conclusions of the prior studies this analysis follows.

### <Author et al. (Year)> — <short title>

- **Methodology**: <model, variables, analysis approach>
- **Experimental design**: <N subjects, equipment, protocol summary>
- **Key results**: <specific numbers, e.g., "r ≈ 0.54", "eBoS ≈ 30% of static BoS">
- **Conclusions**: <authors' main takeaway, 1-2 sentences>

### <Author et al. (Year)> — <short title>

- **Methodology**: ...
- **Experimental design**: ...
- **Key results**: ...
- **Conclusions**: ...

## Methodological Adaptation

> How this analysis maps to the prior studies' methods. Deviations are explicitly justified.

| Prior Study Method | Current Implementation | Deviation Rationale |
|---|---|---|
| <method 1> | <Replicated / Conceptually adopted / Not implemented> | <equipment constraint, missing parameter, etc.> |
| <method 2> | ... | ... |
| <statistical approach> | ... | ... |

**Summary**: This analysis adopts <aspect> from <study> but modifies <aspect> because <reason>.

## Data Summary

- **N trials** (step=X, nonstep=Y)
- Data source: ...
- Trial classification: ...
- Key variables: <list>

## Analysis Methodology

- **Analysis window**: ...
- **Statistical model**: ...
- **Multiple comparison correction**: ...
- **Significance reporting**: `p < 0.05` 기준(`alpha=0.05`), `Sig` only (significant = `< 0.05`, non-significant = `n.s.`), hide numeric `p` and `df` in user-facing tables
- **Peak definition**: `*_peak` uses `abs_peak = max(|x|)` within the analysis window
- **Variable definitions**: ...
- **Special handling**: ...

---

## Results

### 1. <First result>

| Variable | Estimate | SE | t | Sig |
|----------|----------|----|---|-----|
| ... | ... | ... | ... | ... |

### 2. <Second result>

...

---

## Comparison with Prior Studies

> Direct comparison of prior study findings against current results.

| Comparison Item | Prior Study Result | Current Result | Verdict |
|---|---|---|---|
| <item 1> | <number/conclusion> | <number/conclusion> | Consistent / Partially consistent / Inconsistent / Not tested |
| <item 2> | ... | ... | ... |

<For any Inconsistent or Not tested items, explain possible reasons.>

## Interpretation & Conclusion

1. **Key finding 1** — <include relationship to prior study>
2. **Key finding 2**
3. **Key finding 3**

## Limitations

1. ...
2. ...
3. ...

---

## Reproduction

```bash
conda run --no-capture-output -n module python analysis/<topic>/analyze_<topic>.py
```

**Input**: ...
**Output**: fig1–figN PNG (generated in this folder)

## Figures

| File | Description |
|------|-------------|
| fig1_xxx.png | ... |
| fig2_xxx.png | ... |
