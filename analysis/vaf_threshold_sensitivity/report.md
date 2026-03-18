# VAF Threshold Sensitivity

## Research Question

**"VAF 기준값을 85%부터 95%까지 1% 단위로 바꾸면, subject와 step/nonstep 기준의 NMF 시너지 수와 pooled k-means의 K는 어떻게 달라지며, 그중 `90%`를 cutoff로 방어할 수 있는가?"**

이번 분석은 EMG synergy main pipeline의 trial selection과 pooled clustering 규칙을 재사용하고, NMF는 같은 low-level rank fitting / VAF 계산 규칙을 캐시 기반으로 재조합한 민감도 점검이다. 결과는 `trialwise`와 `concatenated` 두 mode 모두에 대해 비교한다.

## Data Summary

- Selected trials: `125`개
- Subject 수: `24`
- Step trials: `53`
- Nonstep trials: `72`
- Data source: `configs/global_config.yaml`의 `input.emg_parquet_path`
- Trial classification: `configs/global_config.yaml`의 `input.event_xlsm_path`
- Analysis modes: `trialwise`, `concatenated`

## Analysis Methodology

- **Analysis window**: main pipeline의 event metadata preparation과 `build_trial_records()` slicing 규칙을 그대로 사용
- **Trial selection**: `analysis_selected_group == True`
- **NMF selection rule**: 각 분석 단위마다 가능한 모든 rank를 한 번씩 fit하고, 각 threshold에서는 그중 처음 threshold를 만족하는 최소 rank를 선택
- **Concatenated mode**: `(subject, velocity, step_class)` 단위 super-trial을 구성한 뒤, 각 source trial의 averaged activation profile을 다시 분리해 threshold별 feature row를 만든다.
- **Clustering rule**: mode별 단일 `pooled_step_nonstep` 공간에서 `cluster_feature_group()`를 호출하고, `gap statistic + zero-duplicate feasibility`로 `K`를 선택
- **Thresholds compared**: `85%`부터 `95%`까지 `1%` 단위
- **Broad sweep clustering setting**: `85%`부터 `95%`까지의 전 구간 탐색은 계산 시간을 관리하기 위해 clustering restart 수만 줄여서 rerun했다.
- **Logic-lock note**: trial selection, NMF rank selection, pooled clustering, gap statistic, zero-duplicate feasibility 규칙은 유지하고, broad sweep에서는 restart 수만 screening 목적에 맞게 축소했다.
- **Coordinate & sign conventions**:

  - Axis & Direction Sign

    | Axis | Positive (+) | Negative (-) | 대표 변수 |
    |------|---------------|---------------|-----------|
    | AP (X) | `+X = Anterior` | `-X = Posterior` | 해당 없음 |
    | ML (Y) | `+Y = Left` | `-Y = Right` | 해당 없음 |
    | Vertical (Z) | `+Z = Up` | `-Z = Down` | 해당 없음 |

  - Signed Metrics Interpretation

    | Metric | (+) meaning | (-) meaning | 판정 기준/참조 |
    |--------|--------------|--------------|----------------|
    | 해당 없음 | 해당 없음 | 해당 없음 | 본 분석은 NMF rank와 cluster count만 다룸 |
    | 해당 없음 | 해당 없음 | 해당 없음 | 본 분석은 좌표 기반 signed metric을 직접 사용하지 않음 |
    | 해당 없음 | 해당 없음 | 해당 없음 | 본 분석은 좌표 기반 signed metric을 직접 사용하지 않음 |

  - Joint/Force/Torque Sign Conventions

    | Variable group | (+)/(-) meaning | 추가 규칙 |
    |----------------|------------------|-----------|
    | EMG synergy weights | 부호 없음 | NMF 입력은 0 이상 값만 사용 |
    | Cluster labels | 부호 없음 | cluster id는 식별자이며 방향 의미 없음 |
    | VAF threshold | 부호 없음 | threshold 상향 시 더 높은 재현율 요구 |

## Results

`85%`부터 `95%`까지 `1%` 단위 broad sweep을 rerun한 결과, threshold가 올라갈수록 두 mode 모두 평균 시너지 수와 평균 VAF가 단조 증가했다. 아래 표의 숫자는 **screening profile**인 reduced-restart broad sweep 결과를 기준으로 한다. `trialwise`는 평균 시너지 수가 `2.768 → 6.032`, 평균 VAF가 `0.875728 → 0.956781`로 상승했고, `concatenated`는 평균 시너지 수가 `3.4444 → 7.2000`, 평균 VAF가 `0.872686 → 0.950773`으로 상승했다.

이 증가 자체만 보면 threshold를 더 높일수록 더 엄격한 재구성 기준을 적용하는 것이므로 당연한 방향이다. 따라서 `90%`를 방어하려면 단순히 mean component count가 늘었다는 사실보다, `90%`가 **ceiling artifact가 시작되기 직전의 마지막 cutoff인지**, 그리고 `90%` 이후가 **일부 지표 개선이 남아 있더라도 ceiling-hit과 clustering burden이 더 먼저 커지기 시작하는 구간인지**를 함께 봐야 한다.

