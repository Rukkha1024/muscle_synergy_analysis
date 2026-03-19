# VAF threshold 추가 검증 ExecPlan (수정본)
# local VAF + shuffled/surrogate null + hold-out/cross-condition reconstruction
# 작업 위치: analysis/vaf_threshold_sensitivity/

이 문서는 living document다.  
작업이 진행될 때마다 `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective`를 계속 업데이트한다.

---

## 이번 수정의 핵심 요약

이번 수정에서 바뀐 점은 2가지다.

첫째, **concatenated mode의 local VAF 정의를 더 명확히 바꾼다.**  
이제 concatenated local VAF의 1차 요약 단위는 **subject-muscle channel**이다.  
정확히 말하면, 같은 subject의 mixed velocity 안에서 같은 class(step 또는 non-step) trial들을 이어 붙여 만든 super-trial에 대해, **각 muscle channel별 local VAF**를 계산한다.

둘째, **작업 위치를 새 폴더가 아니라 기존 `analysis/vaf_threshold_sensitivity/`로 고정한다.**  
즉, 이번 추가분석은 기존 broad sweep 작업을 버리고 새 프로젝트를 만드는 것이 아니라, **기존 작업에 이어서 덧붙이는 확장 분석**이다.

중요한 점은, 첫 번째 수정은 기존 계획과 **실질적으로 충돌하지 않는다.**  
다만 기존 문구 중 “concatenated local VAF는 source trial로 다시 잘라서 평가한다”라는 표현이 **유일한 local VAF 정의처럼 읽히면 문제**가 된다.  
이 문구는 이제 다음처럼 고쳐야 한다.

- **1차 concatenated local VAF**: subject-muscle channel 기준
- **2차 보조 진단**: source trial로 다시 잘라서 trial-level local VAF 확인

즉, 기존 내용은 삭제 대상이 아니라 **역할 재배치 대상**이다.  
source-trial split local VAF는 여전히 필요하다. 이유는 concatenated super-trial 전체에서는 좋아 보여도, 실제로는 일부 source trial에서만 fit가 망가질 수 있기 때문이다.  
따라서 이번 수정은 “기존 내용과 충돌”이 아니라, **concatenated local VAF 해석 층을 2단계로 재정의하는 수정**이다.

---

## Purpose / 큰 목표

이번 추가분석의 목적은 `global VAF 90%`가 단순 관행이 아니라, 실제로도 방어 가능한 cutoff인지 더 단단하게 검증하는 것이다.

검증은 세 층으로 한다.

1. **local VAF**
   - global VAF가 90%여도, 특정 근육 채널은 형편없이 재구성될 수 있다.
   - 따라서 각 muscle channel 수준에서 fit를 봐야 한다.

2. **shuffled / surrogate null model**
   - 실제 데이터가 우연히 구조적으로 보이는 것인지,
   - 아니면 진짜 coordination structure가 있는 것인지 확인해야 한다.

3. **hold-out reconstruction / cross-condition reconstruction**
   - 선택된 W가 같은 전략의 안 본 trial에도 통하는지,
   - 그리고 반대 전략에도 어느 정도 일반화되는지 확인해야 한다.

이번 연구 질문은 “동일한 perturbation 강도에서 왜 step과 non-step이 갈리는가”이므로,  
모든 비교는 반드시 **같은 subject, 같은 mixed velocity 안에서만** 수행한다.

---

## Progress / 진행상황

- [x] 범위 확정: `local VAF`, `shuffled/surrogate null`, `hold-out reconstruction`, `cross-condition reconstruction`
- [x] threshold 비교값 확정: `0.89`, `0.90`, `0.91`
- [x] concatenated local VAF 정의 수정:
  - 1차 요약 = subject-muscle channel
  - 2차 보조 진단 = source trial split local VAF
- [x] 작업 위치 수정: `analysis/vaf_threshold_sensitivity/` 내부에서 기존 작업을 이어서 수행
- [x] `analysis/vaf_threshold_sensitivity/config_validation.yaml` 추가
- [x] `analysis/vaf_threshold_sensitivity/validation_helpers.py` 추가
- [x] `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py` 추가
- [x] `--dry-run` 검증
- [x] smoke run 수행 (`0.89`, `0.90`, `0.91`, `null_repeats=1`)
- [ ] screening run 수행 (`0.89`, `0.90`, `0.91`)
- [ ] exact run 수행 (`0.90`, null repeat 증가)
- [x] `report.md`에 구현 상태와 smoke run 결과 반영
- [x] checksum / reproducibility 확인 (smoke run artifact)

