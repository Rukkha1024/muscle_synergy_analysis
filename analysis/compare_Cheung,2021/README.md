# compare_Cheung,2021 (Cheung et al. (2020) 논문 로직 비교)

이 폴더는 **Cheung et al. (2020) 논문의 muscle synergy 분석 로직**을 현재 프로젝트의 perturbation EMG 데이터셋과 `step vs nonstep` 비교 구조에 맞춰 다시 실행하고, 그 결과를 현재 user synergy analysis 파이프라인(`default_run`)과 비교하기 위한 분석 작업 공간이다.

핵심은 “논문 로직을 그대로 복제”하는 것이 아니라, **현재 프로젝트의 trial 선택과 analysis window는 유지한 채** 논문식 NMF rank 선택, clustering, centroid matching, sparseness, merging/fractionation 해석을 별도 `analysis/` 공간에서 재적용하는 데 있다.

## 1) PDF의 NMF / clustering 분석 방법론

원본 레퍼런스:
- `analysis/compare_Cheung,2021/Cheung et al. - 2020 - Plasticity of muscle synergies through fractionation and merging during development and training of 1.pdf`

논문에서 이번 README와 직접 관련된 방법론 핵심은 아래와 같다.

1. **NMF 기반 synergy 추출**
   - 각 subject/session의 EMG를 Non-negative Matrix Factorization(NMF)으로 분해한다.
   - 시간에 따라 변하는 activation coefficient `C_i(t)`와, 시간 불변 synergy vector `W_i`의 곱으로 EMG를 재구성한다.
   - 논문은 15개 근육을 기록했기 때문에 rank를 `1..15`까지 순차적으로 시험한다.

2. **시너지 수 선택 규칙은 `R² ≈ 0.80`**
   - 각 rank에서 EMG reconstruction `R²`를 계산한다.
   - **`R²`가 약 `0.80`에 처음 도달하는 최소 rank**를 해당 데이터의 시너지 수로 선택한다.
   - 즉, “가장 잘 맞는 rank”를 고르는 방식이 아니라, **재구성이 충분해지는 가장 작은 rank**를 고르는 방식이다.

3. **k-means는 K를 먼저 정하고 실행한다**
   - 사용자님이 짚은 대로, **한 번의 k-means 실행에서는 K를 먼저 정한 뒤 clustering**한다.
   - 다만 논문은 K를 하나로 고정하지 않는다. 대신 **후보 `K = 2..20`을 각각 따로 실행**하고, 각 K마다 결과를 비교해 최종 K를 선택한다.
   - 각 candidate K마다 초기 centroid를 바꿔가며 `1000`회 반복하고, 그중 **point-to-centroid sum이 가장 작은 해**를 채택한다.

4. **최종 cluster 수는 gap statistic으로 선택한다**
   - 논문은 `K = 2..20`의 clustering 결과를 gap statistic으로 비교한다.
   - reference data `500`개를 만들고, 각 reference set도 `100`회씩 k-means를 반복한다.
   - 마지막에는 **가장 작은 적절한 K**를 gap statistic 규칙으로 고른다.

5. **subject-invariant cluster 판정**
   - 각 그룹에서 pooled synergy vector를 clustering한 뒤, **해당 그룹 subject의 `1/3`을 초과하는 subject가 기여한 cluster**를 subject-invariant cluster로 본다.
   - 즉, 특정 개인에게만 나타난 cluster보다 **그룹 내에서 반복적으로 등장하는 cluster**를 중심으로 비교한다.

6. **cluster centroid 비교와 unmatched 규칙**
   - 두 그룹의 subject-invariant cluster centroid는 scalar product(SP)로 비교한다.
   - 논문에서는 `SP < 0.8`인 경우를 **잘 매칭되지 않는 unmatched cluster**로 본다.

7. **추가 해석 지표**
   - 논문은 cluster matching만 보는 것이 아니라, synergy vector의 sparseness도 함께 본다.
   - 또, 한 그룹의 synergy가 다른 그룹의 여러 synergy 조합으로 재구성되는지를 바탕으로 fractionation / merging을 해석한다.
   - 즉, 단순히 “클러스터가 몇 개인가”가 아니라, **기존 synergy가 쪼개졌는지 또는 합쳐졌는지**까지 해석한다.

