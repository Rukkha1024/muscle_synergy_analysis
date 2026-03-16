# `main.py` 콘솔 로그를 구조화된 중간 결과 형태로 개선

이 ExecPlan은 살아 있는 문서다. `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective` 섹션은 작업 진행에 따라 계속 갱신해야 한다.

이 저장소에는 `.agents/PLANS.md`가 있으며, 이 문서는 그 파일 규칙에 맞춰 유지한다. 이 계획서는 현재 워킹트리와 이 파일만 가진 초보 구현자도 끝까지 따라갈 수 있게 작성한다.

## Purpose / Big Picture

EMG 시너지 파이프라인은 이미 실행 로그를 남기고 있지만, 현재 콘솔 출력은 너무 짧아서 사용자가 `python main.py` 실행 중에 각 단계가 정상적으로 진행되는지 바로 확인하기 어렵다. 지금은 step 시작 여부 정도만 알 수 있을 뿐, 병합된 EMG 테이블 크기, 선택된 trial 수, NMF rank 및 VAF 요약, clustering 선택 결과, export 범위를 실행 중에 빠르게 검증할 수 없다.

이 변경 후에는 `python main.py --overwrite --out outputs/runs/console_log_structured` 실행 시 계산 산출물은 그대로 유지하면서도, 콘솔과 run log에 각 step이 구분선과 정렬된 key-value 블록으로 출력된다. 사용자는 노트북, CSV, Excel 파일을 열지 않아도 실행 중간 상태를 바로 확인할 수 있다.

## Progress

- [x] (2026-03-16 09:30Z) 현재 `main.py` 기준 활성 파이프라인이 6단계가 아니라 5단계임을 확인했다.
- [x] (2026-03-16 09:40Z) `main.py`와 `scripts/emg/01_load_emg_table.py`부터 `scripts/emg/05_export_artifacts.py`까지 현재 logging 호출을 검토했다.
- [x] (2026-03-16 09:50Z) `scripts/emg/06_render_figures_only.py`는 메인 파이프라인이 아니라 별도 figure rerender 유틸리티 CLI임을 확인했다.
- [x] (2026-03-16 10:00Z) `bundle.meta`, `cluster_result`, export artifact 경로에 이미 요약용 메타데이터가 충분히 있어 계산 로직 변경 없이 logging-only 구현이 가능함을 확인했다.
- [x] (2026-03-16 11:52Z) 수정 전 짧은 형식 로그를 기준선으로 남기기 위해 `outputs/runs/console_log_baseline` baseline run을 생성했다.
- [x] (2026-03-16 11:55Z) `src/emg_pipeline/log_utils.py`를 추가하고 `main.py`에 동적 step 배너와 step별 elapsed time 로그를 넣었다.
- [x] (2026-03-16 11:58Z) `scripts/emg/01_load_emg_table.py`부터 `scripts/emg/05_export_artifacts.py`까지의 1줄 요약 로그를 구조화된 섹션으로 교체했다.
- [x] (2026-03-16 12:15Z) `outputs/runs/console_log_structured`로 파이프라인을 다시 실행하고 `logs/run.log`에서 구조화 섹션 출력을 확인했다.
- [x] (2026-03-16 12:16Z) `scripts/emg/99_md5_compare_outputs.py`를 실행해 `MD5 comparison passed for curated stable files.` 결과를 확인했다.
- [x] (2026-03-16 12:20Z) 이 한국어 계획서와 영어 동반 계획서에 구현 증거, 최종 결정, 회고를 반영했다.

## Surprises & Discoveries

- Observation: 현재 활성 파이프라인은 `main.py`의 5개 step이며, `scripts/emg/06_render_figures_only.py`는 step-count 배너에 포함되면 안 되는 별도 유틸리티다.
  Evidence: `main.py`의 `STEP_FILES`는 `01_*`부터 `05_*`까지만 포함하고, `06_render_figures_only.py`는 자체 argument parser를 가진 독립 CLI다.

