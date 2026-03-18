# Gap-Free First Zero-Duplicate K Analysis ExecPlan (KO)

이 ExecPlan은 living document다. 작업이 진행되면 `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective` 섹션을 계속 업데이트해야 한다.

이 문서는 `.agents/PLANS.md`를 따른다. 독자는 현재 저장소와 이 문서만 가지고 있는 초보자라고 가정한다. 여기서 설명하는 구현은 반드시 `analysis/` 안에 머물러야 하며, `main.py`나 main pipeline에 새 메뉴, 플래그, selection mode를 추가하면 안 된다.

## Purpose / Big Picture

이 변경이 끝나면 사용자는 main pipeline을 바꾸지 않고도 아주 구체적인 질문에 답할 수 있다. 질문은 "gap statistic을 무시하고, duplicate trial이 처음 0개가 되는 K를 고르면 몇이 나오나?"이다. 이 분석은 pipeline final parquet 파일 하나를 입력으로 받아, pooled clustering 입력을 offline으로 다시 구성하고, 첫 zero-duplicate K를 보고한다. 현재 사용자 질문 기준으로 기대하는 관찰 결과는 gap 기반 값 `15` 대신 `k_selected=13`이 보고되는 것이다.

가장 쉬운 확인 방법은 `analysis/` 아래 스크립트 하나를 실행해 `outputs/final_trialwise.parquet` 같은 final parquet를 넘기고, 스크립트가 K scan 요약을 stdout에 출력하며 자기 analysis 폴더 아래에 작은 artifact 묶음을 쓰고, gap-statistic 경로를 호출하지 않았다고 명시하는지 확인하는 것이다.

## Progress

- [x] (2026-03-19 01:05Z) 사용자가 analysis-only rerun을 원하며 main pipeline에 새 메뉴나 CLI 옵션을 원하지 않는다는 점을 확인했다.
- [x] (2026-03-19 01:10Z) selection rule을 확정했다. duplicate trial이 0개가 되는 첫 번째 K를 선택한다.
- [x] (2026-03-19 01:16Z) 문서 범위를 확정했다. README는 새 analysis 폴더 안에만 쓰고, 저장소 루트 README는 수정하지 않는다.
- [x] (2026-03-19 01:28Z) `analysis/first_zero_duplicate_k_rerun/README.md`, `analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py`, `analysis/first_zero_duplicate_k_rerun/report.md`를 만들었다.
- [x] (2026-03-19 01:33Z) final parquet bundle 하나를 읽고, pooled vector를 재구성하고, `compute_gap_statistic`를 호출하지 않은 채 first zero-duplicate solution을 기록하는 offline rerun을 구현했다.
- [x] (2026-03-19 01:34Z) `tests/test_analysis/test_first_zero_duplicate_k_rerun.py`를 추가하고 synthetic contract 경로에서 `2 passed`를 확인했다.
- [x] (2026-03-19 01:15Z) `outputs/final_concatenated.parquet`에 대해 `--dry-run`을 실행해 live bundle metadata가 `k_gap_raw=15`, `k_selected=15`, `k_min_unique=13`임을 확인했다.
- [x] (2026-03-19 01:16Z) `outputs/final_concatenated.parquet`에 대해 full rerun을 두 번 실행했고, 두 run 모두 `k_selected_first_zero_duplicate=13`을 보고했다.
- [x] (2026-03-19 01:17Z) `default_run`과 `recheck_run` 사이에서 `summary.json`, `k_scan.json`, `k_duplicate_burden.png`의 MD5가 일치함을 확인했다.

## Surprises & Discoveries

- Observation: main clustering 모듈에는 이번 분석에 필요한 duplicate-feasibility machinery가 이미 대부분 들어 있다.
  Evidence: `src/synergy_stats/clustering.py`에는 public path가 여전히 `gap_statistic`만 허용하더라도 `_fit_best_kmeans_result`, `_search_zero_duplicate_candidate_at_k` 같은 내부 helper가 이미 있다.

- Observation: 깔끔한 analysis-only 구현은 raw EMG preprocessing이나 NMF를 다시 돌리지 않고 final parquet bundle만 의존해도 가능하다.
  Evidence: `src/synergy_stats/single_parquet.py`는 하나의 parquet source에서 `minimal_W`, `minimal_H_long`, `labels`, `trial_windows`를 복원할 수 있고, 이 정보면 pooled clustering input을 offline으로 재구성할 수 있다.

