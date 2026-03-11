# CNN README

## 이 문서는 왜 필요한가?

이 문서는 현재 저장소에서 CNN 분석을 아주 쉽게 이해하기 위한 입문 안내서다.

지금 저장소에는 이미 `step`과 `nonstep`을 비교하는 EMG synergy 분석 흐름이 있다. CNN은 그 분석을 바로 대체하려는 것이 아니다. 같은 질문을 다른 방법으로 다시 보는 도구라고 이해하면 된다.

쉽게 말하면 CNN 쪽 질문은 아래와 같다.

"EMG 시계열 데이터를 모델에 보여주면, 그 모델이 step trial과 nonstep trial의 차이를 스스로 배울 수 있을까?"

즉, 실험 목적은 비슷하지만 보는 방식이 다르다.

## 이번 CNN 분석의 목표는 무엇인가?

이번 CNN 분석의 목표는 기존 synergy 분석과 같다.

- `step`과 `nonstep`을 비교한다.
- 같은 trial 개념을 사용한다.
- 같은 실험 의미를 유지한다.

다른 점은 분석 도구다.

- synergy 분석은 EMG를 몇 개의 대표 패턴으로 요약한다.
- CNN은 시간에 따라 변하는 EMG 패턴을 직접 보고 학습하려고 한다.

그래서 핵심 질문은 "CNN이 synergy보다 무조건 더 좋은가?"가 아니다.

더 좋은 질문은 아래와 같다.

"CNN은 EMG에서 어떤 패턴을 보고 step과 nonstep을 구분하는가? 그리고 그 관점이 synergy 분석과 어떻게 다른가?"

## 왜 `analysis/`에서 먼저 시작하나?

CNN은 이 저장소에서 아직 공식 파이프라인이라기보다 실험용 분석에 가깝다.

아직 확정되지 않은 것이 몇 가지 있다.

- 어떤 입력 데이터를 공식 입력으로 쓸지
- 시간 구간을 어떻게 고정 길이로 맞출지
- 어떤 성능 지표를 기본 보고 지표로 둘지
- 결과를 어떤 형태의 공식 산출물로 남길지

이 상태에서 CNN을 바로 메인 파이프라인에 넣으면 기존 synergy 흐름까지 같이 흔들릴 수 있다.

그래서 지금 단계에서는 `analysis/`에서 시작하는 것이 더 안전하다.

정리하면 아래와 같다.

- `scripts/`와 `src/synergy_stats/`는 현재 안정된 공식 흐름이다.
- `analysis/`는 CNN처럼 아직 실험과 비교가 필요한 주제를 올리기에 적절한 공간이다.

## 지금 고려하는 입력 데이터는 무엇인가?

이번 1차 범위에서는 두 가지 입력을 생각한다.

### 1. Raw EMG data

이것은 현재 프로젝트 스타일의 정규화가 들어가기 전, 더 원본에 가까운 EMG 신호를 뜻한다.

장점은 분명하다.

- 가장 원래 신호에 가깝다.
- 진폭, 타이밍, 파형 모양 정보를 많이 유지한다.

하지만 처음 시작하기에는 어려운 점도 있다.

- 사람마다 신호 크기 차이가 매우 클 수 있다.
- 노이즈 처리의 중요성이 커진다.
- 현재 메인 설정 파일에는 raw EMG parquet 경로가 명확히 잡혀 있지 않다.

그래서 raw EMG는 분명 가치가 있지만, 첫 CNN 실험에서는 다루기 더 어렵다.

### 2. Normalized EMG data

이것은 trial 간 또는 subject 간 비교를 쉽게 하도록 크기를 조정한 EMG 데이터다.

현재 저장소에서 바로 확인되는 입력은 min-max normalized parquet이다.

관련 설정 파일:

- `configs/global_config.yaml`

normalized EMG가 첫 실험에 좋은 이유는 아래와 같다.

- 현재 저장소 입력과 바로 연결된다.
- 사람 간 큰 amplitude 차이를 어느 정도 줄일 수 있다.
- 파형의 모양과 timing 차이에 더 집중하기 쉽다.

## 정규화는 하나만 있는 것이 아니다

"normalized"라고 해서 항상 같은 의미는 아니다.

대표적으로 아래처럼 나뉜다.

- min-max normalization
- MVC normalization

둘은 완전히 같은 것이 아니다.

### min-max normalization

보통 값의 범위를 일정 구간으로 맞추는 방식이다.

장점:

- 모델 입력을 다루기 쉽다.
- 채널 간 스케일 차이를 줄이기 좋다.

주의점:

- 절대적인 근활성 크기 의미가 약해질 수 있다.
- 모양 중심 비교로 기울 수 있다.

### MVC normalization

MVC는 `maximum voluntary contraction`의 약자다.

보통 특정 기준 수축값을 기준으로 EMG 크기를 나누는 방식이다. 생리학적으로는 min-max보다 더 해석이 잘 되는 경우가 많다.

하지만 중요한 점이 있다.

현재 저장소에서 바로 보이는 것은 min-max normalized 입력이지, MVC 기반 CNN 입력이 확인된 것은 아니다.

그래서 이번 문서 기준으로는 아래처럼 이해하면 된다.

- min-max normalized EMG: 지금 바로 시작하기 가장 현실적인 입력
- MVC normalized EMG: 나중에 source data와 절차가 확보되면 확장 가능한 입력

## 이번 CNN의 가장 단순한 작업은 무엇인가?

