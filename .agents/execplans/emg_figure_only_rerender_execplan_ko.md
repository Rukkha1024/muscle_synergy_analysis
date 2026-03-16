# 기존 EMG 파이프라인 산출물용 figure-only 재생성 스크립트 추가

이 ExecPlan은 살아 있는 문서다. 작업이 진행되면 `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective` 섹션을 계속 갱신해야 한다.

이 저장소에는 `.agents/PLANS.md`가 있으며, 이 문서는 그 파일의 규칙에 맞춰 유지해야 한다. 이 계획서는 현재 워킹 트리와 이 파일만 가진 초보자도 그대로 따라갈 수 있게 작성한다.

## Purpose / Big Picture

이 변경이 끝나면 사용자는 `main.py`를 다시 돌리거나 NMF, clustering을 재계산하지 않고도 모든 EMG figure를 다시 만들 수 있다. 새 워크플로는 `outputs/runs/<run_id>` 안에 이미 저장된 CSV 산출물을 재사용해서 group figure, cross-group figure, trial별 NMF figure를 같은 위치에 다시 만든다.

사용자가 눈으로 확인할 수 있는 동작은 단순해야 한다. 기존 run 디렉터리에 전용 스크립트를 실행하면 전체 `figures/` 트리가 다시 만들어져야 한다. 사용자는 그 전에 `main.py`, 앞 번호의 다른 스크립트, 별도 준비 명령을 실행할 필요가 없어야 한다. 기존 figure는 기본적으로 덮어써야 하고, figure 생성에 필요한 소스 파일이 하나라도 없으면 즉시 실패해야 하며, non-figure 산출물은 바뀌지 않아야 한다. 사용자는 기존 run에 대해 figure를 다시 만든 뒤 예상 figure 파일이 생겼는지 확인하고, curated stable CSV의 MD5가 이전과 같은지 확인함으로써 이 기능을 검증할 수 있어야 한다.

## Progress

- [x] (2026-03-16 08:35Z) 사용자 요구사항을 확정했다. 모든 figure 계열을 재생성하고, 입력은 run 디렉터리를 기준으로 하며, 기존 figure는 기본적으로 덮어쓰고, 필요한 소스 파일이 없으면 즉시 실패한다.
- [x] (2026-03-16 08:35Z) 현재 figure 경로를 `main.py`, `scripts/emg/05_export_artifacts.py`, `src/synergy_stats/artifacts.py`, `src/synergy_stats/figures.py` 기준으로 파악했다.
- [x] (2026-03-16 08:35Z) 기존 run 디렉터리에 representative `W/H`, minimal-unit `W/H`, cluster label, trial metadata, cross-group decision 테이블이 이미 저장된다는 점을 확인했다.
- [x] (2026-03-16 08:35Z) 설계 방향을 고정했다. `main.py --figures-only` 모드를 추가하지 않고, 별도 스크립트와 공유 가능한 disk-backed rendering helper를 만든다.
- [x] (2026-03-16 09:00Z) `src/synergy_stats/figure_rerender.py`를 구현했다. run 디렉터리 검증, Polars 기반 CSV 로딩, 임시 디렉터리 렌더링, 안전한 `figures/` 교체를 한 곳에서 담당한다.
- [x] (2026-03-16 09:02Z) `scripts/emg/06_render_figures_only.py`를 추가했고, standalone 실행 시 `src` import가 되도록 repository root를 `sys.path`에 넣는 보완을 반영했다.
- [x] (2026-03-16 09:04Z) `src/synergy_stats/artifacts.py`의 direct in-memory figure 렌더링을 제거하고, artifact CSV 작성 뒤 공유 disk-backed helper를 호출하도록 교체했다.
- [x] (2026-03-16 09:06Z) rerender 전용 테스트를 추가했고, workbook export 테스트는 공유 helper를 patch하도록 바꿨으며, MD5 계약 테스트에는 figure-only 차이를 무시하는 검증을 추가했다.
- [x] (2026-03-16 09:08Z) `outputs/runs/default_run`에 대해 standalone rerender를 검증했다. 스크립트가 131개 figure를 다시 만들었고, top-level 6개 figure가 재생성되었으며, `nmf_trials` 개수는 `all_trial_window_metadata.csv`와 일치했고, curated stable MD5 비교도 통과했다.
- [ ] (2026-03-16 09:10Z) `conda run -n cuda python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q`는 여전히 run 디렉터리 아래 `global_step/cluster_labels.csv`, `global_nonstep/clustering_metadata.csv`가 존재해야 한다는 기존 기대 때문에 실패한다. 이 불일치는 figure-only rerender 범위 밖의 pre-existing 계약 문제로 남겨 둔다.