- Observation: 기존 `analysis/cosine_rerun_gap13_duplicate_exclusion/` 폴더는 관련은 있지만 같은 문제는 아니다.
  Evidence: 그 분석은 legacy cross-group baseline bundle에서 clustering 이후의 fixed-`K=13` component exclusion을 다루고 있고, 이번 요청은 gap statistic 없이 K selection 자체를 다시 돌리는 것이다.

- Observation: 사용자가 말한 `13 vs 15` 상황과 정확히 맞는 live bundle은 `trialwise`가 아니라 `concatenated`였다.
  Evidence: `outputs/final_concatenated.parquet` metadata는 `k_gap_raw=15`, `k_selected=15`, `k_min_unique=13`을 기록하고 있었고, 현재 `trialwise` bundle은 `k_gap_raw=17`, `k_selected=21`이었다.

- Observation: concatenated analysis unit의 `trial_num`은 항상 숫자가 아니다.
  Evidence: 첫 live run에서 `concat_nonstep` 같은 문자열이 들어 있어 reconstruction과 JSON export가 정수 변환에 실패했다. 이후 raw trial key를 그대로 보존하도록 수정했다.

- Observation: output reproducibility는 처음에는 `summary.json` 안의 absolute figure path 때문에만 깨졌다.
  Evidence: 첫 MD5 비교에서 `k_scan.json`과 figure byte는 이미 일치했고, `summary.json` diff는 `figure_path` 한 줄뿐이었다. 이 필드를 filename으로 바꾸자 세 파일 MD5가 모두 일치했다.

## Decision Log

- Decision: 새 작업은 `analysis/first_zero_duplicate_k_rerun/`에 둔다.
  Rationale: 사용자가 main pipeline 확장이 아니라 새 analysis 폴더를 원했고, 새 폴더가 기존 cosine rerun과 이번 질문을 깔끔하게 분리해 준다.
  Date/Author: 2026-03-19 / Codex

- Decision: 스크립트는 raw EMG 입력 대신 `outputs/final_trialwise.parquet` 같은 final parquet bundle 하나를 읽는다.
  Rationale: `analysis/`는 pipeline output에 의존해야 한다는 저장소 architecture rule을 따르기 위해서다.
  Date/Author: 2026-03-19 / Codex

- Decision: no-gap rule은 "`k_min`부터 K를 올리며, best searched candidate가 zero duplicate가 되는 첫 번째 K에서 멈춘다"로 정의한다.
  Rationale: 이것이 사용자가 승인한 "gap statistic 적용 안함"의 해석이며, 실제로 `13`이 맞는지 직접 검증하는 가장 직선적인 방법이다.
  Date/Author: 2026-03-19 / Codex

- Decision: 구현은 production pipeline에 `main.py` 플래그, config knob, 새 selection mode를 추가하지 않는다.
  Rationale: 사용자가 main pipeline에 메뉴를 만들지 말라고 명시했다.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

이 계획은 이제 요청된 analysis-only 범위에서 구현이 끝났다. 저장소에는 실행 가능한 스크립트, README, report, 재현 가능한 artifact를 포함한 `analysis/first_zero_duplicate_k_rerun/` 폴더가 생겼다. `outputs/final_concatenated.parquet`에 대해 실행했을 때 analysis는 `k_selected_first_zero_duplicate=13`을 보고하고, 같은 bundle의 pipeline metadata는 여전히 gap 기반 값 `15`를 보고한다. 즉, `main.py`나 production pipeline을 바꾸지 않고도 사용자의 현재 `13 vs 15` 질문에 직접 답할 수 있게 됐다.

## Context and Orientation

main pipeline entrypoint는 `main.py`지만, 이 계획은 그 파일을 수정하지 않는다. 이번 분석의 핵심 입력은 `src/synergy_stats/single_parquet.py`가 쓰는 single-parquet bundle이다. 이 모듈은 `artifact_kind`라는 키를 기준으로 `minimal_W`, `minimal_H_long`, `labels`, `metadata`, `trial_windows` 같은 frame을 하나의 parquet table 안에 저장한다. 새 분석은 그 bundle 파일 하나를 읽어야 하며, 보통 trialwise rerun이면 `outputs/final_trialwise.parquet`, concatenated rerun이면 `outputs/final_concatenated.parquet`를 사용한다.

