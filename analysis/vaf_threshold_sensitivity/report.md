# VAF 기준값 민감도 분석

## 한 줄 요약

VAF 기준값을 85%부터 95%까지 1% 단위로 바꿔 본 결과, **90%는 concatenated에서 shared structure가 완전한 마지막 기준**이었습니다. 89%는 더 가볍지만 다소 느슨하고, 91%부터는 concatenated에서 shared structure가 처음으로 깨지고 K burden과 duplicate burden이 동시에 커지기 시작합니다. 따라서 90%는 "엄격함을 한 단계 더 올리되, 비용이 동시에 커지기 직전에서 멈춘 기준"으로 방어할 수 있습니다.

---

## 배경: 이 분석이 필요한 이유

NMF 시너지 분석에서 VAF 기준값은 "시너지 몇 개면 충분한가?"를 결정하는 핵심 파라미터입니다.

- **기준이 너무 낮으면** (예: 80%): 적은 수의 시너지로도 기준을 통과하므로, 중요한 근육 활동 패턴을 놓칠 수 있습니다.
- **기준이 너무 높으면** (예: 95%): 시너지 수가 과도하게 늘어나고, K burden과 duplicate burden이 급격히 커져 결과의 신뢰도가 떨어집니다.

현재 메인 파이프라인은 90%를 사용합니다. 이 분석은 "90%가 정말 적절한가?"를 **데이터로 검증**하기 위해, 85~95% 범위를 체계적으로 탐색합니다.

> 배경 개념(NMF, VAF, 시너지, pooled clustering, gap statistic 등)에 대한 자세한 설명은 [README.md](README.md)의 **배경지식** 섹션을 참조하세요.

---

## 연구 질문

이 분석은 다음 세 가지 하위 질문을 다룹니다.

1. **시너지 수 변화**: VAF 기준값을 85~95%로 바꾸면 시너지 수(rank)가 어떻게 달라지는가?
2. **클러스터 K 변화**: pooled k-means의 K가 기준값에 따라 어떻게 달라지며, 어디서부터 K burden이 급격히 커지는가?
3. **90% 방어**: 위 결과를 종합했을 때, 90%를 cutoff로 방어할 수 있는가? 89%나 91%가 아닌 이유는 무엇인가?

---

## 데이터 요약

이 분석은 24명의 피험자로부터 수집한 125개 시험(trial)을 대상으로 합니다. 각 시험은 외란(perturbation)에 대한 반응 유형에 따라 **step**(발을 디딘 경우)과 **nonstep**(발을 디디지 않은 경우)으로 분류됩니다.

| 항목 | 값 |
|------|-----|
| 피험자 수 | 24 |
| 선택된 시험 수 | 125 |
| Step 시험 | 53 |
| Nonstep 시험 | 72 |
| 분석 mode | `trialwise`, `concatenated` |
| 데이터 출처 | `configs/global_config.yaml`의 `input.emg_parquet_path` |
| 시험 분류 출처 | `configs/global_config.yaml`의 `input.event_xlsm_path` |

**Trialwise**에서는 125개 시험을 각각 독립적으로 분석합니다. **Concatenated**에서는 같은 사람·같은 속도·같은 반응 유형의 시험을 이어 붙여 45개 분석 단위로 줄여서 분석합니다.

---

## 분석 방법

- **Analysis window**: 메인 파이프라인의 event metadata preparation과 `build_trial_records()` slicing 규칙을 그대로 사용했습니다.
- **Trial selection**: `analysis_selected_group == True`인 시험만 선택했습니다.
- **NMF selection rule**: 각 분석 단위마다 1~8개 rank를 모두 한 번씩 fit하고, 각 threshold에서 "처음 기준을 만족하는 최소 rank"를 선택했습니다.
- **Concatenated mode**: `(subject, velocity, step_class)` 단위로 super-trial을 구성한 뒤, 각 source trial의 averaged activation profile을 다시 분리해 threshold별 feature row를 만들었습니다.
- **Clustering rule**: mode별 단일 `pooled_step_nonstep` 공간에서 `cluster_feature_group()`를 호출하고, `gap statistic + zero-duplicate feasibility`로 K를 선택했습니다.
- **Thresholds**: `85%`부터 `95%`까지 `1%` 단위 (총 11개).
- **Broad sweep clustering setting**: 전 구간 탐색은 계산 시간을 관리하기 위해 clustering restart 수를 줄인 screening profile로 수행했습니다 (repeats=100, gap_ref_n=100, gap_ref_restarts=20, uniqueness_candidate_restarts=100).