## Surprises & Discoveries

- Observation: 이 저장소는 figure 재생성에 필요한 입력을 이미 run 디렉터리에 저장하고 있으므로, figure-only 스크립트는 가볍게 유지할 수 있고 NMF나 clustering을 다시 계산할 필요가 없다.
  Evidence: `outputs/runs/default_run` 아래에 `all_representative_W_posthoc.csv`, `all_representative_H_posthoc_long.csv`, `all_minimal_units_W.csv`, `all_minimal_units_H_long.csv`, `all_cluster_labels.csv`, `all_trial_window_metadata.csv`, `cross_group_w_pairwise_cosine.csv`, `cross_group_w_cluster_decision.csv`가 이미 존재한다.

- Observation: `run_manifest.json`에는 config hash만 있고 원래 config 경로는 없으므로, figure-only 스크립트는 config 입력 정책을 따로 가져야 한다.
  Evidence: `src/emg_pipeline/config.py`는 `config_sha256`과 runtime metadata만 기록한다.

- Observation: plotting 함수는 이미 `src/synergy_stats/figures.py`에 분리돼 있지만, 현재 export 경로는 여전히 `src/synergy_stats/artifacts.py` 안에서 in-memory 객체를 가지고 figure 입력을 조립한다.
  Evidence: `export_results()`가 `save_group_cluster_figure()`, `save_trial_nmf_figure()`, `save_cross_group_heatmap()`, `save_cross_group_matched_w()`, `save_cross_group_matched_h()`, `save_cross_group_decision_summary()`를 직접 호출한다.

- Observation: 현재 실행 환경에서는 plain `python`이 없고, 프로젝트는 `conda run -n cuda python` 전제를 갖는다.
  Evidence: shell 확인 결과 `/bin/bash: line 1: python: command not found`가 나왔다.

- Observation: `scripts/emg/06_render_figures_only.py`를 standalone으로 직접 실행하려면 repository root를 `sys.path`에 명시적으로 추가해야 했다. `main.py` 안의 step module import 경로와 standalone script 경로가 같지 않았다.
  Evidence: 첫 CLI 테스트가 `ModuleNotFoundError: No module named 'src'`로 실패했고, `Path(__file__).resolve().parents[2]`를 `sys.path`에 넣은 뒤 해결됐다.

- Observation: conda 환경의 end-to-end 계약은 새로운 shared rendering path까지는 정상 도달하지만, 그 뒤 `global_step/`, `global_nonstep/` 하위 디렉터리를 기대하는 기존 assertion에서 계속 실패한다.
  Evidence: `tests/test_synergy_stats/test_end_to_end_contract.py`가 pipeline 완료 후에도 `assert step_labels.exists()`에서 실패했다.

## Decision Log