- Observation: 멀티라인 문자열 하나를 `logging.info()`에 넘기면 첫 줄만 타임스탬프와 logger 메타데이터가 붙는다.
  Evidence: Python `logging`의 기본 formatter 동작이며, 줄별 logging이 콘솔과 `run.log` 모두에서 grep하기 더 쉽다.

- Observation: Step 3는 이미 trial별 `n_components`, `vaf`, `extractor_backend`, `extractor_torch_device`, `extractor_torch_dtype`, `extractor_metric_elapsed_sec`를 저장한다.
  Evidence: `src/synergy_stats/nmf.py`의 `extract_trial_features()`가 `FeatureBundle.meta`에 해당 키를 기록한다.

- Observation: Step 4 clustering 결과에는 이미 `selection_status`, `k_gap_raw`, `k_selected`, `duplicate_trials`, `algorithm_used`, `inertia`가 포함된다.
  Evidence: `src/synergy_stats/clustering.py`의 `cluster_feature_group()` 반환 dict에 해당 필드가 존재한다.

- Observation: Step 5는 `src/synergy_stats/artifacts.py` 내부에서 workbook 경로와 workbook validation 로그를 이미 출력한다.
  Evidence: `export_results()`가 step 스크립트로 돌아오기 전에 workbook 저장 위치와 validation summary를 logging한다.

- Observation: 이 저장소의 실제 실행 명령은 bare `python`이 아니라 `conda run -n cuda python ...`이다.
  Evidence: 첫 baseline 시도에서 `python main.py ...`는 PATH에 `python`이 없어 실패했고, `conda run -n cuda python ...` 명령으로 baseline run과 structured run이 모두 성공했다.

- Observation: export가 끝난 실제 run 디렉터리에는 curated stable CSV 8개 외에 cross-group similarity CSV 2개가 더 있어서 CSV 총개수는 10개다.
  Evidence: `outputs/runs/console_log_structured`에는 `cross_group_w_pairwise_cosine.csv`, `cross_group_w_cluster_decision.csv`가 추가로 생성되었다.

- Observation: run 디렉터리 안에는 parquet가 없고, 유일한 parquet 산출물은 run 디렉터리 밖의 `outputs/final.parquet`에 기록된다.
  Evidence: `src/emg_pipeline/config.py`가 `runtime.final_parquet_path`를 `outputs/final.parquet`로 고정하고 있으며, 구현된 Step 5 summary는 이 artifact를 별도로 집계해 Parquet total `1`을 보여준다.

## Decision Log

- Decision: 계획서를 실제 5-step 파이프라인 기준으로 다시 쓰고, `scripts/emg/06_render_figures_only.py`는 범위 밖으로 둔다.
  Rationale: ExecPlan은 현재 저장소 상태와 일치해야 초보 구현자가 모순 없이 실행할 수 있다.
  Date/Author: 2026-03-16 / Codex

- Decision: 구현 범위는 logging-only로 제한하고, 로딩/trial slicing/NMF/clustering/export 계산 로직은 바꾸지 않는다.
  Rationale: 사용자에게 필요한 것은 실행 중 가시성 향상이지, 파이프라인 계산 동작 변경이 아니다.
  Date/Author: 2026-03-16 / Codex

- Decision: 표준 라이브러리 `logging`만 사용하고 `src/emg_pipeline/log_utils.py`에 작은 공통 헬퍼를 둔다.
  Rationale: 기존 logging 설정이 이미 콘솔과 파일을 동시에 처리하므로, 의존성 추가 없이 형식만 일관되게 맞추면 된다.
  Date/Author: 2026-03-16 / Codex

- Decision: 화면에 보이는 각 줄마다 별도의 `logging.info()` 호출을 사용한다.
  Rationale: 모든 줄에 타임스탬프가 붙어야 콘솔과 `run.log` 모두에서 읽기 쉽고 grep하기 쉽다.
  Date/Author: 2026-03-16 / Codex