중요한 clustering logic은 `src/synergy_stats/clustering.py`에 있다. 여기서 "duplicate trial"은 한 trial이 같은 cluster label에 component를 둘 이상 배정받는 경우를 뜻한다. production path는 현재 gap statistic으로 structure-first K를 고른 뒤, zero-duplicate solution이 나올 때까지 K를 위로 올린다. 이번 계획은 첫 단계만 의도적으로 건너뛴다. pooled vector를 다시 만들고, gap 값을 계산하지 않은 채 처음으로 zero-duplicate가 되는 K를 찾는 것이 목표다.

참고할 파일은 다음과 같다.

- `src/synergy_stats/single_parquet.py`: final parquet bundle 로딩
- `src/synergy_stats/clustering.py`: duplicate check와 candidate search semantics
- `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py`: `main.py` 바깥에서 pipeline logic을 재사용하는 analysis script 예시
- `analysis/cosine_rerun_gap13_duplicate_exclusion/README.md`: analysis 폴더 작성 관례 참고용. 다만 selection rule 자체는 이번 계획과 다르다.

## Plan of Work

새 폴더 `analysis/first_zero_duplicate_k_rerun/`를 만들고, 그 안에 최상위 파일 세 개를 둔다. `README.md`는 왜 이 폴더가 필요한지, analysis-only rerun이라는 점, 기대 입력 parquet 경로, dry-run과 full-run 명령을 설명한다. `analyze_first_zero_duplicate_k_rerun.py`는 단일 entry point다. `report.md`는 사람이 읽는 분석 보고서이며, 첫 full validation run 뒤에 반드시 숫자를 반영해 업데이트해야 한다.

스크립트는 pipeline final parquet 입력 경로 하나, output directory, `--dry-run` flag를 받아야 한다. 기본 입력은 현재 사용자 질문이 default rerun context의 구체적 K mismatch를 다루고 있으므로 `outputs/final_trialwise.parquet`로 둔다. 스크립트는 `src.synergy_stats.single_parquet.load_single_parquet_bundle()`로 bundle을 복원한 뒤, `minimal_W` frame에서 pooled clustering table을 다시 구성한다. selected pooled group만 남기고, `subject`, `velocity`, `trial_num`, `component_index` 같은 trial identity 필드를 보존하며, clustering path가 기대하는 vector order를 그대로 따라야 한다.

K selection에서는 `compute_gap_statistic`를 호출하면 안 된다. 대신 재구성한 pooled row에서 `k_min`을 계산하고, 사용 가능한 component 수와 명시적인 CLI 또는 config 기반 상한으로 `k_max`를 정한 뒤, K를 1씩 올리며 scan한다. 각 K마다 production clustering code와 같은 restart behavior를 사용하고, 최소한 다음 필드를 기록한다. candidate K, zero-duplicate solution 존재 여부, best searched candidate의 duplicate trial 수, searched restart 수, zero-duplicate candidate가 존재할 때 그 objective 값. 스크립트는 처음으로 duplicate가 0개가 되는 K에서 멈추고, 그 값을 `k_selected_first_zero_duplicate`로 보고해야 한다.

출력은 analysis 범위 안에만 머물러야 한다. artifact는 `analysis/first_zero_duplicate_k_rerun/artifacts/<run_name>/` 아래에 쓴다. artifact set은 작고 재현 가능하게 유지한다. `summary.json`, `k_scan.json`, `checksums.md5`, 그리고 선택적으로 `k_duplicate_burden.png` 정도면 충분하다. Excel이나 CSV는 쓰지 않는다. `report.md`는 연구 질문, offline reconstruction 방법, 정확한 no-gap selection rule, 관찰된 K scan, 현재 bundle에 대한 최종 답을 설명해야 한다.

## Concrete Steps

작업 디렉터리는 repository root다.

먼저 analysis 폴더와 skeleton을 만든다.

    mkdir -p analysis/first_zero_duplicate_k_rerun/artifacts