- Decision: `main.py`를 확장하지 않고 `scripts/emg/06_render_figures_only.py`를 새로 추가한다.
  Rationale: 사용자가 `main.py`를 매번 실행하지 않고 별도의 figure-only 경로를 원한다고 명시했다.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: 사용자 계약은 “스크립트 한 번 실행”으로 고정한다. 즉, figure-only 스크립트 자체가 전체 rerender 흐름을 끝내야 한다.
  Rationale: 사용자가 figure 생성은 새 스크립트만 실행해서 가능해야 한다고 명시적으로 추가 요구했다.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: 주 입력은 `outputs/runs/<run_id>`로 두고, `--config`는 선택 인자로 두되 기본값은 `configs/global_config.yaml`로 둔다.
  Rationale: 사용자가 승인한 주 입력은 run 디렉터리이지만, figure 설정과 muscle 순서를 얻기 위해 config는 여전히 필요하다. 기본 config 경로를 두면 일반 경로는 짧게 유지하면서 custom config 재현성도 보존할 수 있다.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: group cluster figure, cross-group figure, trial별 NMF figure를 모두 재생성한다.
  Rationale: 사용자가 부분 재생성이 아니라 전체 figure 재생성을 명시적으로 요청했다.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: overwrite는 기본 동작이며, 소스 파일 누락은 즉시 실패로 처리한다.
  Rationale: 이것은 사용자와 합의한 명시적 정책이다. 구현은 부분적 best-effort 출력보다 예측 가능한 전체 재생성을 우선해야 한다.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: 메인 파이프라인과 새 figure-only 스크립트는 하나의 disk-backed rendering 경로를 공유해야 한다.
  Rationale: 하나의 helper를 재사용해야 일반 실행에서 생성한 figure와 저장된 산출물에서 나중에 다시 생성한 figure가 서로 드리프트하지 않는다.
  Date/Author: 2026-03-16 / ChatGPT

- Decision: CSV는 먼저 Polars로 읽고, 기존 matplotlib 함수가 이미 pandas를 요구하는 경계에서만 pandas로 변환한다.
  Rationale: 저장소 규칙상 Polars를 pandas보다 먼저 써야 한다. 현재 plotting 함수는 pandas DataFrame을 받으므로, 변환은 마지막 인터페이스 경계에서만 일어나야 한다.
  Date/Author: 2026-03-16 / ChatGPT

## Outcomes & Retrospective

Figure-only rerender 기능 자체의 구현은 완료됐다. 저장소에는 이제 `src/synergy_stats/figure_rerender.py`라는 shared disk-backed rendering 경로가 있고, 일반 파이프라인은 artifact CSV를 쓴 뒤 이 helper를 사용하며, `scripts/emg/06_render_figures_only.py`는 기존 run 디렉터리만으로 figure를 다시 만들 수 있다.

가장 중요한 검증 결과는 사용자 눈에 바로 보이는 형태로 확보됐다. `conda run -n cuda python scripts/emg/06_render_figures_only.py --run-dir outputs/runs/default_run` 실행으로 figure 131개를 다시 만들었고, top-level figure 세트와 `nmf_trials` 개수가 올바르게 복원됐으며, curated non-figure CSV의 MD5는 바뀌지 않았다. 이 문서에 남아 있는 유일한 미해결 항목은, 이번 기능이 아니라 기존 end-to-end 계약이 `global_step/`, `global_nonstep/` 하위 디렉터리를 기대하는 불일치다.

## Context and Orientation

이 저장소의 진입점은 `main.py`다. 이 파일은 `src/emg_pipeline/config.py`를 통해 YAML 설정을 읽고, `outputs/runs/<run_id>` 아래 run 디렉터리를 준비한 뒤, 아래 wrapper 단계를 순서대로 실행한다.

    scripts/emg/01_load_emg_table.py
    scripts/emg/02_extract_trials.py
    scripts/emg/03_extract_synergy_nmf.py
    scripts/emg/04_cluster_synergies.py
    scripts/emg/05_export_artifacts.py

현재 figure 생성은 `src/synergy_stats/artifacts.py`의 `export_results()` 안에서 이뤄진다. 이 함수는 CSV 산출물을 쓴 뒤, 파이프라인 앞 단계에서 만들어진 in-memory 객체를 이용해 figure를 렌더링한다. 실제 plotting 함수 자체는 이미 `src/synergy_stats/figures.py`에 존재한다.

