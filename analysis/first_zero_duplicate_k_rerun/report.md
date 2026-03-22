# First Zero-Duplicate K Rerun

## Research Question

**"`subject+velocity` paired filter가 main pipeline에 이미 적용된 뒤, paired-only bundle에서는 duplicate trial이 처음 0개가 되는 `K`가 몇이며, cluster presence 기준 step/nonstep paired 통계는 어떻게 보이는가?"**

이 보고서는 더 이상 raw event filtering을 analysis 폴더에서 다시 계산하지 않는다. 현재 source of truth는 main pipeline이 만든 paired-only `final_concatenated.parquet`이며, 이 analysis는 그 final parquet만 읽어 no-gap reclustering과 paired exact McNemar 통계를 다시 계산한다. 핵심 목적은 pipeline이 선택한 gap 기반 `K`와, duplicate burden만 기준으로 다시 찾은 `K`, 그리고 paired cluster presence 해석을 한 문서에서 함께 정리하는 것이다.

## Data Summary

- Source parquet: `outputs/final_concatenated.parquet`
- Target group: `pooled_step_nonstep`
- Analysis date: `2026-03-22`
- Analysis output dir: `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering`
- Paired keys: `21`
- Excluded pair keys inside source bundle: `0`
- Analysis units: `42`
- Pooled vectors: `212`
- Muscles per vector: `16`
- `k_min = 8`, first zero-duplicate at `K=13`

## Analysis Methodology

- **Analysis input**: main pipeline이 쓴 paired-only single parquet bundle에서 `trial_windows`, `source_trial_windows`, `minimal_W`, `minimal_H_long`, `metadata`, `final_summary`를 읽는다.
- **Pipeline selection contract**: 현재 source parquet의 `analysis_selected_group`는 기존 mixed comparison prefilter에 더해 `(subject, velocity)` 기준 paired gate까지 통과한 최종 selected set이다. `analysis_selected_group_prepaired`, `analysis_pair_key`, `analysis_is_paired_key`, `analysis_pair_status`는 이 최종 판단의 audit column이다.
- **Reconstruction rule**: `minimal_W`를 analysis unit별 `W_muscle` matrix로 다시 묶어 pooled clustering vector를 offline으로 재구성한다.
- **Selection rule**: `gap statistic`은 호출하지 않고, `k_min`부터 `K`를 증가시키며 duplicate trial이 처음 0개가 되는 `K`를 선택한다.
- **Duplicate definition**: 같은 analysis unit 안의 component 둘 이상이 같은 cluster label을 받으면 duplicate trial로 센다.
- **Paired statistics rule**: 각 cluster와 각 paired key의 관계를 `both_present`, `step_only`, `nonstep_only`, `both_absent`로 표기하고, discordant pair(`step_only`, `nonstep_only`)를 기준으로 exact McNemar p-value를 계산한 뒤 Benjamini-Hochberg 보정을 적용한다.
- **Reviewer-facing outputs**: paired 통계는 `paired_cluster_stats.csv`, `paired_cluster_detail.csv`, `paired_cluster_statistics.xlsx`에 저장하고, workbook은 `summary`, `cluster_stats`, `paired_detail`, `table_guide` 네 시트로 검증한다.
- **Coordinate & sign conventions**:
  - Axis & Direction Sign

    | Axis | Positive (+) | Negative (-) | 대표 변수 |
    |------|---------------|---------------|-----------|
    | AP (X) | 해당 없음 | 해당 없음 | 본 분석은 `W` vector clustering과 cluster presence만 사용 |
    | ML (Y) | 해당 없음 | 해당 없음 | 본 분석은 `W` vector clustering과 cluster presence만 사용 |
    | Vertical (Z) | 해당 없음 | 해당 없음 | 본 분석은 `W` vector clustering과 cluster presence만 사용 |

  - Signed Metrics Interpretation

    | Metric | (+) meaning | (-) meaning | 판정 기준/참조 |
    |--------|--------------|--------------|----------------|
    | `presence_rate_diff_step_minus_nonstep` | step presence rate가 더 높음 | nonstep presence rate가 더 높음 | paired cluster stats summary |

  - Joint/Force/Torque Sign Conventions

    | Variable group | (+)/(-) meaning | 추가 규칙 |
    |----------------|------------------|-----------|
    | EMG synergy `W` weights | 부호 해석 없음 | `W_value`는 비음수 가중치이며 cluster 구조 비교에만 사용 |