## 2) 유저 데이터셋에 맞춰서 변경된 점

이번 비교는 논문을 그대로 재현하는 것이 아니라, 현재 저장소의 입력 구조와 실험 질문에 맞춰 다음처럼 바꿨다.

1. **입력은 running EMG가 아니라 현재 프로젝트의 perturbation EMG를 사용한다**
   - 논문은 running task의 15개 right-sided lower-limb muscle을 사용했다.
   - 이번 분석은 현재 프로젝트 설정을 그대로 따라 **16채널 EMG**를 사용한다.
   - 사용 근육 목록은 `TA, EHL, MG, SOL, PL, RF, VL, ST, RA, EO, IO, SCM, GM, ESC, EST, ESL`이다.

2. **raw EMG preprocessing을 다시 하지 않는다**
   - 논문은 원시 running EMG를 바탕으로 분석한다.
   - 하지만 현재 저장소는 이미 정규화된 parquet와 event metadata를 입력 source로 사용하므로, 논문식 raw preprocessing을 처음부터 다시 재현하지 않는다.
   - 이번 작업은 **현재 프로젝트 입력에 대한 paper-style adaptation**이다.

3. **비교 축이 developmental / training group이 아니라 `step vs nonstep`이다**
   - 논문은 preschooler, sedentary, novice, experienced, elite 같은 running group을 비교했다.
   - 이번 분석은 같은 perturbation 조건 안에서 **`step` trial과 `nonstep` trial**을 비교한다.
   - 따라서 논문의 developmental conclusion을 그대로 검증하는 작업은 아니다.

4. **trial 선택과 analysis window는 baseline 파이프라인을 기준으로 고정한다**
   - 이번 분석은 trial을 새로 정의하지 않는다.
   - `outputs/runs/default_run/all_trial_window_metadata.csv`의 canonical trial list와 analysis window를 source of truth로 사용한다.
   - 즉, **입력 trial/window는 baseline과 맞추고**, 그 다음 NMF / clustering / 비교 규칙만 논문식으로 바꾼다.

5. **NMF 탐색 범위를 현재 데이터셋에 맞게 `1..16`으로 바꾼다**
   - 논문은 15근육 데이터이므로 `1..15`를 시험했다.
   - 이번 분석은 16채널 입력이므로 `1..16`을 시험한다.
   - rank 선택 규칙 자체는 논문처럼 `R² >= 0.80` 최소 rank를 유지한다.

6. **within-trial duplicate-free 제약을 추가한다**
   - 현재 프로젝트는 한 trial 안의 여러 synergy가 같은 global cluster에 중복 배정되지 않도록 보는 해석을 이미 사용하고 있다.
   - 논문 본문에서 이 제약이 핵심 규칙으로 명시되지는 않지만, 이번 분석은 **현재 프로젝트 해석 규칙과의 정합성**을 위해 duplicate-free constraint를 유지한다.

7. **activation coefficient 중심 재현은 축소하고 structure-level 비교를 우선한다**
   - 논문은 structure와 activation을 함께 해석한다.
   - 이번 분석은 현재 데이터와 baseline 파이프라인 비교에 초점을 두기 위해, **structure-level centroid 비교, cross-fit, sparseness, merging/fractionation** 쪽을 중심으로 둔다.

## 3) PDF 로직 vs user synergy analysis(파이프라인) 로직 차이점

baseline user synergy analysis 결과는 `outputs/runs/default_run/` 아래에 있다.  
이번 비교의 핵심은 “같은 trial/window를 쓰되, NMF와 clustering 규칙이 어디서 달라지는가”를 분리해서 보는 것이다.

### 3.1 NMF 차이

- **논문 / compare_Cheung 로직**
  - rank를 `1..16`까지 순차 탐색한다.
  - 각 rank에서 multiplicative-update NMF를 여러 번 다시 시작한다.
  - 현재 구현은 rank당 `20`회 restart 후 최고 `R²` 해를 보관한다.
  - 최종 rank는 **`R² >= 0.80`을 처음 만족하는 최소 rank**다.