이 저장소에서 “group figure”는 `global_step_clusters`와 `global_nonstep_clusters`다. “Cross-group figure”는 `cross_group_cosine_heatmap`, `cross_group_matched_w`, `cross_group_matched_h`, `cross_group_decision_summary`다. “Trial-level NMF figure”는 `figures/nmf_trials/` 아래의 파일들이며, `all_trial_window_metadata.csv`의 각 trial마다 1개씩 생성된다.

Figure-only 스크립트는 아래 기존 run 산출물을 사용해야 한다.

    all_representative_W_posthoc.csv
    all_representative_H_posthoc_long.csv
    all_minimal_units_W.csv
    all_minimal_units_H_long.csv
    all_cluster_labels.csv
    all_trial_window_metadata.csv
    cross_group_w_pairwise_cosine.csv
    cross_group_w_cluster_decision.csv

이 파일 중 하나라도 없을 때 NMF, clustering, `main.py` 재실행으로 fallback 하지 마라. 사용자는 이 경우 즉시 실패하는 동작을 원한다.

이번 변경에서 가장 중요한 파일은 아래와 같다.

    main.py
    configs/global_config.yaml
    configs/synergy_stats_config.yaml
    scripts/emg/05_export_artifacts.py
    src/emg_pipeline/config.py
    src/synergy_stats/artifacts.py
    src/synergy_stats/figures.py
    tests/test_synergy_stats/test_end_to_end_contract.py
    tests/test_synergy_stats/test_figures_headless_backend.py
    tests/test_synergy_stats/test_md5_compare_outputs.py

새로 만들 파일은 모듈 1개와 스크립트 1개다.

    src/synergy_stats/figure_rerender.py
    scripts/emg/06_render_figures_only.py

README 사용 예시를 갱신한다면, 기존 run에서 figure를 다시 만드는 방법만 최소 범위로 수정해라. 관련 없는 setup 설명이나 이론 설명은 다시 쓰지 마라.

## Plan of Work

### 1. 공유 rerender helper 하나를 만든다

`src/synergy_stats/figure_rerender.py`를 만든다. 이 모듈은 disk-backed figure 생성 경로를 전담해야 한다. 역할은 run 디렉터리를 검증하고, 필요한 CSV를 읽고, `src/synergy_stats/figures.py`가 기대하는 DataFrame을 다시 구성한 뒤, figure 트리를 쓰는 것이다.

작고 안정적인 public surface를 아래처럼 정의한다.

    required_figure_artifacts(run_dir: Path) -> dict[str, Path]
    load_figure_artifacts(run_dir: Path) -> dict[str, object]
    render_figures_from_run_dir(run_dir: Path, cfg: dict[str, Any]) -> dict[str, list[str]]

`required_figure_artifacts()`는 필요한 파일 경로를 해석하고, 입력이 하나라도 없으면 명확한 `FileNotFoundError`를 발생시켜야 한다. 기존 `figures/` 디렉터리를 건드리기 전에 모든 입력을 먼저 검증해야 한다.

`load_figure_artifacts()`는 CSV를 Polars로 읽고, plotting 함수에 넘길 마지막 경계에서만 pandas로 변환해야 한다. 읽기와 쓰기 모두 `utf-8-sig` 호환성을 유지한다. Muscle 순서, figure DPI, figure 확장자는 현재 config 값을 사용한다.

`render_figures_from_run_dir()`는 저장된 산출물만으로 모든 figure 계열을 다시 만들어야 한다. 이 함수는 아래를 수행해야 한다.

1. Representative `W/H`, cluster label, trial metadata를 사용해 `global_step_clusters`와 `global_nonstep_clusters`를 렌더링한다.
2. `all_minimal_units_W.csv`, `all_minimal_units_H_long.csv`, 저장된 trial metadata를 사용해 모든 trial-level NMF figure를 렌더링한다.
3. Saved cross-group CSV와 run 디렉터리에 이미 있는 representative/minimal-unit 입력을 사용해 모든 cross-group figure를 렌더링한다.