그다음 위에서 설명한 script와 문서를 구현한다. 구현 후에는 먼저 dry-run을 실행한다.

    conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
      --source-parquet outputs/final_trialwise.parquet \
      --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run \
      --dry-run

기대하는 dry-run 관찰:

    스크립트가 복원된 bundle key를 출력한다.
    스크립트가 pooled vector count와 계산된 K range를 출력한다.
    스크립트가 full artifact set을 쓰지 않고 종료한다.

그다음 full analysis를 실행한다.

    conda run --no-capture-output -n cuda python analysis/first_zero_duplicate_k_rerun/analyze_first_zero_duplicate_k_rerun.py \
      --source-parquet outputs/final_trialwise.parquet \
      --out-dir analysis/first_zero_duplicate_k_rerun/artifacts/default_run \
      --overwrite

현재 사용자 질문 기준으로 기대하는 full-run 관찰:

    스크립트가 gap statistic을 사용하지 않았다고 명시한다.
    스크립트가 연속된 K 값들에 대한 duplicate-trial count를 출력한다.
    스크립트가 first zero-duplicate K를 보고한다.
    의도한 bundle에서는 관찰된 답이 `k_selected_first_zero_duplicate=13`이어야 한다.

## Validation and Acceptance

수용 기준은 구조보다 동작이다. 사용자는 `analysis/` 아래 스크립트 하나를 실행하고, 기존 final parquet 파일 하나를 넘긴 뒤, no-gap 답을 명확하게 받아야 한다. 스크립트는 `--dry-run`과 full-run 모두 성공해야 한다. output folder는 analysis 범위의 artifact만 가져야 한다. `report.md`는 script가 stdout에 출력한 숫자와 일치해야 한다.

현재 요청에서 가장 중요한 acceptance check는 이것이다. 의도한 parquet bundle에 대해 실행했을 때, 스크립트는 duplicate trial이 처음 0개가 되는 K가 `13`이라는 K scan을 보여주고, main pipeline은 이전에 gap 기반 결과로 `15`를 보고했다는 점을 같이 설명해야 한다. 만약 실제 관찰값이 다르면, 기대값에 맞춰 억지로 쓰지 말고 보고서에 그 차이를 그대로 적어야 한다.

## Idempotence and Recovery

이 분석은 `analysis/first_zero_duplicate_k_rerun/artifacts/` 아래에만 쓰므로 반복 실행이 안전하다. 이전 artifact directory를 덮어쓰려면 `--overwrite`를 사용한다. 중간에 실패하면 해당 analysis artifact 하위 폴더만 지우거나 `--overwrite`로 다시 실행하면 된다. `outputs/final*.parquet`는 건드리면 안 되고, main pipeline output도 수정하면 안 된다.

## Artifacts and Notes

구현 후 기대하는 artifact layout은 다음과 같다.

    analysis/first_zero_duplicate_k_rerun/
      README.md
      analyze_first_zero_duplicate_k_rerun.py
      report.md
      artifacts/default_run/
        summary.json
        k_scan.json
        checksums.md5
        k_duplicate_burden.png

기대하는 summary field는 다음과 같다.

    source_parquet
    group_id
    vector_count
    k_min
    k_max
    selection_method = first_zero_duplicate
    gap_statistic_used = false
    k_selected_first_zero_duplicate
    duplicate_trial_count_by_k

## Interfaces and Dependencies

script는 restored bundle에서 tabular data를 읽거나 reshape할 때 `polars`를 먼저 사용하고, 기존 helper나 plotting path가 필요할 때만 `pandas`를 사용해야 한다. source bundle 복원은 `src.synergy_stats.single_parquet.load_single_parquet_bundle`를 사용한다. duplicate definition은 새로 invent하지 말고 clustering module의 duplicate-search semantics를 재사용해야 한다. 만약 이름이 `_`로 시작하는 `src/synergy_stats/clustering.py` helper를 import한다면, production API를 바꾸지 않고 production search behavior를 mirror하기 위한 의도적 선택이라는 점을 script docstring이나 간단한 주석에 남겨야 한다.

Change note: 이 계획 문서는 사용자가 세 가지 범위 제약을 명확히 한 뒤 추가되었다. 새 analysis 폴더를 만들 것, no-gap rule을 first zero-duplicate K로 정의할 것, README 수정은 analysis 폴더 안에서만 할 것이다.