---

## Surprises & Discoveries / 예상되는 함정

### 1. concatenated local VAF는 한 층으로 끝내면 안 된다
subject-muscle channel local VAF만 보면, 어떤 subject의 특정 muscle이 전체적으로는 잘 맞는 것처럼 보여도 실제로는 일부 source trial에서만 fit가 크게 깨질 수 있다.  
그래서 source trial split local VAF를 **보조 진단으로 반드시 유지**해야 한다.

### 2. hold-out 가능 표본 수가 적을 수 있다
같은 subject·같은 mixed velocity·같은 class 안에서 trial 수가 2개 이상이어야 leave-one-out hold-out이 가능하다.  
trial 수가 부족한 subject가 생길 수 있으므로, eligible subject 수를 반드시 summary에 남겨야 한다.

### 3. null model은 source trial 경계를 넘으면 안 된다
concatenated super-trial 전체를 한 번에 shuffle/circular shift 하면 원래 없던 가짜 구조가 생길 수 있다.  
따라서 null은 **source trial마다 따로 만든 뒤 concatenate**해야 한다.

### 4. local VAF는 저분산 채널에서 불안정할 수 있다
어떤 muscle channel의 분산이 거의 0이면 local VAF가 수학적으로 불안정해진다.  
이 경우 억지로 계산하지 말고 `not_applicable` 처리하고 유효 채널 수를 따로 보고한다.

### 5. source-trial split local VAF는 실제로 매우 거칠 수 있다
smoke run에서 concatenated primary local VAF는 비교적 안정적으로 보였지만,  
source-trial split local VAF의 최소값은 큰 음수까지 내려갔다.  
즉, 2차 보조 진단을 유지해야 한다는 가정이 구현 이후에도 그대로 확인됐다.

### 6. smoke run만으로 최종 결론을 쓰면 안 된다
`null_repeats=1` smoke run은 코드 경로와 artifact 구조를 확인하는 데는 충분했지만,  
`90% 유지` 같은 최종 결론을 쓰기에는 반복 수가 너무 적다.  
따라서 screening / exact run은 그대로 남겨 둔다.

---

## Decision Log / 결정 기록

### Decision 1
**모든 새 작업은 `analysis/vaf_threshold_sensitivity/` 안에서 진행한다.**  
새 analysis 폴더를 따로 만들지 않는다.

**이유**  
사용자 요청이 “기존 작업에 추가”이기 때문이다.  
기존 broad sweep 결과를 reference로 두고, 같은 폴더 안에서 validation layer를 이어 붙이는 구조가 더 자연스럽다.

---

### Decision 2
**기존 `analyze_vaf_threshold_sensitivity.py`는 baseline artifact 생성용으로 보존하고,  
추가분석은 같은 폴더 안의 새 entry script로 수행한다.**

추천 파일명:
- `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py`

**이유**  
기존 broad sweep을 망가뜨리지 않고,  
추가 검증만 따로 재실행하기 쉽기 때문이다.

---

### Decision 3
**concatenated local VAF의 1차 기준은 subject-muscle channel로 둔다.**

정확히는 다음과 같다.

- 같은 subject
- 같은 mixed velocity
- 같은 class(step 또는 non-step)

에서 source trial들을 concatenate한 super-trial을 만들고,  
그 super-trial의 **각 muscle channel별 local VAF**를 계산한다.

**이유**  
concatenated mode의 본질은 “trial을 이어 붙인 하나의 class-level structure”를 보는 것이기 때문이다.  
따라서 concatenated local VAF의 1차 지표는 super-trial의 muscle-channel fit가 맞다.

---

### Decision 4
**source trial split local VAF는 제거하지 않는다.**

이것은 concatenated local VAF의 2차 보조 진단으로 유지한다.

**이유**  
subject-muscle channel 기준은 전체적 fit는 보여주지만,  
“특정 몇 개 trial만 유독 안 맞는가?”는 숨길 수 있다.  
그래서 source trial로 다시 잘라서 trial-level local VAF를 확인해야 한다.

---

### Decision 5
**cross-condition reconstruction은 같은 subject, 같은 mixed velocity 안에서만 한다.**