Figure는 run 루트 아래 임시 디렉터리, 예를 들면 `figures.__tmp__`에 먼저 쓰고, 모든 plot이 성공한 뒤에만 `figures/`를 교체한다. 이렇게 해야 overwrite-by-default 정책을 안전하게 지키면서 중간에 실패했을 때 반쯤 써진 figure 트리를 남기지 않는다.

### 2. 메인 파이프라인도 같은 helper를 타게 만든다

`src/synergy_stats/artifacts.py`를 수정해서 `export_results()`가 더 이상 in-memory 구조에서 figure를 직접 렌더링하지 않게 한다. CSV, parquet, workbook 생성은 현재 위치에 그대로 둔다. Figure 소스 산출물이 모두 성공적으로 써진 뒤 `render_figures_from_run_dir(output_dir, cfg)`를 호출한다.

이 단계가 핵심 중복 제거다. 메인 파이프라인은 여전히 일반 실행 후 같은 figure 파일을 만들어야 하지만, 그 작업을 새 disk-backed helper를 재사용해서 수행해야 한다. 그래야 새 standalone 스크립트와 기존 파이프라인이 동일한 동작 경로를 공유하게 된다.

Clustering, NMF 추출, cross-group 테이블 계산 방식은 바꾸지 마라. 이번 기능은 rendering 경로 리팩터링과 새 엔트리포인트 추가이지, 수치 로직 변경이 아니다.

### 3. 전용 CLI 스크립트를 추가한다

`scripts/emg/06_render_figures_only.py`를 만든다. 스크립트는 얇게 유지해야 한다. 이 스크립트는 아래를 수행해야 한다.

1. `--run-dir`를 필수 인자로 파싱한다.
2. `--config`를 선택 인자로 파싱하되 기본값은 `configs/global_config.yaml`로 둔다.
3. 기존 `src/emg_pipeline/config.py`의 `load_pipeline_config()`로 config를 읽는다.
4. Manifest나 non-figure 산출물을 다시 쓰지 않고 run 디렉터리만 해석한다.
5. `render_figures_from_run_dir()`를 호출한다.
6. 성공 시 종료 코드 `0`, 검증 실패나 렌더링 실패 시 nonzero로 종료한다.

`--skip-missing`, `--partial` 같은 fallback flag는 추가하지 마라. 사용자는 부분 생성 정책을 거부했다.
사용자 관점의 실행 계약은 이 스크립트 한 번이면 충분해야 한다는 점이다. 내부 import는 괜찮지만, 별도 setup 스크립트, chained shell command, `main.py`나 `scripts/emg/05_export_artifacts.py` 선행 실행 요구는 허용하지 않는다.

### 4. 집중된 테스트를 추가한다

`tests/test_synergy_stats/test_figure_rerender.py`를 추가한다. 이 파일은 새로운 helper와 새로운 CLI 계약을 가벼운 fixture 데이터로 검증해야 한다.

최소한 아래 테스트는 있어야 한다.

1. Required CSV 하나를 제거하면 스크립트 또는 helper가 기존 `figures/` 디렉터리를 교체하기 전에 실패한다는 failure-path 테스트.
2. 저장된 CSV 산출물만으로 rerender 했을 때 예상 top-level figure 파일과 예상 개수의 trial figure가 다시 생성된다는 success-path 테스트.
3. Rerender가 저장된 run 산출물만 사용하며, 이전 파이프라인 context 객체를 요구하지 않는다는 테스트.

`tests/test_synergy_stats/test_end_to_end_contract.py`도 확장해서 기존 fixture run이 shared helper를 통해 전체 figure 트리를 계속 생성한다는 점을 증명해야 한다. 네 개의 cross-group figure 모두에 대한 assertion을 추가하고, 현재 trial figure 개수 계약은 유지한다.

Non-figure 안정성 확인이 기존 MD5 성격 테스트와 자연스럽게 맞아떨어진다면, 비슷한 assertion을 다른 파일에 중복해서 만들지 말고 그 파일을 확장해라.

### 5. 사용자 문서를 최소 범위로 갱신한다