- Decision: 배너의 총 step 수는 하드코딩하지 않고 `len(STEP_FILES)`에서 계산한다.
  Rationale: 나중에 step 목록이 바뀌어도 다시 숫자 drift가 생기지 않게 한다.
  Date/Author: 2026-03-16 / Codex

- Decision: `src/synergy_stats/artifacts.py`가 이미 출력하는 workbook 로그는 그대로 두고, Step 5 스크립트에서 구조화된 export summary만 추가한다.
  Rationale: 해당 workbook 로그는 이미 유용한 검증 정보이며, 이번 계획이 정리하려는 반복 포맷 문제와는 성격이 다르다.
  Date/Author: 2026-03-16 / Codex

- Decision: 산출물 무변경 검증은 임의의 2개 파일 해시 대신 저장소에 이미 있는 `scripts/emg/99_md5_compare_outputs.py`를 사용한다.
  Rationale: 이 스크립트가 안정 산출물 집합을 이미 정의하고 있어 logging-only 변경의 pass/fail 근거로 더 적절하다.
  Date/Author: 2026-03-16 / Codex

- Decision: Step 5의 CSV count는 curated MD5 대상 8개가 아니라, 실제 run 디렉터리에 생성된 CSV 전체 개수를 그대로 보여준다.
  Rationale: 구조화 export summary의 목적은 MD5 비교 집합만이 아니라 사용자가 이번 run에서 실제로 만들어진 파일 범위를 즉시 확인하게 하는 데 있다.
  Date/Author: 2026-03-16 / Codex

- Decision: Step 5 summary는 run 디렉터리 밖에 쓰이는 최종 parquet artifact도 포함해 집계한다.
  Rationale: 사용자는 export summary에서 최종 parquet 존재 여부를 함께 확인하길 기대하며, 현재 파이프라인은 `outputs/final.parquet`에 parquet 1개를 기록한다.
  Date/Author: 2026-03-16 / Codex

## Outcomes & Retrospective

구현은 완료되었다. 파이프라인은 이제 5개 step 배너, Step 1~5의 구조화 summary, step별 elapsed time을 콘솔과 `run.log`에 함께 출력한다. 최종 검증에서 stable 산출물 MD5가 baseline과 완전히 일치했으므로, 이번 변경은 계산 결과를 바꾸지 않고 실행 중 가시성만 개선했다.

## Context and Orientation

이 저장소는 EMG(근전도) 시너지 추출 파이프라인을 담고 있다. 메인 진입점은 `main.py`이며, YAML 설정을 읽고 실행 디렉터리를 준비한 뒤 logging을 구성하고 아래 5개 스크립트를 순서대로 실행한다.

    scripts/emg/01_load_emg_table.py
        EMG parquet와 이벤트 workbook 메타데이터를 읽어 하나의 EMG 테이블로 병합한다.

    scripts/emg/02_extract_trials.py
        병합된 EMG 테이블을 `subject-velocity-trial` 단위 window record로 자른다.

    scripts/emg/03_extract_synergy_nmf.py
        각 trial에 대해 NMF(비음수 행렬 분해)를 수행해 `W` 근육 가중치 행렬과 `H` 시간 활성화 행렬을 만든다.

    scripts/emg/04_cluster_synergies.py
        추출된 시너지 성분을 global `step`, `nonstep` 그룹으로 gap statistic 기반 clustering 한다.

    scripts/emg/05_export_artifacts.py
        최종 CSV, parquet, Excel, figure 산출물을 run 디렉터리에 내보낸다.

`scripts/emg/06_render_figures_only.py`도 존재하지만, 이것은 기존 run 디렉터리에서 figure만 다시 그리는 별도 유틸리티 명령이다. `main.py`에서 실행되지 않으며 이번 계획 범위에 포함하지 않는다.