## Results

### 1. Pipeline paired filter가 반영된 source bundle

현재 analysis는 pipeline이 이미 paired gate를 적용한 `outputs/final_concatenated.parquet`를 직접 읽는다. 따라서 source bundle 자체가 paired-only 분석 단위다.

| Metric | Value |
|------|------:|
| `pipeline_k_gap_raw` | `16` |
| `pipeline_k_selected` | `16` |
| `pipeline_k_min_unique` | `13` |
| `paired_key_n` | `21` |
| `excluded_pair_key_n` | `0` |
| `analysis_unit_n_postpaired` | `42` |
| `vector_count` | `212` |

즉, 현재 source parquet 안에는 이미 paired 조건을 만족한 analysis unit만 남아 있으며, paired analysis는 이 확정된 bundle을 다시 해석하는 단계다.

### 2. No-gap rerun K scan

paired-only rerun은 `k_min=8`부터 시작해 duplicate trial 수를 다시 셌다.

| K | Duplicate trials | Zero-duplicate |
|---|-----------------:|----------------|
| `8` | `7` | `No` |
| `9` | `6` | `No` |
| `10` | `4` | `No` |
| `11` | `2` | `No` |
| `12` | `1` | `No` |
| `13` | `0` | `Yes` |

따라서 이번 analysis의 최종값은 `k_selected_first_zero_duplicate = 13`이었다. 현재 bundle에서는 pipeline recommendation `K=16`보다 smaller feasible floor `K=13`이 먼저 존재한다.

### 3. Paired cluster statistics

paired cluster statistics는 `13`개 cluster와 `21`개 paired key의 완전 그리드로 계산됐다. 따라서 `paired_cluster_detail.csv`는 총 `273 = 13 x 21`행을 가지며, 각 행은 “한 cluster x 한 paired key”의 presence evidence를 뜻한다.

| Metric | Value |
|------|------:|
| Tested clusters | `13` |
| Detail rows | `273` |
| BH-adjusted `q < 0.05` clusters | `0` |
| Smallest raw `p` cluster | `cluster_id = 10` |
| Smallest raw `p` | `0.03125` |
| Smallest BH-adjusted `q` | `0.40625` |
| `shared_candidate` clusters | `10` |
| `uncertain_not_significant` clusters | `3` |
| `strategy_biased` clusters | `0` |

즉, raw p-value만 보면 일부 cluster에서 step/nonstep presence 차이가 더 커 보이는 지점이 있지만, BH 보정 이후 reviewer-facing 기준에서 유의한 `strategy_biased` cluster는 남지 않았다. 현재 paired interpretation은 "몇몇 cluster가 step 또는 nonstep에 더 자주 나타날 수는 있으나, 이 source bundle만으로는 보정 후 유의한 전략 편향을 주장하기 어렵다"로 정리하는 편이 안전하다.

### 4. 어디를 열어 보면 되는가

이번 paired rerun의 핵심 산출물은 아래 위치에 있다.

| Output | Path |
|------|------|
| Paired summary JSON | `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/summary.json` |
| Paired stats CSV | `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_stats.csv` |
| Paired detail CSV | `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_detail.csv` |
| Paired workbook | `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_statistics.xlsx` |
| No-gap rerun parquet | `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/final_concatenated.parquet` |

