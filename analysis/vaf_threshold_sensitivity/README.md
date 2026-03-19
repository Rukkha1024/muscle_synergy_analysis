# vaf_threshold_sensitivity

VAF 기준값(85~95%)을 바꿔 보며 시너지 수와 클러스터 K가 어떻게 달라지는지 확인하는 민감도 분석입니다.

---

## 배경지식

이 분석에서 사용하는 핵심 개념을 먼저 간단히 설명합니다. 처음 접하는 분도 아래 설명을 읽으면 결과 표를 이해할 수 있습니다.

### 1. EMG 시너지 (Muscle Synergy)

사람이 움직일 때 여러 근육이 **함께** 활성화됩니다. 이렇게 함께 움직이는 근육 묶음을 *시너지*라고 합니다. 예를 들어 "걸을 때 허벅지 앞쪽과 종아리 뒤쪽이 동시에 켜지는 패턴"이 하나의 시너지입니다.

### 2. NMF (Non-negative Matrix Factorization)

오케스트라 전체 소리가 녹음된 음원에서 바이올린·첼로·플루트 소리를 각각 분리해 내는 기법에 비유할 수 있습니다. NMF는 근전도(EMG) 전체 신호를 여러 시너지로 분해합니다. NMF의 결과는 항상 0 이상의 값이므로, 근육 활성화처럼 "음수가 없는" 데이터에 적합합니다.

### 3. VAF (Variance Accounted For, 설명 분산 비율)

NMF로 분리한 시너지를 다시 합쳤을 때 원래 신호를 얼마나 잘 재현하는지를 나타내는 비율입니다. 100%에 가까울수록 원래 신호를 거의 완벽하게 재현한 것입니다. 예를 들어 VAF = 90%라면 "원래 신호 변동의 90%를 시너지만으로 설명할 수 있다"는 뜻입니다.

### 4. 시너지 수 (Rank)

하나의 시험(trial)에서 NMF가 찾아낸 시너지의 개수입니다. VAF 기준값을 높이면 더 정밀한 재현을 요구하므로 시너지 수가 늘어납니다. 이 분석에서는 1부터 최대 8개까지 시도합니다.

### 5. Pooled Clustering & K

개별 시험마다 추출한 시너지를 한데 모아(*pooled*) k-means 알고리즘으로 유사한 시너지끼리 묶는 과정입니다. K는 "몇 개의 묶음(클러스터)으로 나눌 것인가"를 뜻합니다. 유치원에서 색깔별로 크레파스를 바구니에 나누는 것에 비유할 수 있습니다. K가 너무 크면 비슷한 시너지도 따로 분류되고, 너무 작으면 서로 다른 시너지가 하나로 합쳐집니다.

### 6. Gap Statistic

클러스터 수 K를 자동으로 결정하는 통계적 방법입니다. 실제 데이터의 클러스터링 품질과 무작위 데이터의 클러스터링 품질을 비교해서, 실제 데이터에 의미 있는 구조가 있는 K를 찾습니다. 이 분석에서는 gap statistic이 제시한 K(`k_gap_raw`)에 중복 시너지가 있으면 중복이 사라질 때까지 K를 올립니다. 이렇게 최종 선택된 K가 `k_selected`입니다.

### 7. Trialwise vs. Concatenated

EMG 시너지를 추출하는 두 가지 방식입니다.

- **Trialwise**: 각 시험(trial)을 독립적으로 분석합니다. 125개 시험이 있으면 125번 NMF를 실행합니다. 개별 시험의 특성을 잘 반영하지만, 시험마다 시너지 수가 다를 수 있습니다.
- **Concatenated**: 같은 사람·같은 속도·같은 반응 유형의 시험을 하나로 이어 붙인 뒤(*concatenated*) NMF를 실행합니다. 45개 분석 단위(subject × velocity × step_class)로 줄어들며, 각 단위 안에서 시너지가 더 안정적으로 추출됩니다.

---

## 이 분석의 목표

현재 메인 파이프라인은 VAF 기준값으로 **90%**를 사용합니다. 그런데 왜 89%나 91%가 아니라 90%일까요? 이 분석은 그 질문에 답하기 위해 만들어졌습니다.

구체적으로 다음을 확인합니다.

- VAF 기준값을 `85%`부터 `95%`까지 `1%` 단위로 바꿨을 때, 시너지 수와 pooled K가 어떻게 달라지는지 관찰합니다.
- 결과는 `trialwise`와 `concatenated` 두 mode 모두에서 비교합니다.
- trial selection과 clustering은 **메인 파이프라인의 로직을 그대로 재사용**하고, NMF 역시 같은 rank fitting / VAF 계산 규칙을 캐시 기반으로 재사용합니다.
- 계산 시간을 줄이기 위해 clustering restart 수만 선택적으로 낮춘 screening profile로 broad sweep을 먼저 수행하고, 필요한 구간은 별도 out-dir로 정밀 rerun할 수 있습니다.