**이유**  
다른 velocity를 섞으면 전략 차이와 강도 차이가 다시 섞이기 때문이다.

---

### Decision 6
**primary null은 source trial별 independent circular shift로 둔다.**

secondary null은 time shuffle로 둔다.

**이유**  
circular shift는 amplitude distribution과 시간적 smoothness를 어느 정도 보존하면서도,  
cross-muscle synchrony를 깨뜨릴 수 있어 해석이 더 좋다.

---

### Decision 7
**이번 턴의 실데이터 검증은 smoke run까지만 수행한다.**

구체적으로:

- thresholds = `0.89`, `0.90`, `0.91`
- primary null = `circular_shift`
- `null_repeats = 1`
- out-dir = `analysis/vaf_threshold_sensitivity/artifacts/validity_smoke_89_91`

**이유**  
구현 검증과 artifact contract 확인은 end-to-end smoke run으로 충분했다.  
반면 screening / exact run은 계산량이 더 크고, 결과 해석도 별도 검토가 필요하므로 다음 단계로 남겨 둔다.

---

## Outcomes & Retrospective / 완료 상태 정의

이 작업이 성공적으로 끝난 상태는 다음과 같다.

1. `analysis/vaf_threshold_sensitivity/` 내부에서 새 validation 스크립트가 실행된다.
2. `0.89`, `0.90`, `0.91` 각각에 대해
   - local VAF
   - null model
   - hold-out
   - cross-condition
   결과가 모두 생성된다.
3. `report.md`가 아래 질문에 답할 수 있어야 한다.
   - 90%에서 muscle-channel fit가 충분한가?
   - 90%가 fake/null보다 진짜 구조를 더 잘 보이는가?
   - 90% module이 unseen same-condition trial과 opposite-condition trial에도 일반화되는가?
4. 최종 결론이 “90% 유지 / 90% 약화 / 결론 유예” 중 하나로 분명히 끝난다.

현재 상태 메모:

- 구현 완료
- dry-run 완료
- smoke run 완료
- screening / exact run은 아직 미완료
- 따라서 현재 결론 상태는 **결론 유예**다.

---

## Context / 파일 구조와 방향

이번 작업은 모두 아래 폴더 안에서 진행한다.

- `analysis/vaf_threshold_sensitivity/`

새로 만드는 파일은 다음을 권장한다.

- `analysis/vaf_threshold_sensitivity/config_validation.yaml`
- `analysis/vaf_threshold_sensitivity/validation_helpers.py`
- `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py`
- `analysis/vaf_threshold_sensitivity/report.md`

artifact는 기존 `artifacts/` 하위에 추가한다.

예시:
- `analysis/vaf_threshold_sensitivity/artifacts/default_run/`
- `analysis/vaf_threshold_sensitivity/artifacts/validity_screening_89_91/`
- `analysis/vaf_threshold_sensitivity/artifacts/validity_exact_090/`

즉, 기존 broad sweep artifact는 그대로 두고,  
새 validation artifact를 같은 폴더 아래에 **추가**한다.

---

## Plan of Work / 작업 계획

이번 작업은 세 개의 독립 진단을 같은 입력과 같은 rank selection rule 위에 얹는 방식으로 만든다.

핵심 원칙은 다음과 같다.

- 같은 EMG 입력 사용
- 같은 metadata 사용
- 같은 mixed velocity trial selection 사용
- 같은 NMF rank cap 사용
- 같은 threshold-based minimal rank rule 사용
- 달라지는 것은 **추가 검증 레이어**뿐

구현 순서는 아래가 좋다.

1. config 작성
2. helper 함수 작성
3. dry-run
4. local VAF
5. null model
6. hold-out reconstruction
7. cross-condition reconstruction
8. summary serialization
9. report generation

---

## Detailed Method Rules / 세부 방법 규칙

# 1) Local VAF

## 1-1. Trialwise local VAF
trialwise mode에서는 각 trial을 하나의 unit으로 보고,  
선택된 rank에서 각 muscle channel별 local VAF를 계산한다.

이 단계는 “개별 trial 수준에서 어떤 muscle이 자주 망가지는가”를 보는 용도다.

---

## 1-2. Concatenated local VAF (수정된 핵심 규칙)

concatenated mode에서는 local VAF를 **두 층으로 나눠서** 계산한다.