가장 쉬운 첫 작업은 trial 하나를 보고 `step`인지 `nonstep`인지 맞히는 것이다.

즉, CNN은 우선 이진 분류기(binary classifier)로 시작한다.

쉽게 쓰면:

- 입력: 한 trial의 EMG 시계열
- 출력: `step` 또는 `nonstep`

이렇게 시작하면 문제 정의가 분명하고, 기존 synergy 분석과도 비교하기 쉽다.

## 여기서 trial은 무엇을 뜻하나?

CNN이라고 해서 trial 정의를 새로 만들 필요는 없다.

현재 저장소는 이미 trial window를 정리하는 로직을 갖고 있다.

- 시작점은 `platform_onset`
- 종료점은 `analysis_window_end`
- label은 event metadata 기반으로 준비된다

관련 파일:

- `src/emg_pipeline/io.py`
- `src/emg_pipeline/trials.py`

이 점이 중요한 이유는, CNN이 기존 synergy 분석과 완전히 다른 trial 정의를 쓰기 시작하면 결과 비교 자체가 어려워지기 때문이다.

즉, 방법은 달라도 trial 의미는 최대한 같게 유지하는 편이 좋다.

여기서 더 중요한 점이 하나 있다.

CNN의 filtering logic도 기존 synergy 분석과 동일해야 한다.

즉, CNN은 편의를 위해 새로운 trial selection rule을 따로 만들면 안 된다. 기존 synergy 분석에서 쓰는 `mixed comparison` 기반 filtering, `analysis_selected_group`, step/nonstep 판정 기준, 그리고 분석 window 정의를 그대로 따라야 한다.

쉽게 말하면 아래 원칙이다.

- synergy 분석에 들어가는 trial만 CNN 비교 후보로 본다.
- synergy 분석에서 제외된 trial은 CNN에서도 기본적으로 제외한다.
- 이렇게 해야 두 분석 결과를 같은 실험 맥락에서 비교할 수 있다.

## 왜 NMF 결과를 첫 CNN 입력으로 쓰지 않나?

NMF 결과는 의미가 있지만, 질문이 조금 달라진다.

NMF를 먼저 적용하면 CNN은 raw 또는 normalized EMG 시계열 자체를 직접 보는 것이 아니라, 이미 한 번 요약된 특징을 보게 된다.

그것도 나중에는 유용할 수 있다. 하지만 첫 CNN 실험으로는 가장 깔끔한 시작점이 아니다.

그래서 현재 1차 범위는 아래처럼 잡는다.

- 첫 CNN 비교는 raw EMG와 normalized EMG 중심으로 본다.
- synergy/NMF 출력은 이번 첫 입력 후보에서 제외한다.

이렇게 해야 CNN 분석이 기존 synergy 표현과 섞이지 않고 독립적인 의미를 가질 수 있다.

## 첫 실험은 어떤 모습이 좋나?

처음부터 복잡하게 갈 필요는 없다.

가장 무난한 첫 버전은 아래와 같다.

1. 기존 synergy와 같은 `step vs. nonstep` 목표를 쓴다.
2. 기존 trial window 로직을 그대로 따른다.
3. 가능한 범위에서 raw EMG와 normalized EMG를 비교한다.
4. 작은 1D CNN부터 시작한다.
5. 성능 평가는 subject-wise split으로 한다.

여기서 subject-wise split은 같은 사람이 train과 test에 동시에 들어가지 않게 나누는 방식이다.

이게 중요한 이유는, 그렇지 않으면 모델이 진짜 `step/nonstep` 차이를 배우는 대신 "이 사람의 EMG 스타일"을 외워버릴 수 있기 때문이다.

## 특히 조심해야 할 점

### 1. CNN과 synergy를 너무 빨리 섞지 말 것

CNN은 먼저 독립된 분석 가지로 시작하는 것이 좋다.

처음부터 synergy 결과와 섞으면 어떤 결과가 어떤 표현에서 나온 것인지 해석이 어려워질 수 있다.

### 2. 높은 accuracy를 너무 빨리 믿지 말 것

정확도가 높다고 항상 좋은 모델은 아니다.

subject leakage, trial leakage, preprocessing artifact 때문에 성능이 과장될 수도 있다.

### 3. 첫 모델은 단순하게 갈 것

처음부터 깊고 복잡한 모델을 쓰면 디버깅이 어려워진다.

첫 단계에서는 작고 이해하기 쉬운 CNN이 더 낫다.

## 지금 시점의 실전 추천

바로 구현을 시작한다면 순서는 아래가 가장 현실적이다.

1. `analysis/` 아래에 CNN 전용 실험 구조를 만든다.
2. 현재 연결 가능한 입력인 min-max normalized EMG부터 시작한다.
3. 같은 구조 안에 raw EMG를 나중에 붙일 수 있게 설계한다.
4. 기존 synergy 파이프라인은 건드리지 않은 채 결과를 비교한다.

이 방식의 장점은 명확하다.

- 기존 공식 파이프라인을 보호할 수 있다.
- CNN 실험 설계를 자유롭게 바꿔볼 수 있다.
- 나중에 구조가 안정되면 pipeline 승격도 검토할 수 있다.

## 한 줄 요약

이 저장소에서 CNN은 우선 `analysis/` 아래의 별도 실험 흐름으로 시작하고, 기존 synergy 분석과 같은 step vs. nonstep trial 의미를 유지한 채 raw EMG와 normalized EMG를 직접 입력으로 비교하는 방향이 가장 자연스럽다.