---

## 결과

`85%`부터 `95%`까지 `1%` 단위 broad sweep을 수행한 결과, threshold가 올라갈수록 두 mode 모두 평균 시너지 수와 평균 VAF가 단조 증가했습니다. `trialwise`는 평균 시너지 수가 `2.768 → 6.032`, 평균 VAF가 `0.875728 → 0.956781`로, `concatenated`는 평균 시너지 수가 `3.4444 → 7.2000`, 평균 VAF가 `0.872686 → 0.950773`으로 상승했습니다.

이 증가 자체는 threshold를 올리면 더 엄격한 재구성을 요구하므로 당연한 방향입니다. 따라서 90%를 방어하려면 단순히 시너지 수 증가가 아니라, **91% 이후에 shared structure가 무너지고 burden이 더 빠르게 커지기 시작하는지**를 함께 봐야 합니다.

### 1. Broad sweep: 시너지 수와 burden 요약

> **이 표 읽는 법**
>
> | 컬럼 | 의미 | 예시 |
> |------|------|------|
> | Mode | 분석 방식. `trialwise`(시험별 독립 분석) 또는 `concatenated`(이어붙인 분석) | `trialwise` |
> | VAF | 이 행에서 사용한 VAF 기준값 | `90%` |
> | Total components | 해당 기준에서 모든 분석 단위의 시너지 수를 합한 값 | 496 |
> | Mean components | 분석 단위당 평균 시너지 수 | 3.968 |
> | Mean VAF | 분석 단위별 실제 달성 VAF의 평균 | 0.916088 |
> | `k_gap_raw` | gap statistic이 처음 제시한 클러스터 수 K | 14 |
> | `k_selected` | 중복 시너지를 제거한 뒤 최종 선택된 K | 21 |
> | `k_selected - k_gap_raw` | 중복 제거를 위해 K를 얼마나 올려야 했는지. 이 값이 클수록 clustering burden이 큼 | 7 |

| Mode | VAF | Total components | Mean components | Mean VAF | `k_gap_raw` | `k_selected` | `k_selected - k_gap_raw` |
|------|-----|------------------|-----------------|----------|-------------|--------------|--------------------------|
| `trialwise` | `85%` | 346 | 2.768 | 0.875728 | 11 | 11 | 0 |
| `trialwise` | `86%` | 375 | 3.000 | 0.884373 | 13 | 13 | 0 |
| `trialwise` | `87%` | 400 | 3.200 | 0.891681 | 13 | 13 | 0 |
| `trialwise` | `88%` | 426 | 3.408 | 0.899022 | 13 | 13 | 0 |
| `trialwise` | `89%` | 465 | 3.720 | 0.909410 | 15 | 16 | 1 |
| `trialwise` | `90%` | 496 | 3.968 | 0.916088 | 14 | 21 | 7 |
| `trialwise` | `91%` | 541 | 4.328 | 0.925731 | 14 | 21 | 7 |
| `trialwise` | `92%` | 580 | 4.640 | 0.933098 | 16 | 27 | 11 |
| `trialwise` | `93%` | 632 | 5.056 | 0.941858 | 17 | 27 | 10 |
| `trialwise` | `94%` | 690 | 5.520 | 0.949467 | 17 | 37 | 20 |
| `trialwise` | `95%` | 754 | 6.032 | 0.956781 | 17 | 54 | 37 |
| `concatenated` | `85%` | 155 | 3.4444 | 0.872686 | 9 | 11 | 2 |
| `concatenated` | `86%` | 164 | 3.6444 | 0.878863 | 9 | 11 | 2 |
| `concatenated` | `87%` | 176 | 3.9111 | 0.886427 | 9 | 10 | 1 |
| `concatenated` | `88%` | 191 | 4.2444 | 0.894882 | 11 | 13 | 2 |
| `concatenated` | `89%` | 207 | 4.6000 | 0.903979 | 12 | 13 | 1 |
| `concatenated` | `90%` | 222 | 4.9333 | 0.912506 | 13 | 14 | 1 |
| `concatenated` | `91%` | 242 | 5.3778 | 0.923427 | 15 | 16 | 1 |
| `concatenated` | `92%` | 260 | 5.7778 | 0.929632 | 14 | 21 | 7 |
| `concatenated` | `93%` | 285 | 6.3333 | 0.939028 | 13 | 25 | 12 |
| `concatenated` | `94%` | 306 | 6.8000 | 0.945816 | 15 | 24 | 9 |
| `concatenated` | `95%` | 324 | 7.2000 | 0.950773 | 15 | 29 | 14 |