현재 logging 설정은 `main.py`에 있다. `logging.basicConfig()`가 INFO 레벨 formatter, `FileHandler`, `StreamHandler`를 함께 사용하므로, 하나의 `logging.info()` 호출은 콘솔과 `outputs/runs/<run_id>/logs/run.log`에 동시에 기록된다.

현재 사용자 문제는 파이프라인이 실패한다는 것이 아니다. 문제는 보이는 로그가 너무 짧다는 점이다. 지금은 `main.py`가 "Running step" 한 줄을 남기고, 각 step 스크립트도 보통 한 줄 요약만 남긴다. 이 정도로는 데이터 볼륨, 선택된 trial 수, NMF 요약 품질, clustering 선택 결과, export 범위를 실행 중에 판단하기 어렵다.

이 계획서에서 사용하는 용어는 아래와 같다.

`NMF`: Non-negative Matrix Factorization. 이 저장소에서는 trial EMG 행렬을 시너지 weight `W_muscle`과 시간 활성화 `H_time`으로 분해한다.

`VAF`: Variance Accounted For. NMF 복원이 원본 EMG를 얼마나 잘 설명하는지를 나타내는 0~1 사이 수치다. 클수록 좋다.

`Rank`: 한 trial에서 선택된 시너지 성분 수다. 코드에서는 `n_components`로 저장된다.

`Gap statistic`: 관측된 clustering 품질과 무작위 기준 데이터를 비교해 클러스터 수 `K`를 고르는 방법이다.

`Stable outputs`: `scripts/emg/99_md5_compare_outputs.py`가 비교하는 exported 파일 집합이다. logging-only 수정이라면 이 파일들은 바이트 단위로 동일해야 한다.

## Plan of Work

먼저 코드를 수정하기 전에 baseline run을 확보한다. `outputs/runs/console_log_baseline` 같은 전용 출력 디렉터리를 사용하고, `--overwrite`로 깨끗한 상태에서 현재 파이프라인을 실행한다. 이 baseline은 구현 후에도 계산 산출물이 바뀌지 않았음을 증명하는 기준점이 된다.

그다음 `src/emg_pipeline/log_utils.py`를 새로 만든다. 이 파일은 내부에서 `logging.info()`를 호출하는 아주 작은 포맷 헬퍼만 제공하면 된다. 헬퍼는 실행 상태를 저장하지 말고, 빈 줄, 구분선, 제목 줄, 정렬된 key-value 줄만 출력하도록 단순하게 유지한다. 목적은 `main.py`와 5개 step 스크립트에서 동일한 출력 형식을 재사용하는 것이다.

이후 `main.py`를 수정한다. 다섯 step 파일명을 사람이 읽기 쉬운 제목으로 바꾸는 매핑을 추가하고, 현재의 `Running step: ...` 로그를 step 배너 호출로 교체한다. `run_step(context)` 앞뒤로 wall-clock 시간을 재고, 각 step 완료 후 소요 시간을 출력한다. 기존 설정 로딩, manifest 작성, dry-run 처리, 성공/실패 동작은 그대로 둔다.

그리고 5개 step 스크립트의 1줄 요약 로그를 구조화된 섹션으로 바꾼다.

`scripts/emg/01_load_emg_table.py`는 두 개 섹션을 출력한다. 첫 번째 섹션은 병합된 EMG 테이블 요약으로, row 수, column 수, 선택된 subject 수와 이름, velocity 값, 설정된 muscle channel 수, 해당 muscle column 기준 결측치 수와 비율, EMG 최솟값과 최댓값을 포함한다. 두 번째 섹션은 이미 병합된 selection/event 메타데이터 요약으로, event row 수, selected trial 수, selected step/nonstep trial 분포, surrogate window end를 사용한 selected row 수와 actual window end를 사용한 row 수를 포함한다.