### 1. Broad sweep component and burden summary

| Mode | VAF | Total components | Mean components | Mean VAF | `k_gap_raw` | `k_selected` | `k_selected - k_gap_raw` | Ceiling-hit rate |
|------|-----|------------------|-----------------|----------|-------------|--------------|--------------------------|------------------|
| `trialwise` | `85%` | 346 | 2.768 | 0.875728 | 11 | 11 | 0 | 0.0000 |
| `trialwise` | `89%` | 465 | 3.720 | 0.909410 | 15 | 16 | 1 | 0.0000 |
| `trialwise` | `90%` | 496 | 3.968 | 0.916088 | 14 | 21 | 7 | 0.0000 |
| `trialwise` | `91%` | 541 | 4.328 | 0.925731 | 14 | 21 | 7 | 0.0080 |
| `trialwise` | `92%` | 580 | 4.640 | 0.933098 | 16 | 27 | 11 | 0.0080 |
| `trialwise` | `95%` | 754 | 6.032 | 0.956781 | 17 | 54 | 37 | 0.1600 |
| `concatenated` | `85%` | 155 | 3.4444 | 0.872686 | 9 | 11 | 2 | 0.0000 |
| `concatenated` | `89%` | 207 | 4.6000 | 0.903979 | 12 | 13 | 1 | 0.0000 |
| `concatenated` | `90%` | 222 | 4.9333 | 0.912506 | 13 | 14 | 1 | 0.0222 |
| `concatenated` | `91%` | 242 | 5.3778 | 0.923427 | 15 | 16 | 1 | 0.0444 |
| `concatenated` | `92%` | 260 | 5.7778 | 0.929632 | 14 | 21 | 7 | 0.0667 |
| `concatenated` | `95%` | 324 | 7.2000 | 0.950773 | 15 | 29 | 14 | 0.5778 |

위 표에서 가장 중요한 패턴은 `90%`가 `trialwise`에서는 **ceiling-hit rate = 0**인 마지막 threshold이고, `concatenated`에서는 ceiling-hit이 아주 작게 시작되더라도(`1/45 = 0.0222`) 아직 `shared_cluster_rate = shared_member_rate = 1.0`을 유지하는 practical neighborhood의 끝점이라는 점이다. `91%`로 올리면 `trialwise`는 ceiling-hit이 처음 발생하고(`1/125 = 0.0080`), `concatenated`는 ceiling-hit이 `0.0444`로 커지면서 shared structure가 처음으로 완전성에서 이탈한다(`shared_cluster_rate = 0.9375`, `shared_member_rate = 0.9876`). 이후 `95%`에서는 `trialwise 20/125`, `concatenated 26/45`가 상한(`max_components_to_try = 8`)에 도달했다.

### 2. Adjacent-threshold diagnostic around 90%

| Mode | Transition | Mean component delta | Mean VAF delta | VAF gain per component | `k_selected` delta | Ceiling-hit delta | Duplicate-at-gap delta | Pooled cosine delta |
|------|------------|----------------------|----------------|------------------------|--------------------|-------------------|------------------------|---------------------|
| `trialwise` | `89% -> 90%` | 0.2480 | 0.006678 | 0.026927 | 5 | 0.0000 | 1 | 0.0047 |
| `trialwise` | `90% -> 91%` | 0.3600 | 0.009643 | 0.026786 | 0 | 0.0080 | 3 | 0.0006 |
| `trialwise` | `91% -> 92%` | 0.3120 | 0.007367 | 0.023612 | 6 | 0.0000 | 0 | 0.0064 |
| `concatenated` | `89% -> 90%` | 0.3333 | 0.008527 | 0.025584 | 1 | 0.0222 | 1 | -0.0031 |
| `concatenated` | `90% -> 91%` | 0.4445 | 0.010921 | 0.024569 | 2 | 0.0222 | -1 | 0.0092 |
| `concatenated` | `91% -> 92%` | 0.4000 | 0.006205 | 0.015513 | 5 | 0.0223 | 4 | 0.0131 |

`89% -> 90%`와 `90% -> 91%`의 VAF gain per component는 비슷한 수준이지만, `91%`부터는 burden escalation이 더 분명해진다. `trialwise`에서는 `90% -> 91%`에서 ceiling-hit이 처음 생기고 duplicate burden이 `+3` 늘어난다. `concatenated`에서는 `90% -> 91%`의 pooled cosine mean 자체는 약간 좋아지지만, shared structure가 처음으로 완전성에서 벗어나고 ceiling-hit도 `0.0222 -> 0.0444`로 늘어난다. 즉 `91%`는 설명력 증가가 완전히 없지는 않지만, `90%`보다 분명히 더 비싼 영역으로 진입하는 시작점이다.

### 3. Pooled-structure validity summary

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