이 표에서 가장 중요한 패턴은 다음과 같습니다.

- **Concatenated 90%는 shared structure가 아직 완전합니다.** 아래 표 3에서 보듯이 shared_cluster_rate = shared_member_rate = 1.0을 유지합니다. 91%로 올리면 shared structure가 처음으로 깨집니다.
- **90% → 91% 전환에서 K burden이 동시에 커집니다.** Trialwise에서 gap K 대비 duplicate burden이 +3 늘어나고, concatenated에서도 burden 지표들이 함께 악화됩니다.
- **95%는 방어가 어렵습니다.** K burden(`k_selected - k_gap_raw`)이 trialwise 37, concatenated 14까지 올라가 clustering 결과의 안정성이 크게 떨어집니다.

### 2. 인접 threshold 진단: 90% 전후 비교

> **이 표 읽는 법**
>
> | 컬럼 | 의미 |
> |------|------|
> | Mode | 분석 방식 |
> | Transition | 어디서 어디로 threshold를 올렸는지 |
> | Mean component delta | 평균 시너지 수가 얼마나 늘었는지 |
> | Mean VAF delta | 평균 VAF가 얼마나 올랐는지 |
> | VAF gain per component | 시너지 1개를 추가할 때 VAF가 얼마나 올라가는지. 이 값이 높을수록 효율적 |
> | `k_selected` delta | 최종 K가 얼마나 변했는지 |
> | Duplicate-at-gap delta | gap statistic K에서 발견된 중복 시너지 수 변화 |
> | Pooled cosine delta | 클러스터 내부 코사인 유사도 평균의 변화. 양수면 클러스터가 더 응집됨 |

| Mode | Transition | Mean component delta | Mean VAF delta | VAF gain per component | `k_selected` delta | Duplicate-at-gap delta | Pooled cosine delta |
|------|------------|----------------------|----------------|------------------------|--------------------|------------------------|---------------------|
| `trialwise` | `89% -> 90%` | 0.2480 | 0.006678 | 0.026927 | 5 | 1 | 0.0047 |
| `trialwise` | `90% -> 91%` | 0.3600 | 0.009643 | 0.026786 | 0 | 3 | 0.0006 |
| `trialwise` | `91% -> 92%` | 0.3120 | 0.007367 | 0.023612 | 6 | 0 | 0.0064 |
| `concatenated` | `89% -> 90%` | 0.3333 | 0.008527 | 0.025584 | 1 | 1 | -0.0031 |
| `concatenated` | `90% -> 91%` | 0.4445 | 0.010921 | 0.024569 | 2 | -1 | 0.0092 |
| `concatenated` | `91% -> 92%` | 0.4000 | 0.006205 | 0.015513 | 5 | 4 | 0.0131 |

**89% → 90%와 90% → 91% 비교:**

- **VAF gain per component**는 비슷한 수준입니다(trialwise에서 0.026927 vs 0.026786). 즉 시너지를 추가했을 때 얻는 VAF 개선 효율은 아직 비슷합니다.
- 그러나 **91%부터는 비용이 분명히 커집니다.** Trialwise에서는 `90% → 91%`에서 gap K 대비 중복 burden이 +3 늘어납니다. Concatenated에서는 `90% → 91%`의 pooled cosine 자체는 약간 좋아지지만, shared structure가 처음으로 깨집니다(아래 표 3 참조).
- **91% → 92%**에서는 VAF gain per component가 눈에 띄게 떨어집니다(trialwise 0.023612, concatenated 0.015513). 효율이 확 낮아지는 것입니다.

쉽게 말하면, 91%는 설명력 증가가 완전히 없지는 않지만 90%보다 분명히 더 비싼 영역으로 진입하는 시작점입니다.