`scripts/emg/02_extract_trials.py`는 추출된 `trial_records`를 한 개 섹션으로 요약한다. trial 수, device frame 기준 duration 최소/최대, 포함된 subject 수와 이름, 포함된 velocity 값을 출력한다.

`scripts/emg/03_extract_synergy_nmf.py`는 trial별 계산 로직은 그대로 두고 runtime 및 summary 로그를 구조화한다. runtime 섹션에는 requested backend, resolved Torch device, resolved Torch dtype을 출력한다. summary 섹션에는 완료된 `feature_rows`를 모아 trial 수, rank distribution, VAF range, VAF mean 및 standard deviation, 총 component 수, 평균 trial 처리 시간, 실제 사용 backend 집합을 출력한다.

`scripts/emg/04_cluster_synergies.py`는 runtime 한 줄과 per-group 결과 한 줄을 구조화된 섹션으로 바꾼다. runtime 섹션에는 clustering algorithm, Torch device, Torch dtype, restart batch size, gap-reference batch size를 출력한다. 그리고 `context["cluster_group_results"]`의 각 group마다 별도 섹션을 찍어 `k_gap_raw`, `k_selected`, `selection_status`, duplicate-trial count, inertia, 실제 사용 algorithm을 보여준다.

`scripts/emg/05_export_artifacts.py`는 `export_results(context)` 호출은 그대로 둔다. 그 뒤에 깨끗한 `--overwrite` run 기준의 파일 집계 요약을 한 개 섹션으로 추가한다. output directory 경로, CSV 개수, Excel workbook 개수, parquet 개수, figure 개수를 출력한다. `src/synergy_stats/artifacts.py` 내부 workbook 경로와 workbook validation 로그는 그대로 둔다.

마지막으로 수정된 파이프라인을 `outputs/runs/console_log_structured` 같은 두 번째 깨끗한 출력 디렉터리로 실행하고, 새 콘솔/로그 파일 형식을 확인한다. 그런 다음 저장소의 MD5 비교 스크립트로 baseline과 candidate run의 안정 산출물을 비교한다. 구현이 끝나면 이 계획서와 영어 동반 계획서에 실제 구현 증거와 최종 메모를 기록한다.

## Concrete Steps

작업 디렉터리:

    /home/alice/workspace/26-03-synergy-analysis

코드 수정 전에 baseline run 생성:

    conda run -n cuda python main.py --overwrite --out outputs/runs/console_log_baseline

기대 동작:

    명령이 성공적으로 끝난다.
    `outputs/runs/console_log_baseline` 디렉터리가 생성된다.
    `outputs/runs/console_log_baseline/logs/run.log`에 현재의 짧은 형식 로그가 기록된다.

구현 순서:

    1. `src/emg_pipeline/log_utils.py` 생성
    2. `main.py` 수정
    3. `scripts/emg/01_load_emg_table.py` 수정
    4. `scripts/emg/02_extract_trials.py` 수정
    5. `scripts/emg/03_extract_synergy_nmf.py` 수정
    6. `scripts/emg/04_cluster_synergies.py` 수정
    7. `scripts/emg/05_export_artifacts.py` 수정

수정 후 candidate run 생성:

    conda run -n cuda python main.py --overwrite --out outputs/runs/console_log_structured