### (A) 1차 지표: subject-muscle channel local VAF
같은 subject, 같은 mixed velocity, 같은 class의 source trial을 이어 붙여 만든 super-trial에서,  
각 muscle channel별 local VAF를 계산한다.

이 값이 concatenated local VAF의 **primary metric**이다.

이렇게 해야 “이 subject의 이 muscle channel이, 이 class-level 구조에서 전반적으로 잘 재구성되는가?”를 바로 볼 수 있다.

---

### (B) 2차 지표: source-trial split local VAF
super-trial의 reconstruction 결과를 다시 source trial 길이대로 잘라서,  
각 source trial × muscle channel local VAF를 계산한다.

이 값은 concatenated local VAF의 **secondary diagnostic**이다.

이 단계는 “겉으로는 잘 맞아 보이는데 실제로는 특정 source trial만 망가지는가?”를 확인하기 위한 것이다.

---

## 1-3. 왜 이 수정이 기존 계획과 충돌하지 않는가
기존 계획에서 “concatenated reconstruction은 source trial로 다시 잘라서 local VAF를 본다”는 문장은 틀린 내용이 아니다.  
다만 그 문장만 있으면, concatenated local VAF의 **1차 정의가 trial-level인 것처럼 오해**될 수 있다.

이제는 이렇게 정리하면 된다.

- 기존 문장 유지 가능
- 단, 앞에 다음 문장을 추가해야 함

> concatenated mode의 primary local VAF summary는 subject-muscle channel 기준으로 계산한다.  
> source-trial split local VAF는 hidden bad trial 탐지를 위한 secondary diagnostic으로 사용한다.

즉, **기존 내용은 삭제가 아니라 역할 축소**다.

---

## 1-4. local VAF 계산 규칙
local VAF는 기존 global VAF와 같은 reconstruction 결과를 써서 muscle별로 계산한다.

분산이 너무 작은 channel은 `not_applicable` 처리한다.

threshold별, mode별로 아래 요약치를 만든다.

- `muscle_pass_rate_75`
  - local VAF >= 0.75 비율
- `all_muscles_pass_rate_75`
  - 유효 muscle이 모두 0.75 이상인 unit 비율
- `min_local_vaf`
- `median_local_vaf`
- `worst_muscle_frequency`
  - 가장 자주 최저 fit가 되는 muscle 순위

concatenated mode에서는 이 요약치를 **두 세트**로 만든다.

- subject-muscle channel 기준 요약
- source-trial split 기준 요약

---

# 2) Shuffled / Surrogate Null Model

## 2-1. Primary null
source trial마다 muscle channel별로 독립적인 circular shift를 적용한다.

규칙:
- source trial 안에서만 shift
- trial boundary 넘어가면 안 됨
- 그 후에 concatenate

---

## 2-2. Secondary surrogate
source trial마다 muscle time axis permutation을 적용한다.

이건 primary null 보조 확인용이다.

---

## 2-3. Null 비교 방법
각 threshold에서 observed와 같은 rank selection rule을 null에도 그대로 적용한다.

즉,
- rank 1부터 cap까지 fit
- threshold를 처음 만족하는 최소 rank 선택

이 과정을 반복해서 null rank distribution을 만든다.

핵심 지표는 아래 두 개다.

### `compression_advantage`
`median(null_selected_rank) - observed_selected_rank`

값이 크면 observed가 null보다 더 적은 synergy로 설명된다는 뜻이다.

### `local_advantage`
`observed_muscle_pass_rate_75 - median(null_muscle_pass_rate_75)`

값이 크면 observed local fit가 null보다 좋다는 뜻이다.

subject-level summary를 기본으로 보고한다.

---

# 3) Hold-out Reconstruction

hold-out reconstruction은 “같은 전략 안에서 안 본 trial에도 W가 통하는가”를 본다.

분석 key는 다음과 같다.

- subject
- mixed velocity
- step_class

같은 class에서 trial 수가 2개 이상일 때만 leave-one-out 수행 가능하다.

절차:
1. trial 하나를 test로 뺀다.
2. 나머지를 concatenate하여 train super-trial 생성
3. train data에서 threshold별 최소 rank 선택
4. W_train 학습
5. test에서는 W_train 고정
6. H만 NNLS로 추정
7. global/local VAF 계산

반드시 eligible subject 수와 skipped subject 수를 저장한다.

