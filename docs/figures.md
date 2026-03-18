# Figure 산출물 가이드

파이프라인이 생성하는 각 figure의 파일명, 생성 조건, 시각화 구성, 해석 방법을 정리한다.

---

## 출력 디렉터리 구조

Figure는 mode별 하위 디렉터리 안에만 생성된다. run 루트에는 figure가 저장되지 않는다.

```text
<runtime.output_dir>/
  trialwise/
    figures/
      01_trial_composition.png          ← concatenated mode에만 있음 (여기선 없음)
      03_cluster_strategy_composition.png
      04_pooled_cluster_representatives.png
      05_within_cluster_strategy_overlay.png
      cross_group_cosine_heatmap.png    ← 선택적
      cross_group_matched_w.png         ← 선택적
      cross_group_matched_h.png         ← 선택적
      cross_group_decision_summary.png  ← 선택적
      nmf_trials/
        <subject>_v<velocity>_T<trial_num>_<step_class>_nmf.png
  concatenated/
    figures/
      01_trial_composition.png          ← concatenated mode 전용
      03_cluster_strategy_composition.png
      04_pooled_cluster_representatives.png
      05_within_cluster_strategy_overlay.png
      nmf_trials/
        ...
```

> 기존 run의 figure만 다시 만들려면 `scripts/emg/06_render_figures_only.py`를 사용한다.

---

## 공통 시각 설계

| 요소 | 값 |
|------|----|
| step 색상 | `#5C7CFA` (파랑) |
| nonstep 색상 | `#E64980` (분홍) |
| 매칭된 시너지 색상 | `#2F9E44` (초록) |
| 그룹 고유 시너지 색상 | `#868E96` (회색) |
| 기본 해상도 | 150 DPI (설정: `figures.dpi`) |
| 기본 형식 | PNG (설정: `figures.format`) |
| 한국어 폰트 | NanumGothic → NanumBarunGothic → Malgun Gothic 순 탐색 |

---

## Figure 01 — Trial Composition

| 항목 | 내용 |
|------|------|
| 파일명 | `01_trial_composition.png` |
| 저장 위치 | `<mode>/figures/` |
| 생성 조건 | **concatenated mode 전용** |

### 시각화 구성

- 형식: 그룹 막대 그래프
- X축: 피험자 (subject)
- Y축: source window 개수
- 색상: step(파랑) / nonstep(분홍)
- 막대 위에 실제 개수 표시

### 핵심 질문

> concatenated trial 구성이 피험자 간, 전략 간 균형 잡혀 있는가?

### 해석 가이드

각 피험자별로 step과 nonstep source window가 얼마나 모였는지 한눈에 확인한다.
특정 피험자 또는 전략 쪽으로 편향이 심하다면 pooling 결과 해석 시 주의가 필요하다.

---

## Figure 03 — Cluster Strategy Composition

| 항목 | 내용 |
|------|------|
| 파일명 | `03_cluster_strategy_composition.png` |
| 저장 위치 | `<mode>/figures/` |
| 생성 조건 | pooled_step_nonstep 그룹이 존재할 때 |

### 시각화 구성

- 형식: 100% 누적 막대 그래프
- X축: cluster ID (정렬됨)
- Y축: 비율 (0–1)
- 아래 세그먼트: step (파랑), 위 세그먼트: nonstep (분홍)
- 각 막대 위에 `n={합계}` 표시

### 핵심 질문

> 각 pooled cluster 안에서 step과 nonstep이 어떤 비율로 섞여 있는가?

### 해석 가이드

- 한쪽 전략이 압도적인 cluster → 해당 cluster는 전략 특이적 synergy일 가능성 높음
- 두 전략이 고루 섞인 cluster → 전략에 무관하게 사용되는 공통 synergy일 가능성 높음
- Figure 05와 함께 읽어야 구성 비율과 실제 패턴 차이를 종합 평가할 수 있음

---

## Figure 04 — Pooled Cluster Representatives

| 항목 | 내용 |
|------|------|
| 파일명 | `04_pooled_cluster_representatives.png` (또는 `pooled_step_nonstep_clusters.png`) |
| 저장 위치 | `<mode>/figures/` |
| 생성 조건 | pooled_step_nonstep 그룹이 존재할 때 |

### 시각화 구성

cluster당 한 행, 각 행은 두 패널로 구성:

**왼쪽 패널 — W (근육 가중치)**
- 형식: 막대 그래프
- X축: 근육명 (채널 순서)
- Y축: 가중치 (0–1.15, column-normalized)
- 색상: 단일 파랑 (`#5C7CFA`)
- 제목: `Cluster {id}: W | {n_trials}/{total} trials ({pct}%) | {n_subjects}/{total} subjects`

**오른쪽 패널 — H (시간적 활성화)**
- 형식: 선 그래프
- X축: 정규화된 분석 창 (0–100%)
- Y축: 활성화 값
- 색상: 초록 (`#2F9E44`)

### 핵심 질문

> 각 대표 synergy의 특징적인 근육 조합(W)과 시간적 활성화 패턴(H)은 무엇인가?

### 해석 가이드

- W 패널: 어떤 근육들이 이 synergy를 구성하는지 확인. 가중치가 높은 근육이 핵심 기여 근육
- H 패널: synergy가 분석 창(platform_onset ~ step/surrogate_step_onset) 내에서 언제 활성화되는지 확인
- 제목의 trial/subject 커버리지는 이 cluster가 얼마나 일반화된 패턴인지를 나타냄