완료된 structured run에서 실제로 관찰한 출력 형태:

    2026-03-16 20:55:26,537 INFO root:
    2026-03-16 20:55:26,537 INFO root: ══════════════════════════════════════════════════════════
    2026-03-16 20:55:26,537 INFO root:   Step 1/5 : Load EMG Table
    2026-03-16 20:55:26,538 INFO root: ══════════════════════════════════════════════════════════
    2026-03-16 20:55:28,247 INFO root: [EMG Data]
    2026-03-16 20:55:28,248 INFO root:         Rows            : 474500
    2026-03-16 20:55:28,248 INFO root:         Columns         : 83
    2026-03-16 20:55:28,248 INFO root:         Subjects        : 24 (가윤호, 강비은, 권유영, 김민정, 김서하, 김우연, ...)
    2026-03-16 20:55:28,248 INFO root: [Event Metadata]
    2026-03-16 20:55:28,248 INFO root:         Selected trials      : 125
    2026-03-16 20:55:28,248 INFO root:         Selected step        : 53
    2026-03-16 20:55:28,249 INFO root: Step 1 done (1.72s)
    ...
    2026-03-16 21:15:37,935 INFO root: [Export Summary]
    2026-03-16 21:15:37,935 INFO root:         CSV files        : 10
    2026-03-16 21:15:37,935 INFO root:         Excel workbooks  : 2
    2026-03-16 21:15:37,936 INFO root:         Parquet files    : 1
    2026-03-16 21:15:37,936 INFO root:         Figures          : 131
    2026-03-16 21:15:37,936 INFO root: Step 5 done (133.09s)
    2026-03-16 21:15:37,936 INFO root: Pipeline completed successfully.

구현 후 안정 산출물 비교:

    conda run -n cuda python scripts/emg/99_md5_compare_outputs.py \
        --base outputs/runs/console_log_baseline \
        --new outputs/runs/console_log_structured

기대 비교 결과:

    MD5 comparison passed for curated stable files.

MD5 비교 결과가 `MISSING` 또는 `DIFF`를 출력하면, `Progress`를 완료로 바꾸기 전에 수정한 logging 관련 스크립트를 먼저 다시 점검한다.

## Validation and Acceptance

아래 조건을 모두 만족하면 이 변경을 승인한다.

`conda run -n cuda python main.py --overwrite --out outputs/runs/console_log_structured` 실행이 성공해야 하며, 파이프라인 계산 동작은 바뀌지 않아야 한다. 콘솔에는 `STEP_FILES`의 각 파일에 대응하는 5개의 step 배너가 보여야 하고, 현재 저장소 상태에서는 `Step 1/5`부터 `Step 5/5`까지 표시되어야 한다. 총 step 수는 하드코딩된 숫자가 아니라 `len(STEP_FILES)`에서 계산해야 한다.

Step 1은 구조화된 EMG data summary와 event metadata summary를 출력해야 한다. Step 2는 trial extraction summary를 출력해야 한다. Step 3은 NMF runtime summary와 NMF aggregate summary를 출력해야 한다. Step 4는 clustering runtime summary와 각 global group별 결과 섹션을 출력해야 한다. Step 5는 `export_results(context)` 완료 후 구조화된 export summary를 출력해야 한다. `src/synergy_stats/artifacts.py`가 출력하는 workbook 저장/검증 로그는 계속 보존되어야 한다.

`outputs/runs/console_log_structured/logs/run.log`에도 콘솔과 동일한 구조화 로그가 기록되어야 한다. 두 출력은 같은 `logging` handler를 사용하기 때문이다.

아래 명령이

    conda run -n cuda python scripts/emg/99_md5_compare_outputs.py \
        --base outputs/runs/console_log_baseline \
        --new outputs/runs/console_log_structured

`MD5 comparison passed for curated stable files.`를 출력해야 한다. 이것이 logging 개선이 안정 산출물을 바꾸지 않았다는 증거다. 이번 구현 완료 시점에는 이 명령이 실제로 기대한 성공 문구를 출력했다.

## Idempotence and Recovery

이 계획의 구현 단계는 모두 반복 실행해도 안전하다. 헬퍼 모듈 추가와 logging 호출 변경은 additive edit이며, baseline run과 candidate run은 서로 다른 출력 디렉터리를 사용하므로 디렉터리 이름만 유지하면 비교 증거도 보존된다.