shared cluster rate와 shared member rate는 `trialwise`에서는 계속 포화되어 있었지만, `concatenated`에서는 `91%`에서 처음으로 `1.0` 아래로 떨어졌다. 반면 `89%`와 `90%`는 둘 다 `shared_cluster_rate = shared_member_rate = 1.0`을 유지했다. 따라서 이번 run에서는 `pooled member cosine mean` 하나만으로 cutoff를 고르기보다, `trialwise` ceiling-hit onset, `concatenated` shared-structure retention, `k_selected - k_gap_raw` escalation을 함께 보는 쪽이 더 유용했다.

### 4. What supports `90%`

현재 broad sweep 결과만 놓고 보면, `90%`를 지지하는 가장 강한 근거는 **"trialwise에서는 마지막 zero-ceiling threshold이고, concatenated에서는 shared structure가 아직 완전한 상태로 남아 있는 가장 높은 practical compromise"**라는 점이다. `89%`는 더 parsimonious하지만 덜 엄격하고, `91%`는 mean VAF를 더 올리더라도 `trialwise` ceiling-hit onset과 `concatenated` shared-structure erosion이 함께 시작된다.

특히 `trialwise`에서는 `90% -> 91%`에서 `k_selected`가 더 좋아지지 않는데도 ceiling-hit이 처음 생기고 duplicate burden이 `+3` 늘어난다. `concatenated`에서는 `90%`가 이미 아주 작은 ceiling-hit을 보이지만(`0.0222`), `shared_cluster_rate = shared_member_rate = 1.0`은 유지한다. 반면 `91%`는 ceiling-hit이 `0.0444`로 커지고 shared structure가 `0.9375 / 0.9876`으로 처음 무너진다. `92%`부터는 `k_selected`가 `16 -> 21`로 다시 크게 올라가므로, `90%`는 `89%`와 `91%` 사이의 현실적인 타협점으로 해석할 수 있다.

## Interpretation

이번 결과는 "`90%`가 최소 burden cutoff"라는 뜻은 아니다. 실제로 burden만 보면 `89%`가 더 가볍다. 그러나 사용자 질문은 **왜 `90%`를 써야 하는가**에 가깝고, 그 질문에 대한 가장 설득력 있는 답은 "`90%`가 과도하게 느슨한 `89%`보다 더 엄격하면서도, `91%`에서 시작되는 trialwise ceiling-hit과 concatenated shared-structure 저하가 아직 본격화되기 전의 cutoff"라는 operational sweet spot 논리다.

또한 `95%`는 broad sweep만으로도 방어하기 어렵다. `trialwise`는 ceiling-hit rate가 `0.1600`, `concatenated`는 `0.5778`까지 올라가서, 높은 재구성 기준이라기보다 `max_components_to_try=8` 상한의 영향을 강하게 받는 구간으로 보인다. `92%` 이상도 이 방향으로 빠르게 이동하므로, 실질적 선택지는 `89%`, `90%`, `91%` 근방으로 좁혀진다.

현 단계에서 가장 정직한 해석은 다음과 같다. `89%`는 더 가볍지만 다소 느슨하고, `91%`는 더 엄격하지만 `trialwise` ceiling-hit과 `concatenated` 구조 저하가 함께 시작된다. 따라서 `90%`는 "strictness를 한 단계 더 올리되, 두 mode에서 비용 신호가 동시에 더 나빠지기 직전에서 멈춘 cutoff"로 가장 방어하기 쉽다.

### Conclusion

1. `85% -> 95%` broad sweep에서 mean component count와 mean VAF는 두 mode 모두 단조 증가했다.
2. `90%`는 `trialwise`에서는 ceiling-hit rate가 아직 `0`인 마지막 threshold였고, `concatenated`에서는 shared structure가 여전히 완전한(`shared_cluster_rate = shared_member_rate = 1.0`) 마지막 practical compromise였다.
3. `91%`는 설명력을 조금 더 올리지만 `trialwise`에서는 ceiling-hit이 시작되고, `concatenated`에서는 shared structure가 처음으로 완전성에서 이탈했다.
4. `92%` 이상은 `K` burden과 ceiling-hit이 더 빠르게 커졌고, `95%`는 상한 포화의 영향이 명확했다.
5. 따라서 현재 결과에서 `90%`를 방어하는 가장 강한 문장은 "`90%`는 더 엄격한 reconstruction criterion을 확보하면서도, `91%`에서 시작되는 trialwise ceiling-hit과 concatenated 구조 저하가 동시에 커지기 직전의 cutoff"라는 것이다.

## Reproduction

`report.md`의 표와 결론은 아래 **screening profile** broad sweep command를 기준으로 작성했다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --dry-run
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
  --cluster-repeats 100 \
  --gap-ref-n 100 \
  --gap-ref-restarts 20 \
  --uniqueness-candidate-restarts 100
```

아래 command는 같은 스크립트를 default clustering profile로 rerun하는 방법이며, restart 수가 더 크기 때문에 broad sweep 숫자가 본문 표와 완전히 같지 않을 수 있다.

```bash
conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py
```

**Input**:

- `configs/global_config.yaml`
- `configs/synergy_stats_config.yaml`

**Output**:

- `analysis/vaf_threshold_sensitivity/artifacts/default_run/summary.json`
- `analysis/vaf_threshold_sensitivity/artifacts/default_run/checksums.md5`