`README.md`는 기존 run에서 figure를 다시 만드는 방법을 설명하는 부분만 수정한다. 변경 범위는 작게 유지한다. 새 명령 예시는 아래와 같아야 한다.

    conda run -n cuda python scripts/emg/06_render_figures_only.py --run-dir outputs/runs/default_run

이 명령이 기본적으로 `figures/` 트리를 덮어쓰며, 필요한 figure source CSV가 없으면 실패한다는 점도 함께 문서화한다.

## Concrete Steps

모든 명령은 저장소 루트에서 실행한다.

    cd /home/alice/workspace/26-03-synergy-analysis

코드를 바꾸기 전 현재 동작을 확인한다.

    conda run -n cuda python main.py --help
    conda run -n cuda python scripts/emg/06_render_figures_only.py --help

구현 후 기대 결과는 새 스크립트의 help가 존재하고, `main.py`는 여전히 전체 파이프라인 엔트리포인트로 남아 있는 것이다.

MD5 비교용 non-figure 스냅샷을 먼저 만든다.

    tmp_before="$(mktemp -d)"
    cp -R outputs/runs/default_run "$tmp_before/default_run_before"

Figure-only 스크립트를 실행한다.

    conda run -n cuda python scripts/emg/06_render_figures_only.py --run-dir outputs/runs/default_run

기대되는 터미널 결과는 성공 메시지와 run 디렉터리 이름, 생성된 figure 개수다. NMF나 clustering 단계가 다시 실행되면 안 된다.
이 한 번의 명령만으로 작업이 끝나야 하며, 전후로 다른 스크립트를 추가 실행할 필요가 없어야 한다.

Figure 트리를 검증한다.

    find outputs/runs/default_run/figures -maxdepth 1 -type f | sort
    find outputs/runs/default_run/figures/nmf_trials -type f | wc -l

기대 결과는 top-level 디렉터리에 아래 여섯 파일이 존재하는 것이다.

    cross_group_cosine_heatmap.png
    cross_group_decision_summary.png
    cross_group_matched_h.png
    cross_group_matched_w.png
    global_nonstep_clusters.png
    global_step_clusters.png

그리고 `nmf_trials` 파일 개수는 `all_trial_window_metadata.csv`의 unique trial 개수와 같아야 한다.

테스트를 실행한다.

    conda run -n cuda pytest tests/test_synergy_stats/test_figure_rerender.py -q
    conda run -n cuda pytest tests/test_synergy_stats/test_end_to_end_contract.py -q

Curated non-figure 산출물을 스냅샷과 비교한다.

    conda run -n cuda python scripts/emg/99_md5_compare_outputs.py \
      --base "$tmp_before/default_run_before" \
      --new outputs/runs/default_run

기대 결과는 아래와 같다.

    MD5 comparison passed for curated stable files.

## Validation and Acceptance

아래 조건이 모두 참일 때만 변경을 승인한다.

1. `scripts/emg/06_render_figures_only.py --run-dir <existing_run>`이 이전 파이프라인 단계를 다시 호출하지 않고 전체 `figures/` 트리를 재생성한다.
2. 사용자는 다른 스크립트나 수동 준비 없이 이 스크립트 한 번만 실행해서 figure 재생성을 끝낼 수 있어야 한다.
3. 스크립트는 기존 `figures/` 트리를 기본적으로 덮어쓴다.
4. 필요한 CSV 입력이 하나라도 없으면, 스크립트는 기존 `figures/` 트리를 교체하기 전에 nonzero로 종료한다.
5. `main.py`는 여전히 일반 파이프라인 실행 중 같은 figure 계열을 생성해야 하며, 이제 그 동작은 CSV 산출물 작성 뒤 같은 helper를 재사용해 수행한다.
6. `scripts/emg/99_md5_compare_outputs.py`가 rerender 전 스냅샷과 rerender 후 run 디렉터리를 비교했을 때 통과해야 하며, 이것으로 curated non-figure 산출물이 바뀌지 않았음을 증명한다.

