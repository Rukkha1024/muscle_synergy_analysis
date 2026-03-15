---
name: plot-bos-com-xy-gif
description: Generate BOS+COM XY overlay visualizations (static PNG and animated GIF) from replace_V3D outputs to see where COM lies relative to BOS over time. Use when asked for "BOS/COM gif", "COM inside/outside BOS", step vs nonstep comparisons, right/left foot stepping trials (step_R/step_L), CCW 90-degree view rotation to match the experiment view, or when you need BOS-freeze at step_onset while keeping COM visible to the end. Uses `scripts/plot_bos_com_xy_sample.py`, `output/all_trials_timeseries.csv`, and optionally reads trial state from `data/perturb_inform.xlsm` (platform sheet).
---

# Plot Bos Com Xy Gif

## 핵심 아이디어(1문장)

`BOS 사각형(프레임별 min/max) + COM 궤적(누적+현재점)`을 같은 XY 평면에 겹쳐서, 시간에 따른 COM의 BOS 내부/외부 위치를 PNG/GIF로 빠르게 확인한다.

## Source Of Truth

- 구현 스크립트: `scripts/plot_bos_com_xy_sample.py`
- 입력 CSV(기본): `output/all_trials_timeseries.csv`
- 이벤트/상태 워크북(기본): `data/perturb_inform.xlsm` (`platform` 시트의 `state`로 step_R/step_L/nonstep 표시)
- 출력 폴더(기본): `output/figures/bos_com_xy_sample/`

이 스킬은 위 파일/경로/로직을 “표준 실행 절차”로 고정해서 반복 생산을 빠르게 하는 목적이다. 스크립트를 복제하지 말고, 필요한 경우에만 `scripts/plot_bos_com_xy_sample.py`를 수정한다.

## Quick Start

### 1) 특정 1 trial GIF 생성 (권장 기본)

```bash
conda run -n module python scripts/plot_bos_com_xy_sample.py \
  --subject 조민석 --velocity 30 --trial 2 \
  --step_vis phase_bos
```

기본값으로 아래가 적용된다.

- `--csv output/all_trials_timeseries.csv`
- `--event_xlsm data/perturb_inform.xlsm`
- `--rotate_ccw_deg 90`
- `--fps 20`, `--frame_step 1`, `--dpi 180`
- `--save_gif` 기본 True (`--no-save_gif`로만 비활성화 가능)
- BOS 모드는 live-only이며 freeze 출력은 생성하지 않음

### 2) right1col GIF 생성 (`--step_vis none`)

```bash
conda run -n module python scripts/plot_bos_com_xy_sample.py \
  --subject 이재유 --velocity 20 --trial 1 \
  --step_vis none
```

### 3) Nonstep(또는 footlift) trial GIF 생성

```bash
conda run -n module python scripts/plot_bos_com_xy_sample.py \
  --subject 조민석 --velocity 30 --trial 6 \
  --step_vis phase_bos
```

## 입력 요구사항

### CSV: `output/all_trials_timeseries.csv`

`scripts/plot_bos_com_xy_sample.py`는 아래 컬럼이 최소로 필요하다.

- Trial key: `subject`, `velocity`, `trial`
- Time index: `MocapFrame`
- Events (trim 구간/마커): `platform_onset_local`, `platform_offset_local`, `step_onset_local`
- COM: `COM_X`, `COM_Y`
- BOS 사각형 bounds: `BOS_minX`, `BOS_maxX`, `BOS_minY`, `BOS_maxY`

옵션 컬럼:

- `time_from_platform_onset_s`가 있으면 GIF 좌상단 패널에 시간(`t=... s`)을 함께 출력한다.

필수 컬럼 누락 시 즉시 에러로 종료한다. (입력 CSV가 “pipeline 결과물”이므로, 이 스크립트는 입력 보정을 하지 않는다.)

### XLSM(상태 표시용): `data/perturb_inform.xlsm`

`--show_trial_state`가 켜져 있으면(기본 True) `platform` 시트의 아래 컬럼을 읽어서 title subtitle로 표시한다.

- `subject`, `velocity`, `trial`, `state`

`state`는 아래 값을 기대한다.

- `step_R`, `step_L`, `nonstep`, `footlift`

값이 다르거나 매칭 행이 없으면 경고 후 `trial_type=unknown`으로 표시한다. (플롯 생성 자체는 진행)

## Trial 선택 규칙 (중요)

- `--subject --velocity --trial`을 모두 주면 해당 trial을 그린다.
- 일부만 주면 에러로 종료한다 (모호성 방지).
- 셋 다 미지정이면 `(subject, velocity, trial)` 정렬 기준 “첫 trial”을 자동 선택한다.

## 좌표/축/뷰(회전) 규칙

- 이 스크립트는 “표시용(display) 좌표”를 따로 만든다.
- `--rotate_ccw_deg`로 화면을 CCW(반시계)로 0/90/180/270도 회전할 수 있다.
- 기본값은 `--rotate_ccw_deg 90`이며, 플롯 title에 `view=CCW90`처럼 명시된다.

회전은 “데이터 자체 수정”이 아니라, 플롯 표시를 위해 COM과 BOS bounds 모두에 동일 변환을 적용한다.

