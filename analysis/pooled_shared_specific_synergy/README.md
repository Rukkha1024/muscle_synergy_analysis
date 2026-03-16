# pooled_shared_specific_synergy

## 왜 이 폴더를 만들었는가

baseline pipeline은 step과 nonstep 조건을 **각각 따로** clustering 한 뒤 cross-group cosine matching으로 synergy 쌍을 비교한다. 이 방식은 두 조건의 cluster space가 서로 다르기 때문에, "같은 cluster 안에서 step과 nonstep의 구조가 실제로 얼마나 비슷한지"를 직접 답하기 어렵다.

이 분석은 그 한계를 보완하기 위해, 두 조건의 trial-level `W` 벡터를 **하나의 공통 cluster space에 풀링**한 뒤 같은 cluster 내부에서 step/nonstep 구성을 직접 비교한다.

## 사용자 목표

같은 `cluster_id` 안에서 아래 네 가지를 직접 비교하는 것이 핵심 목적이다.

1. step member 수 vs nonstep member 수 (occupancy balance)
2. step/nonstep subject coverage (특정 피험자 편중 여부)
3. step sub-centroid와 nonstep sub-centroid의 구조 유사도 (cosine similarity)
4. 같은 cluster 안에서 step 대표 `H`와 nonstep 대표 `H`의 시간 프로파일 차이

## 입력 데이터

| 입력 | 경로 |
| --- | --- |
| 파이프라인 설정 | `configs/global_config.yaml` |
| baseline run | `outputs/runs/default_run` |
| EMG parquet | global config의 `emg_path` 참조 |
| Event workbook | global config의 `event_workbook` 참조 |

## 폴더 구조

```
analysis/pooled_shared_specific_synergy/
  README.md                                  # 이 파일
  analyze_pooled_shared_specific_synergy.py  # 단일 진입점
  report.md                                  # 연구 리포트 (배경·방법론·해석)
  artifacts/<run_name>/                      # 실행 산출물
    report.md                                # artifact-level 결과 리포트
    pooled_cluster_members.csv
    pooled_cluster_summary.csv
    pooled_representative_W.csv
    pooled_representative_H_long.csv
    checksums.md5
    run_metadata.json
    figures/
      pooled_clusters.png
      step_vs_nonstep_W.png
      step_vs_nonstep_H.png
      occupancy_summary.png
      k_selection_diagnostic.png
      subcentroid_similarity_heatmap.png
```

## 실행 방법

작업 디렉터리: repo root

### dry-run (입력 확인만)

```bash
conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
  --config configs/global_config.yaml \
  --baseline-run outputs/runs/default_run \
  --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
  --dry-run
```

### 전체 실행

```bash
conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
  --config configs/global_config.yaml \
  --baseline-run outputs/runs/default_run \
  --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
  --overwrite
```

### practical override (빠른 검증용)

```bash
conda run -n module python analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py \
  --config configs/global_config.yaml \
  --baseline-run outputs/runs/default_run \
  --outdir analysis/pooled_shared_specific_synergy/artifacts/dev_run \
  --overwrite \
  --nmf-backend sklearn_nmf \
  --clustering-algorithm sklearn_kmeans \
  --repeats 40 \
  --gap-ref-n 20 \
  --gap-ref-restarts 10 \
  --uniqueness-candidate-restarts 80
```

## 주요 Figure 설명

| Figure | 설명 |
| --- | --- |
| `pooled_clusters.png` | pooled centroid별 대표 `W`(bar)와 `H`(time series)를 한눈에 보여준다. 공통 cluster vocabulary 파악용. |
| `step_vs_nonstep_W.png` | 같은 cluster 안에서 step-only / nonstep-only sub-centroid `W`를 나란히 비교한다. 각 subplot 제목의 **cosine** 값은 해당 cluster 내 step member들의 `W` 평균(step sub-centroid)과 nonstep member들의 `W` 평균(nonstep sub-centroid) 사이의 cosine similarity다. 1.0에 가까우면 두 조건의 근육 조성이 거의 동일하고, 낮아질수록 조건 간 `W` 구조 차이가 크다. |
| `step_vs_nonstep_H.png` | 같은 cluster 안에서 step / nonstep 대표 activation `H`를 겹쳐 그린다. `W`가 유사해도 시간 프로파일(타이밍·크기)이 다른 경우를 확인할 수 있다. |
| `occupancy_summary.png` | cluster별 raw member count와 subject-normalized occupancy를 분리 표시한다. 특정 피험자가 cluster를 과도 점유하는 편향을 식별할 수 있다. |
| `k_selection_diagnostic.png` | gap statistic 추천값과 zero-duplicate feasibility rule이 최종 `K`를 어떻게 결정했는지 보여준다. |
| `subcentroid_similarity_heatmap.png` | step sub-centroid와 nonstep sub-centroid 간 cross-cluster cosine similarity를 heatmap으로 요약한다. 대각선(same cluster) 및 비대각선(cross cluster) 매칭을 한눈에 확인할 수 있다. |

## 해석 메모

이 분석은 **pipeline 대체가 아니라 analysis-only validation/interpretation layer**다. baseline output을 덮어쓰지 않으며, 결과 해석도 항상 `outputs/runs/default_run/`과 분리해서 본다.