## Idempotence and Recovery

Rerender 경로는 idempotent 해야 한다. 같은 run 디렉터리에 새 스크립트를 여러 번 실행해도 같은 figure 집합으로 `figures/` 트리를 단순 교체하는 결과여야 한다.

안전한 복구 경로는 아래와 같다.

1. 먼저 필요한 입력을 모두 검증한다.
2. 임시 sibling 디렉터리에 figure를 렌더링한다.
3. 모든 작업이 성공한 뒤에만 `figures/`를 교체한다.

렌더링이 실패하면 이전 `figures/` 디렉터리를 그대로 유지하고, 가장 먼저 막힌 missing file 또는 rendering exception을 명확하게 보고해야 한다.

## Artifacts and Notes

저장된 run 디렉터리에는 이미 figure 재생성에 필요한 정보가 충분하다. 구현은 아래 파일 집합을 source of truth로 취급해야 한다.

    outputs/runs/default_run/all_representative_W_posthoc.csv
    outputs/runs/default_run/all_representative_H_posthoc_long.csv
    outputs/runs/default_run/all_minimal_units_W.csv
    outputs/runs/default_run/all_minimal_units_H_long.csv
    outputs/runs/default_run/all_cluster_labels.csv
    outputs/runs/default_run/all_trial_window_metadata.csv
    outputs/runs/default_run/cross_group_w_pairwise_cosine.csv
    outputs/runs/default_run/cross_group_w_cluster_decision.csv

재생성되어야 하는 top-level figure 트리는 아래와 같다.

    outputs/runs/<run_id>/figures/global_step_clusters.<ext>
    outputs/runs/<run_id>/figures/global_nonstep_clusters.<ext>
    outputs/runs/<run_id>/figures/cross_group_cosine_heatmap.<ext>
    outputs/runs/<run_id>/figures/cross_group_matched_w.<ext>
    outputs/runs/<run_id>/figures/cross_group_matched_h.<ext>
    outputs/runs/<run_id>/figures/cross_group_decision_summary.<ext>
    outputs/runs/<run_id>/figures/nmf_trials/*.<ext>

`<ext>`는 `configs/synergy_stats_config.yaml`의 figure suffix를 따른다.

## Interfaces and Dependencies

`src/synergy_stats/figure_rerender.py`에는 아래 함수를 정의한다.

    def required_figure_artifacts(run_dir: Path, *, include_cross_group: bool = True) -> dict[str, Path]:
        ...

    def load_figure_artifacts(run_dir: Path, *, include_cross_group: bool = True) -> dict[str, object]:
        ...

    def render_figures_from_run_dir(run_dir: Path, cfg: dict[str, Any]) -> dict[str, list[str]]:
        ...

`load_figure_artifacts()`는 CSV를 `utf-8-sig`로 decode한 뒤 Polars로 파싱하고, `src/synergy_stats/figures.py`에 실제로 넘겨야 하는 마지막 테이블만 pandas DataFrame으로 변환해야 한다. 선택적 `include_cross_group` 키워드는 cross-group figure 출력을 끈 config와도 shared helper가 호환되도록 한다.

`scripts/emg/06_render_figures_only.py`에는 아래를 정의한다.

    def main() -> int:
        ...

그리고 config는 아래 import로 읽는다.

    from src.emg_pipeline.config import load_pipeline_config

`src/synergy_stats/artifacts.py`에서는 direct plot 호출을 아래 방식으로 교체한다.

    from .figure_rerender import render_figures_from_run_dir

    ...
    render_figures_from_run_dir(output_dir, cfg)

Plan Change Note: 구현 완료 후 문서를 갱신했다. shared rerender 경로 완성, direct-script import-path 보완, `default_run` 검증 결과(`131`개 figure 재생성, curated MD5 불변), 그리고 `global_step/`, `global_nonstep/` 하위 디렉터리 assertion에 대한 기존 end-to-end 계약 불일치를 함께 기록했다.