- 회전 로직: `scripts/plot_bos_com_xy_sample.py:359` (`rotate_xy`)
- BOS bounds 회전: `scripts/plot_bos_com_xy_sample.py:372` (`rotate_box_bounds`)

### Axis label (앞/뒤/좌/우)

축 라벨은 “회전 후 표시 좌표 기준”으로 다음을 사용한다.

- X: `X (m) [- Left / + Right]`
- Y: `Y (m) [+ Anterior / - Posterior]`

라벨 위치: `scripts/plot_bos_com_xy_sample.py:614`, `scripts/plot_bos_com_xy_sample.py:744`

## Inside / Outside 판정

프레임별로 아래 조건을 만족하면 inside로 판정한다.

- `BOS_minX <= COM_X <= BOS_maxX` and `BOS_minY <= COM_Y <= BOS_maxY`

구현 위치: `scripts/plot_bos_com_xy_sample.py:313`

유효 프레임(valid frame) 정의:

- COM/BOS가 NaN/Inf가 아닌 프레임
- `BOS_min <= BOS_max` bounds 순서가 정상인 프레임

유효 프레임 필터링 위치: `scripts/plot_bos_com_xy_sample.py:300`

## PNG(정적) 구성

정적 PNG는 “trial 전체를 한 장”으로 요약한다.

- 모든 유효 프레임의 BOS 사각형 외곽선을 얇게 누적 오버레이(연한 회색)
- COM 전체 궤적(파랑) + inside/outside 점 분리(초록/빨강)
- 이벤트 프레임 점 마커 강조:
  - `platform_onset`: 검정 원
  - `platform_offset`: 주황 사각형
  - `step_onset`: 보라 삼각형 (step_onset이 null이면 생략)

## GIF(애니메이션) 구성

GIF는 “프레임별로 BOS + 누적 COM + 현재 COM 상태”를 보여준다.

- BOS: 반투명 하늘색 fill + 경계선
- COM 누적 궤적: 시작~현재 프레임까지 계속 연장
- 현재 COM 점: inside=초록, outside=빨강
- 좌상단 패널: frame/time/status/event/bos 상태 및 inside ratio

### Step trial에서 BOS freeze (step_onset 이후)

요구사항: step이면 BOS는 step_onset에서 멈추고(COM은 끝까지 계속) nonstep은 예외로 BOS가 계속 갱신.

- `step_onset_local`이 존재하면(step trial로 간주) step_onset 시점의 BOS bounds를 찾아 그 이후 프레임에서 고정한다.
- `step_onset_local`이 null이면(nonstep) BOS는 매 프레임 갱신된다.

구현 위치: `scripts/plot_bos_com_xy_sample.py:653`

## 출력 파일 규칙

기본 출력 경로:

- `output/figures/bos_com_xy_sample/`

파일명:

- `<subject>__velocity-<v>__trial-<n>__bos_com_xy_static.png`
- `<subject>__velocity-<v>__trial-<n>__bos_com_xy_anim.gif`

suffix는 `--png_name_suffix`, `--gif_name_suffix`로 바꿀 수 있다.

## “오른발(step_R)만” trial 찾는 방법

이 스크립트는 trial을 자동으로 step_R만 골라주진 않는다. (trial state는 “표시용”)

빠른 방법(추천): `data/perturb_inform.xlsm`의 `platform` 시트에서

- `subject == <이름>`
- `state == step_R`

인 행을 찾아 `velocity/trial`을 그대로 CLI에 넣는다.

터미널에서 빠르게 조회(예시):

```bash
conda run -n module python -c \"import pandas as pd; df=pd.read_excel('data/perturb_inform.xlsm', sheet_name='platform'); df=df[['subject','velocity','trial','state']]; print(df[(df['subject'].astype(str).str.strip()=='조민석') & (df['state'].astype(str).str.strip()=='step_R')].sort_values(['velocity','trial']).to_string(index=False))\"
```

## 재현성/검증(권장)

### 1) 생성 확인

- PNG/GIF 파일 존재 확인
- 콘솔에 trial 선택/valid 통계/inside 비율/저장 경로 로그가 나오는지 확인

### 2) MD5 재현성 확인(동일 인자 2회 실행)

```bash
md5sum output/figures/bos_com_xy_sample/*.png output/figures/bos_com_xy_sample/*.gif | sort
```

같은 명령을 동일 인자로 다시 실행했을 때 MD5가 변하면 비결정성 원인이 있는지 확인한다.

## 자주 나는 문제와 대응

- `Missing required columns: ...`
  - 원인: 입력 CSV가 기대 컬럼을 포함하지 않음.
  - 대응: `output/all_trials_timeseries.csv`를 생성하는 upstream pipeline을 먼저 점검.
- `Event workbook not found: ...`
  - 원인: `data/perturb_inform.xlsm` 경로가 다름.
  - 대응: `--event_xlsm`로 올바른 xlsm 경로 지정, 또는 `--no-show_trial_state`로 상태표시를 끄고 진행.
- `No valid frame remains ...`
  - 원인: COM/BOS가 전부 NaN이거나 BOS bounds가 전부 뒤집힘(min>max).
  - 대응: 입력 생성 단계(BOS/COM 계산)부터 확인 필요.

## 더 깊은 설계/코드 포인터

상세 설계/코드 포인터는 `references/bos-com-xy-gif-design.md`를 참고한다.