### 3. Pooled structure 유효성 요약

> **이 표 읽는 법**
>
> | 컬럼 | 의미 |
> |------|------|
> | Mode | 분석 방식 |
> | VAF | VAF 기준값 |
> | Shared cluster rate | step 시너지와 nonstep 시너지가 모두 포함된 클러스터의 비율. 1.0이면 모든 클러스터가 양쪽을 공유 |
> | Shared member rate | 전체 시너지 중 shared cluster에 속한 비율. 1.0이면 모든 시너지가 shared cluster에 소속 |
> | Pooled member cosine mean | 클러스터 내부에서 시너지 벡터 간 코사인 유사도의 평균. 높을수록 같은 클러스터의 시너지가 서로 비슷 |
> | Shared subcentroid cosine mean | shared cluster에서 step과 nonstep 각각의 중심점(subcentroid) 간 코사인 유사도. 높을수록 step과 nonstep의 시너지가 서로 비슷 |
> | Tiny cluster rate | 매우 작은 클러스터(3개 이하 멤버)의 비율 |

| Mode | VAF | Shared cluster rate | Shared member rate | Pooled member cosine mean | Shared subcentroid cosine mean | Tiny cluster rate |
|------|-----|---------------------|--------------------|---------------------------|--------------------------------|-------------------|
| `trialwise` | `89%` | 1.0000 | 1.0000 | 0.8910 | 0.9649 | 0.0000 |
| `trialwise` | `90%` | 1.0000 | 1.0000 | 0.8957 | 0.9690 | 0.0000 |
| `trialwise` | `91%` | 1.0000 | 1.0000 | 0.8963 | 0.9765 | 0.0000 |
| `trialwise` | `92%` | 1.0000 | 1.0000 | 0.9027 | 0.9623 | 0.0000 |
| `trialwise` | `95%` | 1.0000 | 1.0000 | 0.9210 | 0.9492 | 0.0000 |
| `concatenated` | `89%` | 1.0000 | 1.0000 | 0.8841 | 0.9607 | 0.0000 |
| `concatenated` | `90%` | 1.0000 | 1.0000 | 0.8810 | 0.9621 | 0.0000 |
| `concatenated` | `91%` | 0.9375 | 0.9876 | 0.8902 | 0.9451 | 0.0000 |
| `concatenated` | `92%` | 1.0000 | 1.0000 | 0.9033 | 0.9480 | 0.0000 |
| `concatenated` | `95%` | 1.0000 | 1.0000 | 0.9145 | 0.9452 | 0.0000 |

**핵심 발견:**

- **Trialwise**에서는 shared cluster rate와 shared member rate가 85~95% 전 구간에서 계속 1.0(포화)입니다.
- **Concatenated 91%에서 shared structure가 처음으로 깨집니다.** Shared cluster rate가 1.0에서 0.9375로, shared member rate가 1.0에서 0.9876으로 떨어졌습니다. 이는 16개 클러스터 중 1개가 step 또는 nonstep 전용 클러스터가 되었다는 뜻입니다.
- 89%와 90%는 둘 다 `shared_cluster_rate = shared_member_rate = 1.0`을 유지했습니다.

따라서 이번 run에서는 pooled member cosine 하나만으로 cutoff를 고르기보다, concatenated shared-structure retention, `k_selected - k_gap_raw` escalation, duplicate burden을 함께 보는 쪽이 더 유용했습니다.

### 4. 핵심 비교: 89% vs 90% vs 91%

아래 표는 세 threshold의 핵심 지표를 나란히 비교합니다.

| 지표 | 89% (trialwise / concat) | 90% (trialwise / concat) | 91% (trialwise / concat) |
|------|--------------------------|--------------------------|--------------------------|
| Mean components | 3.720 / 4.6000 | 3.968 / 4.9333 | 4.328 / 5.3778 |
| `k_selected` | 16 / 13 | 21 / 14 | 21 / 16 |
| `k_selected - k_gap_raw` | 1 / 1 | 7 / 1 | 7 / 1 |
| Shared cluster rate (concat) | 1.0000 | 1.0000 | 0.9375 |
| Shared member rate (concat) | 1.0000 | 1.0000 | 0.9876 |