가장 먼저 열어볼 파일은 `paired_cluster_statistics.xlsx`다. `summary` 시트에서 paired subset 규모와 `K=13` 선택 결과를 확인하고, `cluster_stats` 시트에서 cluster별 `mcnemar_p`, `mcnemar_q_bh`, `interpretation_label`을 읽는다. 특정 cluster가 어떤 paired key에서 `step_only`, `nonstep_only`, `both_absent`였는지를 보고 싶으면 `paired_detail` 시트를 열면 된다.

### 5. Reproducibility check

같은 source parquet에 대해 paired analysis를 두 번 반복 실행했을 때, 아래 artifact는 byte-level로 일치했다.

| File class | Verification result |
|------|------|
| `summary.json`, `k_scan.json` | 동일 |
| `paired_subset_manifest.csv`, `excluded_nonpaired_manifest.csv` | 동일 |
| `paired_cluster_stats.csv`, `paired_cluster_detail.csv` | 동일 |
| `final.parquet`, `final_concatenated.parquet` | 동일 |
| PNG figures | 동일 |
| `analysis_methods_manifest.json` | 동일 |

반면 `.xlsx` workbook은 sheet 구조와 내용은 같았지만 MD5 equality는 강제하지 않았다. `openpyxl`이 workbook metadata를 다시 쓰기 때문에, 현재는 **내용 재현성은 workbook reopen validation으로 확인하고, byte-level 재현성은 non-`.xlsx` artifact에 대해서만 확인**한다.

## Interpretation

이 분석의 해석 단위는 biomechanical sign이 아니라 **paired subset 안에서의 duplicate-free cluster feasibility와 cluster presence asymmetry**다. 따라서 가장 중요한 비교는 "pipeline이 gap statistic 때문에 선택한 `K`"와 "gap을 빼면 가장 먼저 feasible한 `K`", 그리고 "paired cluster presence 차이가 보정 후에도 남는가"의 세 가지다.

### Summary interpretation

현재 paired-only source bundle에서 no-gap rerun의 first zero-duplicate 해는 `K=13`이다. 반면 main pipeline은 gap recommendation을 반영해 `K=16`을 선택했다. 다시 말해, 현재 pipeline이 `16`을 보고하는 이유는 duplicate-free floor가 16이기 때문이 아니라, **paired subset에서도 gap statistic이 더 큰 구조적 추천값을 먼저 제안하기 때문**이다.

paired exact McNemar 결과를 함께 보면, cluster별 raw discordance는 존재하지만 BH 보정 후 `q < 0.05`에 도달한 cluster는 없다. 따라서 현재 evidence는 "paired subset에서도 `K=13`이 first zero-duplicate floor로 재현된다"까지는 강하게 말할 수 있지만, "**특정 cluster가 step 전략 또는 nonstep 전략에 유의하게 편향된다**"까지는 현재 bundle만으로 확정하기 어렵다.

### Conclusion

1. 현재 paired-only `concatenated` bundle에서 first zero-duplicate floor는 `K=13`이다.
2. 같은 bundle의 pipeline gap recommendation은 `K=16`이다.
3. paired cluster presence exact McNemar + BH 결과에서는 유의한 `strategy_biased` cluster가 남지 않았다.
4. reviewer는 `paired_cluster_statistics.xlsx`를 열어 cluster-level 통계와 paired detail evidence를 바로 확인할 수 있다.

## Reproduction

```bash
conda run --no-capture-output -n cuda python main.py --config configs/global_config.yaml --out outputs/paired_refilter_pipeline --overwrite

conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_paired_refilter_reclustering.py --source-parquet outputs/final_concatenated.parquet --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering --overwrite
```

**Input**:
- `outputs/final_concatenated.parquet`

**Output**:
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/final.parquet`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/final_concatenated.parquet`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/analysis_methods_manifest.json`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_subset_manifest.csv`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/excluded_nonpaired_manifest.csv`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_stats.csv`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_detail.csv`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/paired_cluster_statistics.xlsx`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/summary.json`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/k_scan.json`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/checksums.md5`
- `analysis/first_zero_duplicate_k_rerun/artifacts/paired_refilter_reclustering/k_duplicate_burden.png`
