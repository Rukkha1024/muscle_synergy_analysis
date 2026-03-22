# First Zero-Duplicate K Rerun

## Research Question

**"`subject+velocity` paired filter가 main pipeline에 이미 적용된 뒤, paired-only bundle에서는 duplicate trial이 처음 0개가 되는 `K`가 몇이며, cluster presence 기준 step/nonstep paired 통계는 어떻게 보이는가?"**

이 보고서는 현재 paired-only final parquet를 기준으로, `K` 선택 결과와 paired cluster presence 통계 해석만 간결하게 정리한다. 실행 방법, 산출물 경로, workbook 여는 법은 [README.md](/home/alice/workspace/26-03-synergy-analysis/analysis/first_zero_duplicate_k_rerun/README.md)에 둔다.

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

## Minimal Method

- source parquet는 main pipeline이 이미 paired gate를 적용한 `outputs/final_concatenated.parquet`다.
- `gap statistic`은 다시 쓰지 않고, duplicate trial이 처음 0개가 되는 `K`를 선택한다.
- cluster presence는 `both_present`, `step_only`, `nonstep_only`, `both_absent`로 요약하고, discordant pair에 대해 exact McNemar와 BH 보정을 적용한다.

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

### Note: 통계 검정의 한계

1. **Power 부족 문제.** n=21 paired key로 13개 cluster를 동시 검정(BH 보정)하면, 유의성 달성에 필요한 raw p ≈ 0.004이다. McNemar exact test로 이 수준을 충족하려면 discordant pair 9–10개 이상이 전부 한 방향이어야 하며, 총 pair 21개에서 이 조건을 달성하는 것은 사실상 불가능하다.
2. **결과 해석.** 위 통계 결과의 "유의한 cluster 없음"은 "차이가 없다"가 아니라 "이 표본 규모로는 어떤 차이도 검출할 power가 없다"로 읽어야 한다.
3. **결정 사항.** paired cluster presence에 대한 formal statistical test(McNemar + BH)는 현재 표본 규모에서 무의미하므로, 논문 보고 시에는 적용하지 않는다. Presence rate 차이는 descriptive finding으로만 기술한다.