- **현재 baseline pipeline 로직**
  - 설정은 `configs/synergy_stats_config.yaml`을 따른다.
  - `VAF >= 0.90`를 처음 만족하는 최소 rank를 선택한다.
  - `max_components_to_try`는 현재 `8`이다.
  - baseline은 rank당 여러 restart 중 최고 `R²`를 고르는 구조가 아니라, **각 rank를 한 번 적합해 순차 탐색**하는 구조다.

정리하면:
- compare_Cheung: **`R² 0.80`, `1..16`, rank당 multi-restart**
- baseline pipeline: **`VAF 0.90`, `1..8`, rank당 single-fit 중심**

### 3.2 Clustering 차이

- **논문 / compare_Cheung 로직**
  - candidate `K`를 여러 개 둔다.
  - 각 candidate K마다 k-means를 반복 실행한다.
  - 그다음 **gap statistic**으로 최종 K를 선택한다.
  - 이번 구현은 여기에 duplicate-free assignment를 덧붙여, trial 내부 중복 cluster 배정을 막는다.

- **현재 baseline pipeline 로직**
  - `global_step`, `global_nonstep`으로 고정 grouping 후 pooled synergy vector를 clustering한다.
  - candidate K는 `k_min = max(2, subject_hmax)`에서 시작한다.
  - 이후 K를 증가시키다가 **within-trial duplicate가 0개가 되는 첫 K**를 바로 채택한다.
  - 즉, baseline은 **gap statistic을 쓰지 않고**, “중복 없는 가장 작은 K”를 선택하는 쪽에 가깝다.

정리하면:
- compare_Cheung: **여러 K 평가 후 gap statistic으로 최종 K 선택**
- baseline pipeline: **zero-duplicate가 되는 첫 K 선택**

### 3.3 Common cluster와 centroid matching 차이

- **논문 / compare_Cheung 로직**
  - `1/3` 이상 subject가 기여한 cluster만 common cluster로 인정한다.
  - common centroid끼리 scalar product를 계산한다.
  - `SP < 0.8`이면 unmatched로 남긴다.

- **현재 baseline pipeline 로직**
  - representative W/H export는 있지만, 논문식 common-cluster `1/3` 규칙과 `SP < 0.8 unmatched` 규칙을 직접 전면에 두지는 않는다.
  - baseline은 주로 trial feature extraction, global grouping, representative export 중심의 산출물을 만든다.

즉, compare_Cheung은 baseline 결과를 단순 재출력하는 것이 아니라, **논문식 cluster semantics를 현재 데이터에 다시 입히는 분석**이다.

### 3.4 Downstream 해석 범위 차이

- **논문 / compare_Cheung 로직**
  - rank 선택
  - common cluster 추출
  - centroid matching
  - sparseness
  - cross-fit
  - centroid-level / individual-level merging or fractionation
  - baseline representative synergy와의 correspondence 비교

- **현재 baseline pipeline 로직**
  - trial window 확정
  - trial-level NMF
  - global step/nonstep clustering
  - representative W/H export

즉, compare_Cheung은 baseline pipeline 위에 **“논문식 구조 비교 해석층”을 추가한 분석**이라고 보는 편이 정확하다.

## 4) 실행 방법

작업 디렉토리: repo root (`/home/alice/workspace/26-03-synergy-analysis`)

dry-run:

```bash
conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py --dry-run
```

full run:

```bash
conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py
```

논문에 더 가까운 clustering runtime으로 돌리려면 `--paper-full`을 추가한다.

## 5) 참고 문서

- 분석 스크립트: `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`
- 결과 리포트: `analysis/compare_Cheung,2021/report.md`
- 체크섬 기록: `analysis/compare_Cheung,2021/checksums.md5`

이 README는 **비교 기준과 방법론 차이**를 설명하는 문서이고, 실제 결과 수치와 figure 해석은 `report.md`에서 확인하면 된다.
시각화 파일 목록도 `report.md`의 Figures 섹션을 참고하면 된다.
