# First Zero-Duplicate K Rerun

## Research Question

**"`gap statistic`을 쓰지 않고, duplicate trial이 처음 0개가 되는 `K`를 고르면 현재 bundle에서는 몇이 되는가?"**

이 보고서는 main pipeline을 수정하지 않고, existing final parquet bundle만 읽어서 no-gap rerun을 수행한 결과를 정리한다. 핵심 목적은 pipeline이 보고한 gap 기반 `K`와, duplicate burden만 기준으로 다시 찾은 `K`가 어떻게 다른지 분리해서 설명하는 것이다.

## Data Summary

- Source parquet: `outputs/final_concatenated.parquet`
- Target group: `pooled_step_nonstep`
- Analysis date: `2026-03-19`
- Analysis units: `45`
- Pooled vectors: `221`
- Muscles per vector: `16`
- `k_min = 7`, scanned through `K=13`

## Analysis Methodology

- **Analysis input**: main pipeline이 쓴 single parquet bundle에서 `minimal_W`, `metadata`, `final_summary`를 읽는다.
- **Reconstruction rule**: `minimal_W`를 trial별 `W_muscle` matrix로 다시 묶어 pooled clustering vector를 offline으로 재구성한다.
- **Selection rule**: `gap statistic`은 호출하지 않고, `k_min`부터 `K`를 증가시키며 duplicate trial이 처음 0개가 되는 `K`를 선택한다.
- **Duplicate definition**: 같은 trial 안의 component 둘 이상이 같은 cluster label을 받으면 duplicate trial로 센다.
- **Clustering search behavior**: duplicate 판정과 candidate search는 `src/synergy_stats/clustering.py`의 production helper semantics를 그대로 따른다.
- **Coordinate & sign conventions**:
  - Axis & Direction Sign

    | Axis | Positive (+) | Negative (-) | 대표 변수 |
    |------|---------------|---------------|-----------|
    | AP (X) | 해당 없음 | 해당 없음 | 본 분석은 `W` vector clustering만 사용 |
    | ML (Y) | 해당 없음 | 해당 없음 | 본 분석은 `W` vector clustering만 사용 |
    | Vertical (Z) | 해당 없음 | 해당 없음 | 본 분석은 `W` vector clustering만 사용 |

  - Signed Metrics Interpretation

    | Metric | (+) meaning | (-) meaning | 판정 기준/참조 |
    |--------|--------------|--------------|----------------|
    | 해당 없음 | 해당 없음 | 해당 없음 | 본 분석은 signed biomechanical metric을 직접 해석하지 않음 |

  - Joint/Force/Torque Sign Conventions

    | Variable group | (+)/(-) meaning | 추가 규칙 |
    |----------------|------------------|-----------|
    | EMG synergy `W` weights | 부호 해석 없음 | `W_value`는 비음수 가중치이며 cluster 구조 비교에만 사용 |

## Results

### 1. Pipeline metadata 기준선

main pipeline이 이미 기록한 `concatenated` metadata는 다음과 같았다.

| Metric | Value |
|------|------:|
| `pipeline_k_gap_raw` | `15` |
| `pipeline_k_selected` | `15` |
| `pipeline_k_min_unique` | `13` |

이 baseline만 봐도, 현재 bundle에서는 duplicate burden 관점의 최소 feasible `K`와 gap recommendation이 서로 다르다는 점이 드러난다.

### 2. No-gap rerun K scan

offline rerun은 `k_min=7`부터 시작해 duplicate trial 수를 다시 셌다.

| K | Duplicate trials | Zero-duplicate |
|---|-----------------:|----------------|
| `7` | `17` | `No` |
| `8` | `12` | `No` |
| `9` | `6` | `No` |
| `10` | `3` | `No` |
| `11` | `2` | `No` |
| `12` | `1` | `No` |
| `13` | `0` | `Yes` |

따라서 이번 analysis의 최종값은 `k_selected_first_zero_duplicate = 13`이었다.

### 3. Reproducibility check

같은 명령을 `default_run`과 `recheck_run` 두 output dir에 각각 실행했고, 아래 파일의 MD5가 완전히 일치했다.

| File | MD5 |
|------|-----|
| `summary.json` | `ecda7339ca25c388940b8a6eac239086` |
| `k_scan.json` | `a30d401fdab1339e59413668d0d664ca` |
| `k_duplicate_burden.png` | `eaa22f6a9af78bff9dc0867e6f1fad76` |

## Interpretation

이 분석의 해석 단위는 biomechanical sign이 아니라 **duplicate-free cluster feasibility**다. 따라서 가장 중요한 비교는 "pipeline이 gap statistic 때문에 선택한 `K`"와 "gap을 빼면 가장 먼저 feasible한 `K`"의 차이다.

### Summary interpretation

현재 `outputs/final_concatenated.parquet`에서는 no-gap rerun과 pipeline metadata가 같은 결론을 가리킨다. duplicate trial이 처음 0개가 되는 지점은 `K=13`이고, gap statistic이 반영된 pipeline recommendation은 `K=15`다. 다시 말해, pipeline이 `15`를 보고한 것은 "13에서 아직 duplicate가 남아서"가 아니라, **gap statistic이 구조적 추천값으로 15를 먼저 제안했기 때문**이다.

### Conclusion

1. 현재 `concatenated` bundle에서 duplicate-free floor는 `K=13`이다.
2. same bundle의 pipeline gap recommendation은 `K=15`다.
3. 따라서 사용자가 제기한 "`gap statistic`을 빼면 `13`이어야 한다"는 해석은 이 bundle에 대해 재현됐다.

## Reproduction

```bash
conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py --source-parquet outputs/final_concatenated.parquet --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run --overwrite
```

**Input**:
- `outputs/final_concatenated.parquet`

**Output**:
- `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/summary.json`
- `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/k_scan.json`
- `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/checksums.md5`
- `analysis/first_zero_duplicate_k_rerun/artifacts/default_run/k_duplicate_burden.png`