---

# 4) Cross-condition Reconstruction

cross-condition reconstruction은
- step에서 학습한 W가 non-step을 설명하는지
- non-step에서 학습한 W가 step을 설명하는지
를 본다.

같은 subject, 같은 mixed velocity 안에서만 수행한다.

절차:
1. within-condition hold-out fold에서 얻은 W_train 사용
2. opposite-condition test trial 전체에 대해 fixed-W reconstruction 수행
3. direction을 둘 다 계산
   - step -> non-step
   - non-step -> step

저장할 지표:
- `within_test_global_vaf`
- `cross_test_global_vaf`
- `within_test_local_pass_rate_75`
- `cross_test_local_pass_rate_75`
- `cross_within_delta`
- `cross_within_ratio`

threshold 해석 원칙은 다음과 같다.

- 89%: 너무 적게 분해되어 within도 cross도 낮을 수 있음
- 91%: within은 조금 오르지만 cross penalty가 커지면 over-fragmentation 신호
- 90%: within 성능과 shared structure 보존의 타협점이면 가장 유리

---

## Concrete Execution Steps / 실제 실행 절차

작업 디렉터리: 저장소 루트

### Step 1. config 준비
새 validation config를 만든다.

예시 파일:
- `analysis/vaf_threshold_sensitivity/config_validation.yaml`

config에는 최소한 아래 값이 있어야 한다.

- thresholds: [0.89, 0.90, 0.91]
- local_vaf_floor: 0.75
- variance_epsilon
- null_methods
- null_repeats_screening
- null_repeats_exact
- holdout_min_trials
- seed
- out_dir

---

### Step 2. dry-run
먼저 dry-run을 돌려서 아래를 출력하게 한다.

- selected subject 수
- selected trial 수
- class별 trial 수
- hold-out eligible 수
- threshold 목록
- null 설정

예시:

```bash
conda run --no-capture-output -n module python \
  analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py \
  --config configs/global_config.yaml \
  --validation-config analysis/vaf_threshold_sensitivity/config_validation.yaml \
  --dry-run
````

---

### Step 3. screening run

`0.89`, `0.90`, `0.91`에 대해 primary null 100회 기준으로 screening run을 수행한다.

예시:

```bash
conda run --no-capture-output -n module python \
  analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py \
  --config configs/global_config.yaml \
  --validation-config analysis/vaf_threshold_sensitivity/config_validation.yaml \
  --thresholds 0.89 0.90 0.91 \
  --null-method circular_shift \
  --null-repeats 100 \
  --out-dir analysis/vaf_threshold_sensitivity/artifacts/validity_screening_89_91
```

---

### Step 4. exact 90% run

90% exact run에서는 null 반복 수를 늘리고, secondary surrogate도 같이 본다.

예시:

```bash
conda run --no-capture-output -n module python \
  analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_validity.py \
  --config configs/global_config.yaml \
  --validation-config analysis/vaf_threshold_sensitivity/config_validation.yaml \
  --thresholds 0.90 \
  --null-method circular_shift time_shuffle \
  --null-repeats 500 \
  --out-dir analysis/vaf_threshold_sensitivity/artifacts/validity_exact_090