---

## 입력 데이터

| 파일 | 설명 |
|------|------|
| `configs/global_config.yaml` | 프로젝트 전체 설정. 아래 두 경로를 포함합니다 |
| `configs/synergy_stats_config.yaml` | NMF 및 clustering 관련 파라미터의 source of truth |
| `input.emg_parquet_path` (global_config 내부) | min-max 정규화된 EMG 데이터 (parquet 형식) |
| `input.event_xlsm_path` (global_config 내부) | 이벤트 메타데이터. 각 시험의 step/nonstep 분류 정보 포함 |

---

## 분석이 동작하는 방식

분석은 다음 순서로 진행됩니다.

1. **시험 선택**: 메인 파이프라인과 동일하게 `load_event_metadata()` → `merge_event_metadata()` → `build_trial_records()` 경로를 거쳐 분석 대상 시험을 선택합니다.

2. **NMF 실행 (trialwise)**: 각 시험에 대해 1~8개 rank를 모두 한 번씩 fit합니다. 이후 threshold별로 "처음 기준을 만족하는 최소 rank"를 선택합니다. 한 번 fit한 결과를 캐시에 저장하므로, threshold를 바꿀 때 NMF를 다시 계산하지 않아도 됩니다.

3. **NMF 실행 (concatenated)**: 같은 사람·같은 속도·같은 step 분류의 시험을 하나로 이어 붙인 super-trial을 만들어 fit한 뒤, 원래 시험 단위의 activation profile을 다시 분리합니다. 비유하자면, 여러 장의 사진을 파노라마로 합쳐서 분석한 뒤 각 사진으로 다시 나누는 것과 같습니다.

4. **Pooled clustering**: 각 mode에서 추출한 모든 시너지를 step과 nonstep 구분 없이 하나의 공간에 모은 뒤 `cluster_feature_group()`을 호출합니다.

5. **K 선택**: 메인 파이프라인과 동일하게 `gap statistic + zero-duplicate feasibility` 규칙을 따릅니다. gap statistic이 제시한 K에서 중복 시너지가 발견되면, 중복이 사라질 때까지 K를 올립니다.

---

## 실행 방법

### 1단계: Dry-run (설정 확인)

실제 분석 없이 설정과 데이터 로딩만 확인합니다. "이 설정으로 정말 돌릴 건지" 미리 점검하는 용도입니다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --dry-run
```

### 2단계: Screening profile (빠른 탐색)

clustering restart 수를 줄여서 85~95% 전 구간을 빠르게 탐색합니다. `report.md`의 broad sweep 숫자가 이 command로 재현됩니다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
  --cluster-repeats 100 \
  --gap-ref-n 100 \
  --gap-ref-restarts 20 \
  --uniqueness-candidate-restarts 100
```

### 3단계: Exact profile (정밀 rerun)

같은 분석을 default clustering 설정(restart 수가 더 큼)으로 수행합니다. screening보다 정확하지만 시간이 오래 걸립니다. restart 수 차이로 인해 screening과 숫자가 완전히 같지 않을 수 있습니다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py
```

### 선택: 특정 구간 정밀 분석

관심 구간(예: 89~91%)만 별도 출력 폴더에 정밀 rerun할 수 있습니다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
  --thresholds 0.89 0.90 0.91 \
  --out-dir analysis/vaf_threshold_sensitivity/artifacts/exact_89_91
```

---

## 산출물

| 파일 | 설명 | 언제 확인하나 |
|------|------|--------------|
| `report.md` | 사용자용 요약 리포트. 표·해석·결론 포함 | 분석 결과를 읽을 때 가장 먼저 |
| `artifacts/default_run/summary.json` | broad sweep 전체 결과를 구조화한 JSON | 프로그래밍으로 결과를 재활용할 때 |
| `artifacts/default_run/by_threshold/vaf_XX/summary.json` | 각 threshold별 상세 결과 JSON (XX = 85~95) | 특정 threshold만 깊이 볼 때 |
| `artifacts/default_run/checksums.md5` | broad sweep 산출물의 MD5 체크섬 | 재현성 검증할 때 |
| `artifacts/exact_89_91/` | 89~91% 주변 정밀 rerun 결과 저장 폴더 (선택) | 정밀 비교가 필요할 때 |

각 `summary.json`에는 `run_metadata`가 포함되어 있습니다. 여기에는 clustering restart override 사용 여부와 base/effective 설정값이 기록되어 있어, 어떤 설정으로 실행했는지 추적할 수 있습니다.