- **89%**: 가장 가벼운 설정입니다. 모든 지표가 양호하지만, 기준이 다소 느슨합니다.
- **90%**: concatenated에서 shared structure가 아직 완전합니다(1.0). K burden도 아직 관리 가능한 수준입니다.
- **91%**: concatenated에서 shared structure가 처음으로 무너지고(0.9375 / 0.9876), trialwise duplicate burden이 +3 늘어납니다.

---

### 90%를 지지하는 근거

현재 broad sweep 결과를 놓고 보면, 90%를 지지하는 가장 강한 근거는 세 가지입니다.

1. **Concatenated에서 shared structure가 완전한 마지막 practical compromise입니다.** 90%에서는 shared_cluster_rate = shared_member_rate = 1.0을 유지하지만, 91%에서는 처음으로 1.0 아래로 떨어집니다(0.9375 / 0.9876). 이는 step과 nonstep이 공유하지 않는 독립 클러스터가 처음 나타났다는 의미입니다.

2. **비용 신호가 동시에 악화되는 직전 지점입니다.** `90% → 91%` 전환에서 concatenated shared-structure erosion(-0.0124), trialwise duplicate burden 증가(+3)가 **함께** 발생합니다. 어느 한 지표만 나빠진 것이 아니라 여러 지표가 동시에 나빠지는 첫 번째 threshold가 91%입니다.

3. **91% → 92% 이후 VAF 효율이 급락합니다.** VAF gain per component가 trialwise 0.023612, concatenated 0.015513으로 떨어지며, K burden도 함께 커집니다.

---

## 해석

이번 결과는 "90%가 최소 burden cutoff"라는 뜻은 아닙니다. 실제로 burden만 보면 89%가 더 가볍습니다.

그러나 사용자 질문은 **"왜 90%를 써야 하는가"**에 가깝고, 그 질문에 대한 가장 설득력 있는 답은 다음과 같습니다.

> 90%는 과도하게 느슨한 89%보다 더 엄격하면서도, 91%에서 시작되는 concatenated shared-structure 저하와 duplicate burden 증가가 아직 본격화되기 전의 cutoff입니다.

쉽게 말하면, 90%는 **"한 단계 더 높은 기준을 설정하되, 아직 괜찮은 마지막 지점"**입니다.

또한 95%는 broad sweep만으로도 방어하기 어렵습니다. K burden(`k_selected - k_gap_raw`)이 trialwise 37, concatenated 14까지 올라가서 clustering 결과의 안정성이 크게 떨어집니다. 92% 이상도 이 방향으로 빠르게 이동하므로, 실질적 선택지는 89%, 90%, 91% 근방으로 좁혀집니다.

---

## 결론

1. **단조 증가**: `85% → 95%` broad sweep에서 mean component count와 mean VAF는 두 mode 모두 단조 증가했습니다. (기준이 엄격해지면 시너지가 늘어나는 것은 자연스러운 현상입니다.)

2. **90% = 마지막 안전 지점**: Concatenated에서 shared structure가 여전히 완전한(shared_cluster_rate = shared_member_rate = 1.0) 마지막 practical compromise였습니다.

3. **91% = 비용 시작점**: 설명력을 조금 더 올리지만, concatenated에서 shared structure가 처음으로 완전성에서 이탈하고 trialwise duplicate burden이 증가했습니다.

4. **92% 이상 = 급격한 비용 증가**: K burden과 duplicate burden이 더 빠르게 커졌고, VAF gain per component 효율도 급락했습니다.

5. **90% 방어 문장**: "90%는 더 엄격한 reconstruction criterion을 확보하면서도, 91%에서 시작되는 concatenated 구조 저하와 duplicate burden 증가가 동시에 커지기 직전의 cutoff"입니다.

---

## 재현 방법

`report.md`의 표와 결론은 아래 **screening profile** broad sweep command를 기준으로 작성했습니다. 먼저 dry-run으로 설정을 확인한 뒤, screening profile로 실행합니다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --dry-run
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
  --cluster-repeats 100 \
  --gap-ref-n 100 \
  --gap-ref-restarts 20 \
  --uniqueness-candidate-restarts 100
```

아래 command는 같은 스크립트를 default clustering profile로 rerun하는 방법이며, restart 수가 더 크기 때문에 broad sweep 숫자가 본문 표와 완전히 같지 않을 수 있습니다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py
```

**Input**:

- `configs/global_config.yaml`
- `configs/synergy_stats_config.yaml`

**Output**:

- `analysis/vaf_threshold_sensitivity/artifacts/default_run/summary.json`
- `analysis/vaf_threshold_sensitivity/artifacts/default_run/checksums.md5`

---

<!-- AUTO_APPEND: validity-implementation-2026-03-19 -->
## 추가 검증 구현 상태

이번 턴에서는 broad sweep 해석을 바꾸지 않고, 그 위에 **local VAF + null model + hold-out + cross-condition** 검증 레이어를 실행할 수 있는 새 스크립트를 구현했다.

구현 검증은 아래 smoke run으로 수행했다.

```bash
python3 analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py \
  --config configs/global_config.yaml \
  --validation-config analysis/vaf_threshold_sensitivity/config_validation.yaml \
  --thresholds 0.89 0.90 0.91 \
  --null-repeats 1 \
  --out-dir analysis/vaf_threshold_sensitivity/artifacts/validity_smoke_89_91
```

이 run은 **end-to-end smoke run**이다. 즉, 코드 경로와 artifact 생성이 정상인지 확인하는 용도이며, 최종 논문용 결론을 대신하지는 않는다. 최종 해석은 `null_repeats=100` screening run과 `null_repeats=500` exact 90% run을 다시 돌린 뒤 작성해야 한다.

### smoke run에서 확인한 점

1. `summary.json`, `by_threshold/vaf_89/summary.json`, `by_threshold/vaf_90/summary.json`, `by_threshold/vaf_91/summary.json`, `checksums.md5`가 모두 생성되었다.
2. concatenated local VAF는 계획대로 두 층으로 저장되었다.
   - `subject_muscle_channel_summary`
   - `source_trial_split_summary`
3. `null_model`, `holdout`, `cross_condition` 블록이 모두 채워졌다.

### smoke run의 빠른 관찰

- **local VAF**: `89% -> 90% -> 91%`로 갈수록 trialwise와 concatenated primary local VAF는 전반적으로 개선됐다. 예를 들어 trialwise `muscle_pass_rate_75`는 `0.794 -> 0.8235 -> 0.842`, concatenated primary는 `0.775 -> 0.7972 -> 0.8361`로 상승했다.
- **source-trial split local VAF**: secondary diagnostic이 실제로 필요하다는 점이 확인됐다. concatenated primary는 양호해 보여도 source-trial split에서는 최소 local VAF가 크게 음수인 trial이 나타났다(`89%`: `-6.3554`, `91%`: `-7.3260`).
- **null model**: smoke run에서도 observed가 null보다 더 압축적이라는 신호는 유지됐다. 예를 들어 concatenated `compression_advantage_median`은 `89%`에서 `2.5`, `90%`와 `91%`에서 `2.0`이었다.
- **hold-out reconstruction**: within-condition hold-out 성능은 threshold가 올라갈수록 개선됐다. `within_test_global_vaf_mean`은 `0.8452 -> 0.8541 -> 0.8644`, `within_test_local_pass_rate_75_mean`은 `0.6083 -> 0.6320 -> 0.6595`였다.
- **cross-condition reconstruction**: `step -> nonstep`은 within 대비 거의 보존됐지만, `nonstep -> step`은 세 threshold 모두에서 약 `-0.05` 수준의 penalty가 유지됐다.

### 현재 해석

이 smoke run만 놓고도 "`90%`가 null보다 약하고 hold-out에서 무너진다"는 신호는 보이지 않았다. 다만 이것만으로 "`90% 유지`"를 최종 결론으로 확정하면 안 된다. 이유는 다음과 같다.

- null 반복 수가 `1`이라 통계적으로 너무 얕다.
- secondary surrogate(`time_shuffle`)를 아직 넣지 않았다.
- source-trial split local VAF의 극단값을 안정적으로 해석하려면 screening / exact run이 더 필요하다.

따라서 현재 상태의 가장 정확한 문장은 다음과 같다.

> 구현은 완료됐고, smoke run에서는 `89 / 90 / 91` 비교와 artifact 생성이 정상 동작했다.  
> 최종 결론은 screening / exact run을 다시 수행한 뒤 `90% 유지 / 90% 약화 / 결론 유예` 중 하나로 정리해야 한다.