baseline과 candidate 디렉터리를 다시 생성할 때는 항상 `--overwrite`를 사용한다. 그래야 과거 시도의 stale artifact가 지워져 파일 개수 집계가 결정적으로 유지된다. 부분 수정 후 다시 시도해야 하면 각 디렉터리에서 baseline/candidate 명령을 다시 실행하고, 그 다음 MD5 비교를 다시 실행하면 된다.

예상치 못한 산출물 변경이 발생하면 `main.py`, `src/emg_pipeline/log_utils.py`, `scripts/emg/01_load_emg_table.py`부터 `scripts/emg/05_export_artifacts.py`까지의 logging 관련 수정만 되돌린다. 저장소의 다른 변경은 되돌리지 않는다.

## Artifacts and Notes

생성 또는 수정 대상 파일:

    src/emg_pipeline/log_utils.py
    main.py
    scripts/emg/01_load_emg_table.py
    scripts/emg/02_extract_trials.py
    scripts/emg/03_extract_synergy_nmf.py
    scripts/emg/04_cluster_synergies.py
    scripts/emg/05_export_artifacts.py
    .agents/execplans/console_log_structured_output_execplan_en.md
    .agents/execplans/console_log_structured_output_execplan_ko.md

명시적 범위 밖 파일:

    scripts/emg/06_render_figures_only.py
    src/synergy_stats/figure_rerender.py
    src/synergy_stats/artifacts.py

`src/synergy_stats/artifacts.py`가 출력하는 workbook 경로 및 workbook validation 로그는 현재처럼 유지하는 것이 맞다. 이번 계획은 그 로그를 지우는 것이 아니라, 그 바깥에 상위 수준의 구조화 summary를 추가하는 작업이다.

## Interfaces and Dependencies

`src/emg_pipeline/log_utils.py`에 아래와 동등한 함수들을 만든다.

    def log_step_banner(step_num: int, total_steps: int, title: str) -> None:
        """빈 줄과 divider/title/divider 배너를 logging한다."""

    def log_kv_section(header: str, pairs: list[tuple[str, object]]) -> None:
        """섹션 제목과 정렬된 key-value 행을 logging한다."""

    def compact_list(values: Iterable[object], *, limit: int = 6) -> str:
        """subject, velocity, backend 목록을 짧은 comma-separated preview로 포맷한다."""

`main.py`는 `log_step_banner`를 import하고, `total_steps = len(STEP_FILES)`를 계산하며, `STEP_FILES`의 각 경로를 사용자에게 보일 제목으로 매핑하고, wall-clock elapsed time을 잰 뒤 step 완료 한 줄 로그를 직접 남긴다.

`scripts/emg/01_load_emg_table.py`부터 `scripts/emg/05_export_artifacts.py`까지는 `log_kv_section`을 import해 사용해야 한다. 헬퍼는 이미 문자열로 포맷된 값이나 `str()`로 변환 가능한 값을 받으면 충분하다. 헬퍼가 pandas 내부 구조나 config 세부사항을 알 필요는 없다.

새로운 서드파티 의존성은 추가하지 않는다. 표준 라이브러리 `logging`과, 요약 통계를 구성할 때 이미 프로젝트에 설치된 pandas, NumPy, `collections.Counter` 같은 기존 의존성만 사용한다.

## Revision Note

2026-03-16: 이 ExecPlan을 현재 5-step 파이프라인 기준으로 전면 재작성했다. 오래된 Step 6/posthoc 참조를 제거했고, 영어 동반 계획서와 의도 범위를 다시 동기화했으며, 약한 2개 파일 해시 비교 대신 저장소의 curated MD5 비교 절차를 검증 흐름으로 채택했다.
2026-03-16: 구현 완료 후 living section을 실제 실행 결과에 맞게 갱신했다. baseline/structured run, MD5 검증 결과를 기록했고, 문서 명령을 `conda run -n cuda python ...`으로 바로잡았으며, 인터페이스 설명을 실제 helper 이름과 맞췄다.