```

---

### Step 5. report 작성

report는 반드시 아래 질문 구조로 쓴다.

1. 90%에서 subject-muscle channel local VAF가 충분한가?
2. 90% observed는 null보다 더 압축 가능한가?
3. 90% W는 unseen same-condition과 opposite-condition에도 일반화되는가?

그리고 마지막 섹션은 반드시 아래 비교로 끝난다.

* 89 vs 90 vs 91

---

## Validation and Acceptance / 합격 기준

### 1. dry-run이 정상 종료되어야 한다

trial selection count와 eligible count가 명확히 출력되어야 한다.

### 2. artifact가 생성되어야 한다

다음 파일이 생겨야 한다.

* `analysis/vaf_threshold_sensitivity/report.md`
* `analysis/vaf_threshold_sensitivity/artifacts/<run_name>/summary.json`
* `analysis/vaf_threshold_sensitivity/artifacts/<run_name>/checksums.md5`
* `analysis/vaf_threshold_sensitivity/artifacts/<run_name>/by_threshold/vaf_89/summary.json`
* `analysis/vaf_threshold_sensitivity/artifacts/<run_name>/by_threshold/vaf_90/summary.json`
* `analysis/vaf_threshold_sensitivity/artifacts/<run_name>/by_threshold/vaf_91/summary.json`

### 3. summary.json 필수 블록

아래 블록이 모두 있어야 한다.

* `local_vaf`
* `null_model`
* `holdout`
* `cross_condition`

### 4. concatenated local VAF는 반드시 두 층으로 저장해야 한다

* `subject_muscle_channel_summary`
* `source_trial_split_summary`

둘 중 하나만 있으면 불완전하다.

### 5. cross-condition은 양방향 다 있어야 한다

* step -> non-step
* non-step -> step

### 6. 90%를 미리 정답처럼 쓰면 안 된다

반드시 `89 / 90 / 91` 비교를 먼저 보여주고 결론을 써야 한다.

### 7. 재현성이 있어야 한다

같은 seed, 같은 설정이면 같은 결과가 나와야 한다.

---

## Idempotence / 재실행 안전성

이번 작업은 기존 broad sweep artifact를 보존한다.

즉,

* `analysis/vaf_threshold_sensitivity/artifacts/default_run/`는 건드리지 않는다.
* validation run은 새 artifact 폴더에만 쓴다.

출력 폴더를 지우고 같은 명령을 다시 돌렸을 때 결과가 같아야 한다.
다르면 seed 또는 null generation deterministic 문제가 있는 것이다.

---

## Interfaces / 추천 helper 함수

새 helper 파일:

* `analysis/vaf_threshold_sensitivity/validation_helpers.py`

추천 함수:

```python
def compute_local_vaf(x: np.ndarray, x_hat: np.ndarray, variance_epsilon: float) -> dict:
    """근육별 local VAF와 요약치 반환"""

def generate_null_trial(x: np.ndarray, method: str, rng: np.random.Generator) -> np.ndarray:
    """source trial 경계를 넘지 않는 null trial 생성"""

def solve_h_fixed_w(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    """W 고정 상태에서 NNLS로 H 추정"""

def reconstruct_with_fixed_w(x: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """fixed-W reconstruction 결과 반환"""

def split_concatenated_trial_matrix(x: np.ndarray, source_lengths: list[int]) -> list[np.ndarray]:
    """concatenated matrix를 source trial 단위로 다시 분리"""

def summarize_subject_muscle_channel_local_vaf(local_vaf_by_supertrial: list[dict]) -> dict:
    """concatenated super-trial의 subject-muscle channel local VAF 요약"""

def summarize_source_trial_split_local_vaf(local_vaf_by_split_trial: list[dict]) -> dict:
    """source trial split local VAF 요약"""
```

---

## Final Interpretation Rule / 최종 해석 규칙

최종 결론은 아래 순서로 판단한다.

### 1단계

90%가 89%보다

* subject-muscle channel local VAF를 개선하고,
* null 대비 compression advantage를 유지하거나 키우고,
* within-condition generalization도 개선하면

90%는 우선 유리하다.

### 2단계

91%가 90%보다 within fit는 조금 올려도,

* cross_within_delta가 커지거나
* cross_within_ratio가 낮아지거나
* source-trial split local VAF에서 불안정성이 커지면

91%는 over-fragmentation 신호로 본다.

### 3단계

90%가

* subject-muscle channel level에서 충분히 괜찮고,
* null보다 우월하고,
* unseen same-condition과 opposite-condition에도 지나치게 무너지지 않으면,

최종 결론은 **“90% 유지”**로 간다.

---

## Change Note / 변경 메모

Change Note (수정본):

1. concatenated local VAF에 대해 **subject-muscle channel 기준의 primary summary**를 추가했다.
2. 기존의 source-trial split local VAF는 삭제하지 않고 **secondary diagnostic**으로 재정의했다.
3. 따라서 기존 내용과 실질 충돌은 없다.
   단, 기존 문구가 source-trial split만을 concatenated local VAF의 유일한 정의처럼 읽히면 수정이 필요하다.
4. 모든 작업 경로를 새 폴더가 아니라 **`analysis/vaf_threshold_sensitivity/` 내부**로 변경했다.
5. 이번 추가분석은 기존 broad sweep 작업을 버리는 것이 아니라, **같은 폴더에서 이어서 확장하는 작업**으로 고정했다.

사용한 스킬: `document-writer`, `analysis-report`