---

## Figure 05 — Within-Cluster Strategy Overlay

| 항목 | 내용 |
|------|------|
| 파일명 | `05_within_cluster_strategy_overlay.png` |
| 저장 위치 | `<mode>/figures/` |
| 생성 조건 | pooled cluster 내 step 또는 nonstep 중 적어도 한 쪽이 n ≥ 3 |

### 시각화 구성

cluster당 한 행, 각 행은 두 패널로 구성:

**왼쪽 패널 — W 비교 (그룹 막대)**
- step 평균 W: 파랑 막대 (왼쪽 오프셋)
- nonstep 평균 W: 분홍 막대 (오른쪽 오프셋)
- 막대 너비: 0.35

**오른쪽 패널 — H 비교 (오버레이 + SD 밴드)**
- step 평균 H: 파랑 선 (linewidth 3.0) + 파랑 SD 음영 (alpha 0.2)
- nonstep 평균 H: 분홍 선 (linewidth 3.0) + 분홍 SD 음영 (alpha 0.2)
- 표본이 부족하면 (n < 3) "insufficient n" 메시지 출력

### 핵심 질문

> 같은 cluster에 묶인 trial이라도 step과 nonstep이 실제로 다른 활성화 패턴을 보이는가?

### 해석 가이드

- W 패널에서 두 전략의 막대 높이가 비슷 → 근육 조합은 공통적
- H 패널에서 두 선의 형태가 다름 → 같은 근육 조합이라도 활성화 타이밍이 다름
- SD 밴드가 넓으면 해당 전략 내 개인차가 크다는 의미
- Figure 03과 함께 읽으면: 구성 비율(03) + 실제 패턴 차이(05)를 종합 판단 가능

---

## 개별 Trial NMF Figures

| 항목 | 내용 |
|------|------|
| 파일명 | `<subject>_v<velocity>_T<trial_num>_<step_class>_nmf.png` |
| 저장 위치 | `<mode>/figures/nmf_trials/` |
| 생성 조건 | 모든 분석 대상 trial에 대해 생성 |

### 시각화 구성

Figure 04와 동일한 W/H 이중 패널 구조, component당 한 행.

- 제목: `{subject} v{velocity} T{trial_num} ({step_class})`
- NMF로 추출된 각 component(synergy)를 개별 행으로 표시

### 핵심 질문

> 특정 trial에서 추출된 개별 NMF component들은 어떤 패턴인가?

### 해석 가이드

이상 trial을 진단하거나, 대표 cluster와 매칭되기 전 원시 component를 확인할 때 사용한다.
파일 수가 많으므로 특정 피험자/trial을 타겟팅해서 열어보는 용도로 적합하다.

---

## Cross-Group Figures (선택적)

다음 4개의 figure는 `cross_group_w_similarity` 설정이 활성화되어 있고, `global_step`과 `global_nonstep` 그룹이 모두 존재할 때만 생성된다. 기본 main pipeline 실행에서는 생성되지 않는다.

---

### Cross-Group Cosine Similarity Heatmap

| 항목 | 내용 |
|------|------|
| 파일명 | `cross_group_cosine_heatmap.png` |
| 저장 위치 | `<mode>/figures/` |

**시각화 구성**
- 형식: 2D 히트맵
- X축: nonstep cluster ID, Y축: step cluster ID
- 색상: Blues (0–1)
- 셀 안에 코사인 유사도 값 (소수점 2자리)
- ★ 표시: 임계값을 통과한 매칭 쌍

**핵심 질문**: step과 nonstep의 어떤 cluster 쌍이 가장 유사한가?

---

### Cross-Group Matched W Profiles

| 항목 | 내용 |
|------|------|
| 파일명 | `cross_group_matched_w.png` |
| 저장 위치 | `<mode>/figures/` |

**시각화 구성**
- 매칭된 쌍: step/nonstep W를 나란히 그룹 막대로 비교
- 매칭되지 않은 그룹 고유 cluster: 단일 색상 막대
- 제목에 코사인 유사도 표시

**핵심 질문**: 유사하다고 판정된 step/nonstep cluster들이 실제로 같은 근육을 사용하는가?

---

### Cross-Group Matched H Profiles

| 항목 | 내용 |
|------|------|
| 파일명 | `cross_group_matched_h.png` |
| 저장 위치 | `<mode>/figures/` |

**시각화 구성**
- 매칭된 쌍: step/nonstep H 평균 선 오버레이 + SD 밴드
- 그룹 고유 cluster: 단일 선 + SD 밴드, 제목에 `mean ± SD` 표기

**핵심 질문**: 근육 조합이 유사한 cluster들이 시간적 활성화 패턴도 유사한가?

---

### Cross-Group Decision Summary

| 항목 | 내용 |
|------|------|
| 파일명 | `cross_group_decision_summary.png` |
| 저장 위치 | `<mode>/figures/` |

**시각화 구성**
- 형식: 수평 누적 막대 그래프
- Y축: step / nonstep 그룹
- 초록 세그먼트: `same_synergy` (매칭됨), 회색 세그먼트: `group_specific_synergy`
- 흰색 텍스트로 개수 표시

**핵심 질문**: 전체 cluster 중 전략 공통 시너지와 전략 고유 시너지의 비율은 어떻게 되는가?
