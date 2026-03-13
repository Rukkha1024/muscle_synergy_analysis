# Implement a paper-style step-vs-nonstep muscle synergy analysis under `analysis/`

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` supplied with the task context. The implementation must also respect the repository rules from `.agents/AGENTS.md`: do the work under `analysis/`, use conda env `module`, keep pipeline code untouched, and treat the baseline pipeline output as the source of truth for trial selection and analysis windows.


## Purpose / Big Picture / 목적 / 큰 그림

한국어: 이 변경이 끝나면 사용자는 `outputs/runs/default_run`의 기존 파이프라인 산출물을 그대로 입력으로 사용하면서, 논문 기반 근육시너지 분석을 별도의 `analysis/` 작업공간에서 다시 실행할 수 있다. 새 분석은 현재 프로젝트의 trial 선택과 window 정의는 유지하고, 그 위에 논문식 NMF rank 선택, gap-statistic 기반 k-means, 공통 시너지 판정, centroid 매칭, cross-fit, merging/fractionation, 그리고 baseline `default_run`과의 직접 비교를 수행한다. 사용자는 하나의 분석 스크립트를 실행해 `report.md`를 얻고, 그 문서에서 “현재 baseline 결과와 paper-style 결과가 어디서 같고 어디서 다른지”를 바로 확인할 수 있어야 한다.

English: After this change, a user will be able to reuse the existing pipeline artifacts in `outputs/runs/default_run` and run a separate paper-based muscle synergy analysis under `analysis/`. The new analysis keeps the current project’s trial selection and analysis window definitions intact, then layers on the paper-style NMF rank rule, gap-statistic k-means, common-synergy detection, centroid matching, cross-fit, merging/fractionation, and a direct comparison against the baseline `default_run`. The user should be able to run one analysis script and read one `report.md` file to see where the current baseline and the paper-style results agree or differ.


## Progress / 진행 상황

- [x] (2026-03-13T00:00Z) 한국어: 사용자와 요구사항 브리프를 잠갔다. 입력은 현재 프로젝트 파이프라인 산출물이며, 근육은 16채널 그대로 사용한다. trial 선택과 window는 현재 파이프라인 로직을 따른다. trial 내부 중복 라벨만 금지한다. 공통 시너지는 `1/3` 이상 subject가 기여한 cluster만 인정한다. cluster centroid는 `SP < 0.8`이면 unmatched로 남긴다. 비교 대상은 `default_run`만 사용한다. English: The requirements brief is locked with the user. The input is the current project pipeline output, the 16-channel muscle set is kept as-is, trial selection and windowing follow the current pipeline logic, only within-trial duplicate labels are forbidden, only clusters contributed by at least one-third of subjects count as common synergies, centroid matches with `SP < 0.8` remain unmatched, and the only baseline comparison target is `default_run`.

- [x] (2026-03-13T09:35Z) 한국어: 실제 저장소 입력 경로를 다시 확인했다. `outputs/final.parquet`는 time-series EMG가 아니라 baseline NMF 요약 산출물이고, 재분석용 EMG time-series는 `configs/global_config.yaml`의 `input.emg_parquet_path`에 연결된 normalized parquet에서 읽어야 한다는 점을 문서에 반영했다. English: Re-checked the real repository inputs. `outputs/final.parquet` is a baseline NMF summary artifact rather than the time-series EMG source, and the re-analysis EMG time series must be read from the normalized parquet referenced by `configs/global_config.yaml -> input.emg_parquet_path`; this is now reflected in the plan.

- [x] (2026-03-13T09:35Z) 한국어: 구현 위치를 사용자 요청과 실제 폴더 상태에 맞춰 `analysis/compare_Cheung,2021/`로 고정했다. English: Fixed the implementation location to `analysis/compare_Cheung,2021/` so it matches the user request and the current folder layout.

- [x] (2026-03-13T13:40Z) 한국어: `analysis/compare_Cheung,2021/` 폴더에 단일 진입점 스크립트, 보고서, figure 출력 경로를 만들었다. English: Created the single-entry script, report, and figure output path under `analysis/compare_Cheung,2021/`.

- [x] (2026-03-13T13:40Z) 한국어: baseline metadata와 config 기반 normalized EMG parquet를 읽는 dry-run 경로를 구현하고 실행 검증했다. English: Implemented and validated the dry-run path that reads baseline metadata and the config-driven normalized EMG parquet.

- [x] (2026-03-13T13:40Z) 한국어: 논문식 NMF rank 탐색과 best-of-20 재시작 로직을 구현했다. English: Implemented the paper-style NMF rank search and best-of-20 restarts.

- [x] (2026-03-13T13:40Z) 한국어: duplicate-free k-means, gap statistic, 공통 cluster 판정, step↔nonstep centroid 매칭을 구현하고 full run에서 검증했다. English: Implemented duplicate-free k-means, the gap statistic, common-cluster detection, and step↔nonstep centroid matching and validated them in the full run.

- [x] (2026-03-13T13:40Z) 한국어: cross-fit, centroid 수준 merging/fractionation, 개별 synergy 수준 merging/fractionation과 MI를 구현했다. English: Implemented cross-fit, centroid-level merging/fractionation, individual-synergy-level merging/fractionation, and the Merging Index (MI).

- [x] (2026-03-13T13:40Z) 한국어: paper-style 결과를 `default_run` baseline과 비교하고 `report.md`를 완성했다. English: Compared the paper-style results against the `default_run` baseline and completed `report.md`.

- [x] (2026-03-13T13:40Z) 한국어: dry-run, prototype, full run, 결과 검증, 재실행 MD5 비교를 마쳤다. English: Finished dry-run, prototype, full run, result validation, and rerun MD5 comparison.


## Surprises & Discoveries / 예상 밖 발견 사항

- Observation:
  한국어: 입력 EMG는 이미 filtering, min-max normalization, resampling을 거친 상태이므로, 논문의 raw EMG 전처리 단계는 재실행할 수 없다. 따라서 이번 구현은 “논문 완전 재현”이 아니라 “현재 project 입력에 대한 paper-style adaptation”이다.
  English: The EMG input has already been filtered, min-max normalized, and resampled, so the paper’s raw-EMG preprocessing cannot be replayed. This implementation is therefore not a full reproduction of the paper, but a paper-style adaptation to the project’s current inputs.

  Evidence:
  한국어: baseline truth는 `outputs/runs/default_run/all_trial_window_metadata.csv`에 있고, 실제 재분석용 time-series EMG는 `configs/global_config.yaml`의 `input.emg_parquet_path`에 연결된 normalized parquet에 있다.
  English: The baseline truth is stored in `outputs/runs/default_run/all_trial_window_metadata.csv`, while the actual time-series EMG used for re-analysis lives in the normalized parquet referenced by `configs/global_config.yaml -> input.emg_parquet_path`.

- Observation:
  한국어: 논문은 centroid 간 매칭과 unmatched 규칙은 분명히 서술하지만, 프로젝트가 이미 사용하는 “trial 내부 duplicate-free cluster assignment”는 논문에 명시되지 않았다. 이 제약은 사용자 요구와 현재 프로젝트 해석 방식에 맞춘 project-specific adaptation이다.
  English: The paper clearly specifies centroid matching and unmatched handling, but it does not explicitly specify the project’s existing “within-trial duplicate-free cluster assignment.” That constraint is a project-specific adaptation chosen to match the user’s requirement and the project’s current interpretation.

  Evidence:
  한국어: 이 규칙은 사용자와의 요구사항 고정 단계에서 명시적으로 선택되었다.
  English: This rule was explicitly selected during requirements discovery with the user.

- Observation:
  한국어: 사용자는 subject를 섞어서 전부 비교하길 원한다. 따라서 cross-fit과 merging/fractionation도 동일 subject-velocity 내부 pairing이 아니라 step pool 전체와 nonstep pool 전체의 all-by-all 비교가 되어야 한다.
  English: The user wants all subjects mixed together. Therefore, cross-fit and merging/fractionation must use all-by-all comparisons between the pooled step set and the pooled nonstep set, not only same-subject or same-velocity pairs.

  Evidence:
  한국어: 사용자가 “subject 다 섞어서 전부 비교”를 명시적으로 선택했다.
  English: The user explicitly chose “mix all subjects and compare everything.”

- Observation:
  한국어: 사용자는 custom academic style보다 파이프라인 기본 figure style을 선호했다. 따라서 최종 cluster figure는 `src/synergy_stats/figures.py`의 `save_group_cluster_figure()`를 재사용해야 했다.
  English: The user preferred the pipeline's default figure style over the custom academic style, so the final cluster figures had to reuse `save_group_cluster_figure()` from `src/synergy_stats/figures.py`.

  Evidence:
  한국어: 스타일 수정 요청 이후 `global_step_clusters.png`와 `global_nonstep_clusters.png`를 pipeline renderer로 다시 생성해 확인했다.
  English: After the style-change request, `global_step_clusters.png` and `global_nonstep_clusters.png` were regenerated and checked with the pipeline renderer.


## Decision Log / 결정 로그

- Decision:
  한국어: 구현 위치는 사용자 요청대로 `analysis/compare_Cheung,2021/` 하나로 고정한다.
  English: Fix the implementation location to a single folder, `analysis/compare_Cheung,2021/`, as requested by the user.

  Rationale:
  한국어: 사용자가 명시적으로 `analysis/compare_Cheung,2021/` 안에서 작업하길 요청했고, analysis-report 규칙도 self-contained analysis folder를 요구한다.
  English: The user explicitly requested work inside `analysis/compare_Cheung,2021/`, and the analysis-report rule also requires a self-contained analysis folder.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: trial selection과 analysis window는 새로 계산하지 않고, `outputs/runs/default_run/all_trial_window_metadata.csv`를 canonical truth로 사용한다.
  English: Do not recompute trial selection or analysis windows; use `outputs/runs/default_run/all_trial_window_metadata.csv` as the canonical truth.

  Rationale:
  한국어: 사용자가 “현 project pipeline logic 대로 진행”을 선택했고, analysis는 pipeline과 분리되어야 하므로 baseline 산출물만 읽는 쪽이 가장 안전하다.
  English: The user chose to follow the current project pipeline logic, and analysis must remain separated from the pipeline, so reading only baseline artifacts is the safest route.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: 논문식 rank rule은 `1..16` 탐색, `R² >= 0.80` 최소 rank 채택, 각 rank는 20회 random restart 중 최고 `R²` 해를 선택하는 방식으로 구현한다.
  English: Implement the paper-style rank rule as a search over `1..16`, select the smallest rank with `R² >= 0.80`, and keep the highest-`R²` solution among 20 random restarts at each rank.

  Rationale:
  한국어: 사용자는 16채널 입력을 유지하기로 했고, 논문의 핵심 규칙은 rank selection logic에 있다.
  English: The user decided to keep the 16-channel input, and the paper’s key rule is the rank-selection logic.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: cluster 수 탐색은 paper-style `2..20`을 따르되, duplicate-free가 가능한 최소값 이상으로 lower bound를 자동 보정한다.
  English: Search the number of clusters over paper-style `2..20`, but automatically raise the lower bound so that duplicate-free assignment remains feasible.

  Rationale:
  한국어: 사용자는 논문식 `2..20` 범위를 원했지만, 한 trial 안의 synergy 수보다 작은 k에서는 duplicate-free assignment가 수학적으로 불가능하다.
  English: The user wants the paper-style `2..20` range, but duplicate-free assignment is mathematically impossible if `k` is smaller than the number of synergies extracted from a trial.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: common synergy는 cluster centroid로 정의하고, unique subject 기준 `>= ceil(n_subjects / 3)`를 충족하는 cluster만 common cluster로 인정한다.
  English: Define a common synergy as a cluster centroid, and accept only clusters with unique-subject coverage `>= ceil(n_subjects / 3)` as common clusters.

  Rationale:
  한국어: 사용자가 논문과 같은 common-cluster 기준을 고정했다.
  English: The user explicitly locked the paper’s common-cluster rule.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: step centroid와 nonstep centroid의 대응은 Hungarian 1:1 matching으로 찾고, `SP < 0.8`이면 unmatched로 남긴다.
  English: Find the step↔nonstep centroid correspondence using Hungarian one-to-one matching, and leave any pair with `SP < 0.8` unmatched.

  Rationale:
  한국어: 사용자가 논문식 unmatched 규칙을 그대로 적용하기로 했다.
  English: The user chose to preserve the paper’s unmatched rule.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: cross-fit과 merging/fractionation은 subject를 섞은 all-by-all 비교로 구현한다.
  English: Implement cross-fit and merging/fractionation as all-by-all comparisons with all subjects mixed together.

  Rationale:
  한국어: 사용자가 같은 subject-velocity 내부 pairing보다 pooled comparison을 원했다.
  English: The user chose pooled comparison over same-subject or same-velocity pairing.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: baseline comparison target은 `outputs/runs/default_run`만 사용한다.
  English: Use only `outputs/runs/default_run` as the baseline comparison target.

  Rationale:
  한국어: 사용자가 `compare_professor`는 제외하고 `default_run`만 비교 대상으로 고정했다.
  English: The user explicitly excluded `compare_professor` and fixed `default_run` as the only comparison target.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: analysis-only 제약 때문에 새 YAML config는 만들지 않고, 스크립트 상단의 `PaperMethodConfig` dataclass와 CLI override를 사용한다.
  English: Because the work is restricted to `analysis/`, do not add a new YAML config; use a `PaperMethodConfig` dataclass near the top of the script plus CLI overrides.

  Rationale:
  한국어: 사용자는 코드 수정 범위를 `analysis/`로 제한했다. 동시에 매개변수는 한곳에 모아야 하므로, analysis script 내부의 명시적 dataclass와 CLI가 가장 단순하고 안전하다.
  English: The user restricted the change scope to `analysis/`. At the same time, parameters must remain centralized, so an explicit dataclass plus CLI overrides inside the analysis script is the simplest safe compromise.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro

- Decision:
  한국어: 재분석용 EMG time-series는 `outputs/final.parquet`가 아니라 `configs/global_config.yaml`의 `input.emg_parquet_path`와 `input.event_xlsm_path`를 통해 다시 로드하고, baseline run은 trial selection/window truth와 대표 시너지 비교에만 사용한다.
  English: Reload the re-analysis EMG time series through `configs/global_config.yaml -> input.emg_parquet_path` and `input.event_xlsm_path`, not through `outputs/final.parquet`; use the baseline run only for trial-selection/window truth and representative-synergy comparison.

  Rationale:
  한국어: 현재 저장소의 `outputs/final.parquet`는 time-series가 아니라 muscle-weight long table이라 trial-level EMG 재구성에 사용할 수 없다. 반면 config에 연결된 normalized parquet와 event workbook은 실제로 존재하며, 기존 analysis code path도 같은 입력을 사용한다.
  English: In the current repository, `outputs/final.parquet` is a muscle-weight long table rather than a time-series EMG source, so it cannot support trial-level EMG reconstruction. The normalized parquet and event workbook referenced by the config both exist, and the existing analysis code path already uses those same inputs.

  Date/Author:
  2026-03-13 / GPT-5.4 Pro


## Outcomes & Retrospective / 결과 및 회고

한국어: 구현은 end-to-end로 실행 가능한 상태까지 완료되었다. 이제 처음 보는 구현자도 이 문서만 보고 `analysis/compare_Cheung,2021/` 안에서 baseline metadata와 config 기반 normalized EMG 입력을 사용해 paper-style 분석을 끝까지 수행하고, `report.md`와 pipeline-style cluster figure 및 비교 figure에서 baseline과 paper-style 결과를 확인할 수 있어야 한다.

English: Implementation is now complete enough to execute end-to-end. A first-time contributor can read only this document, work inside `analysis/compare_Cheung,2021/`, run the full paper-style analysis using baseline metadata plus the config-driven normalized EMG input, and produce `report.md` together with pipeline-style cluster figures and supporting comparison figures.


## Context and Orientation / 현재 맥락과 구조 설명

한국어: 이 저장소의 기본 파이프라인은 `subject-velocity-trial`을 기본 단위로 사용해 step과 nonstep을 비교한다. 여기서 “trial key”는 `subject`, `velocity`, `trial_num`, 그리고 step/nonstep class를 합친 식별자다. baseline run은 이미 어떤 trial이 선택되었는지, step인지 nonstep인지, window가 실제 step 종료인지 surrogate 종료인지, selection rule을 통과했는지를 `outputs/runs/default_run/all_trial_window_metadata.csv`에 기록해 둔다. 이 plan에서 “canonical truth”라는 말은 바로 이 파일을 뜻한다. 새 analysis는 이 truth를 다시 계산하지 않고 그대로 믿어야 한다.

English: The default pipeline in this repository compares step and nonstep using `subject-velocity-trial` as the basic unit. Here, a “trial key” means the identifier formed by `subject`, `velocity`, `trial_num`, and the step/nonstep class. The baseline run already records which trials were selected, whether each is step or nonstep, whether the window end is a real step end or a surrogate end, and whether the trial passed the selection rule, inside `outputs/runs/default_run/all_trial_window_metadata.csv`. In this plan, the phrase “canonical truth” means this file. The new analysis must trust this file and must not recompute those choices.

한국어: baseline truth는 `outputs/runs/default_run/all_trial_window_metadata.csv`에서 읽는다. 하지만 실제 time-series input은 `configs/global_config.yaml`의 `input.emg_parquet_path`와 `input.event_xlsm_path`를 통해 다시 로드한다. 이렇게 해야 baseline과 동일한 trial selection/window truth를 유지하면서도 trial-level EMG를 다시 구성할 수 있다. baseline 대표 시너지는 `outputs/runs/default_run/all_representative_W_posthoc.csv`에서 읽어 비교한다. 필요하면 baseline cluster membership은 `all_cluster_members.csv`와 `all_cluster_labels.csv`에서 보조적으로 읽을 수 있지만, 새 analysis의 canonical truth는 여전히 `all_trial_window_metadata.csv`다.

English: Read the baseline truth from `outputs/runs/default_run/all_trial_window_metadata.csv`. However, reload the actual time-series input through `configs/global_config.yaml -> input.emg_parquet_path` and `input.event_xlsm_path`. This is the only way to keep the same trial-selection/window truth while still reconstructing trial-level EMG. Read baseline representative synergies from `outputs/runs/default_run/all_representative_W_posthoc.csv` for comparison. If needed, baseline cluster membership can be read from `all_cluster_members.csv` and `all_cluster_labels.csv` as auxiliary inputs, but the new analysis still treats `all_trial_window_metadata.csv` as the canonical truth.

한국어: 이 analysis는 논문을 “그대로” 복제하지 않는다. 논문은 running EMG의 raw preprocessing, 15근육, session 단위 subject-group 비교를 사용했다. 현재 프로젝트는 이미 min-max normalization과 resampling이 완료된 16채널 perturbation EMG를 갖고 있고, 사용자는 현재 project pipeline의 trial selection과 window logic을 그대로 쓰길 원한다. 그래서 이번 작업은 “논문의 structural muscle-synergy logic을 현재 step-vs-nonstep perturbation dataset에 옮기는 adaptation”이다. 이 차이는 `report.md`의 `Methodological Adaptation` 섹션에서 반드시 표로 설명해야 한다.

English: This analysis does not reproduce the paper “as-is.” The paper used raw running EMG preprocessing, 15 muscles, and session-level comparisons across subject groups. The current project already has min-max normalized and resampled 16-channel perturbation EMG, and the user wants to keep the current project pipeline’s trial selection and window logic. Therefore this work is an adaptation: it moves the paper’s structural muscle-synergy logic into the current step-vs-nonstep perturbation dataset. That difference must be explained explicitly in a table inside the `Methodological Adaptation` section of `report.md`.

한국어: “trial synergy vector”는 한 trial에서 추출된 NMF `W`의 한 column이다. “activation coefficient”는 그 column에 대응되는 `H`의 한 row다. “common cluster”는 k-means cluster centroid이면서, 그 cluster에 속한 synergy들이 최소한 전체 subject의 `1/3` 이상에서 나온 경우를 뜻한다. “duplicate-free”는 같은 trial 안에서 나온 둘 이상의 synergy가 같은 cluster label을 공유하지 않게 만드는 규칙이다. “cross-fit”은 한 group의 synergy basis를 고정한 채 다른 group의 EMG를 재구성하고 `R²`를 보는 절차다. “merging”은 target synergy 하나가 source group의 둘 이상의 synergy를 non-negative linear combination으로 잘 설명될 때를 뜻하고, “fractionation”은 그 반대 방향 해석이다. “MI”는 target group의 synergy 중 몇 퍼센트가 merging으로 설명되는지를 나타내는 비율이다.

English: A “trial synergy vector” means one column of the NMF `W` matrix extracted from one trial. An “activation coefficient” means the matching row of `H`. A “common cluster” means a k-means cluster centroid for which the member synergies come from at least one-third of the subjects in that group. “Duplicate-free” means no two synergies from the same trial are allowed to share the same cluster label. “Cross-fit” means fixing the synergy basis from one group and reconstructing EMG from another group, then measuring `R²`. “Merging” means one target synergy can be well explained by a non-negative linear combination of two or more source-group synergies; “fractionation” is the reverse interpretation. “MI” is the percentage of target-group synergies that can be explained as merging.


## Plan of Work / 작업 계획

### Milestone 1 / 마일스톤 1 — Create the analysis workspace and a truthful dry-run

한국어: 먼저 `analysis/compare_Cheung,2021/` 안에 self-contained 분석 파일을 만든다. 이 폴더에는 최소한 `analyze_compare_cheung_synergy_analysis.py`, `report.md`, 그리고 이미 있는 참조 PDF가 유지되어야 한다. 구현자는 이 analysis가 pipeline을 재실행하지 않는다는 사실을 잊지 않도록, 스크립트의 첫 단계에서 `--run-dir` 아래 baseline artifact와 config에 연결된 normalized EMG/event 입력의 존재 여부를 모두 검사해야 한다. dry-run은 파일 존재 여부, schema, selected trial 수, step/nonstep trial 수, unique subject 수, muscle column 수만 출력하고 종료해야 한다. 이 dry-run은 “이 analysis가 baseline truth와 현재 입력 파일만으로 작동 가능한가?”를 가장 먼저 증명하는 단계다.

English: First create the self-contained analysis files inside `analysis/compare_Cheung,2021/`. The folder must contain at least `analyze_compare_cheung_synergy_analysis.py`, `report.md`, and the existing reference PDF. To prevent accidental pipeline coupling, the script must begin by checking both the baseline artifacts under `--run-dir` and the normalized EMG/event inputs referenced by the config. The dry-run must only print file existence, schema, selected-trial counts, step/nonstep counts, unique-subject counts, and the number of muscle columns, then exit. This dry-run is the first proof that the analysis can work from the baseline truth plus the current input files alone.

한국어: 이 단계에서 수정할 핵심 파일은 `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`와 `analysis/compare_Cheung,2021/report.md`다. 보고서는 아직 빈칸이 많아도 되지만, prior-study-replication 구조의 11개 섹션 제목은 모두 미리 있어야 한다. 스크립트는 `argparse`를 사용하고, `--dry-run`은 필수다.

English: The main files touched in this milestone are `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py` and `analysis/compare_Cheung,2021/report.md`. The report may still contain placeholders, but all 11 required section headings from the prior-study-replication structure must already exist. The script must use `argparse`, and `--dry-run` is mandatory.

### Milestone 2 / 마일스톤 2 — Recompute trial-level synergies using the paper-style NMF rule

한국어: 두 번째 단계는 config에 연결된 normalized EMG parquet와 event workbook에서 선택된 trial의 EMG 행렬을 다시 구성하고, 각 trial마다 논문식 NMF를 돌리는 것이다. 중요한 점은 baseline의 NMF 결과를 재사용하지 않는다는 것이다. baseline은 `VAF >= 0.90`와 project-specific normalization/representative export를 쓰므로, 이번 단계는 같은 trial window 위에서 “다른 NMF selection rule”을 다시 적용하는 재분석이다. 각 trial마다 time × muscles 행렬 `X`를 만들고, 값이 음수이면 즉시 오류로 멈춘다. 입력이 min-max normalized라고 해도 schema 오류나 잘못된 join이 있으면 음수가 생길 수 있기 때문이다.

English: The second milestone reconstructs the selected trial EMG matrices from the config-linked normalized EMG parquet and event workbook, then runs the paper-style NMF on each trial. The important point is that the baseline NMF results are not reused. The baseline uses `VAF >= 0.90` and project-specific normalization/representative export, so this stage is a re-analysis on the same trial window using a different NMF selection rule. For each trial, build a time × muscles matrix `X`, and stop with an error if any value is negative. Even if the input is min-max normalized, a schema error or a bad join can still create invalid values.

한국어: NMF routine은 스크립트 내부에 직접 구현한다. 각 rank `r`에 대해 `1..16`을 순서대로 시도한다. 각 rank에서는 `W`와 `H`를 `Uniform(0, X.max())`에서 20번 다르게 초기화한다. multiplicative update rule을 사용해 반복하고, `R² = 1 - SSE / SST`를 매 iteration마다 계산한다. `R²`의 절대 변화가 `1e-5`보다 작은 상태가 20 iteration 연속 유지되면 그 restart를 종료한다. 각 rank에서는 최고 `R²` restart만 보관한다. trial의 최종 rank는 `R² >= 0.80`를 처음 만족한 최소 rank다. 어떤 trial도 0.80에 도달하지 못하면 가장 높은 `R²` rank를 보관하되, 보고서에 threshold miss로 명시한다.

English: The NMF routine must be implemented directly inside the script. Try ranks `r = 1..16` in order. For each rank, initialize `W` and `H` 20 times from `Uniform(0, X.max())`. Use multiplicative update rules, and compute `R² = 1 - SSE / SST` at every iteration. Stop a restart when the absolute `R²` change stays below `1e-5` for 20 consecutive iterations. Keep only the highest-`R²` restart at each rank. The final rank for a trial is the smallest rank that reaches `R² >= 0.80`. If a trial never reaches 0.80, keep the highest-`R²` rank anyway and mark it as a threshold miss in the report.

한국어: NMF scale ambiguity를 없애기 위해, 최종으로 채택한 각 synergy vector는 clustering 전에 L2 unit vector로 정규화하고 그 norm을 activation 쪽으로 흡수한다. 이건 project-specific interpretation을 바꾸지 않는다. 단지 squared-Euclidean clustering, scalar product, NNLS reconstruction을 안정적으로 수행하기 위한 구현상 정리다.

English: To remove NMF scale ambiguity, normalize each final synergy vector to a unit L2 vector before clustering and absorb its norm into the activation side. This does not change the scientific interpretation. It is an implementation step that makes squared-Euclidean clustering, scalar products, and NNLS reconstruction stable.

### Milestone 3 / 마일스톤 3 — Prototype and then run duplicate-free gap-statistic clustering

한국어: 세 번째 단계는 가장 위험한 부분이다. 논문은 plain k-means와 gap statistic을 쓰지만, 현재 프로젝트는 trial 내부 duplicate-free cluster assignment를 요구한다. 이 둘을 합치기 위해, 먼저 prototype 모드에서 작은 설정으로 duplicate-free clustering이 제대로 작동하는지 검증하고, 그다음 full setting으로 올린다. prototype은 전체 데이터가 아니라 selected trial 중 앞의 소수 trial만 써도 된다. 목적은 “한 trial 안의 synergy가 같은 cluster에 겹치지 않으면서 centroid가 안정적으로 수렴하는가?”를 확인하는 것이다.

English: The third milestone is the riskiest. The paper uses plain k-means and the gap statistic, but the current project requires duplicate-free cluster assignment within each trial. To combine those two rules, first validate duplicate-free clustering in a prototype mode with small settings, then raise the settings to the full configuration. The prototype can use only a small subset of selected trials. Its purpose is to prove that synergies from the same trial do not collapse into the same cluster while centroids still converge stably.

한국어: full clustering algorithm은 다음 순서로 구현한다. 먼저 step pool과 nonstep pool을 완전히 분리한다. 각 group에서 candidate `k`는 `max(2, group_trial_rank_max)`부터 `min(20, n_synergies)`까지 탐색한다. 각 `k`에 대해 일반 k-means centroid를 여러 seed로 시작하고, 각 replicate마다 trial별 cost matrix를 만들어 Hungarian assignment로 duplicate-free label을 강제한다. 그런 다음 reassigned labels로 centroid를 다시 계산한다. labels가 안정화되거나 maximum repair iteration에 도달할 때까지 이 과정을 반복한다. 최종 objective는 모든 vector의 centroid 거리 제곱합이다. 이 duplicate-free objective는 실제 데이터와 gap statistic의 reference 데이터 양쪽에 동일하게 적용해야 한다.

English: The full clustering algorithm works in this order. Separate the step pool and the nonstep pool completely. For each group, search candidate `k` from `max(2, group_trial_rank_max)` to `min(20, n_synergies)`. For each `k`, start with ordinary k-means centroids across multiple seeds, then for each replicate build a trial-level cost matrix and use Hungarian assignment to force duplicate-free labels. Recompute centroids from the reassigned labels. Repeat until labels stabilize or a maximum number of repair iterations is reached. The final objective is the total sum of squared centroid distances across all vectors. This duplicate-free objective must be applied to both the observed data and the gap-statistic reference data.

한국어: prototype 설정은 `gap_ref_n = 20`, `gap_ref_restarts = 10`, `kmeans_restarts = 25` 정도로 작게 두고, full 설정은 paper-aligned `gap_ref_n = 500`, `gap_ref_restarts = 100`, `kmeans_restarts = 1000`으로 둔다. script는 prototype과 full의 결과를 명시적으로 구분해 stdout에 출력해야 한다. prototype이 통과하지 않으면 full run을 시작하지 않는다.

English: Use a small prototype setting such as `gap_ref_n = 20`, `gap_ref_restarts = 10`, and `kmeans_restarts = 25`, then switch to the paper-aligned full setting `gap_ref_n = 500`, `gap_ref_restarts = 100`, and `kmeans_restarts = 1000`. The script must print prototype and full results separately to stdout. If the prototype does not pass, the full run must not start.

한국어: clustering이 끝나면 각 cluster에서 unique subject 수를 세고, `>= ceil(n_subjects / 3)`를 만족하는 cluster만 common cluster로 남긴다. step common centroids와 nonstep common centroids는 unit vector로 정규화한 뒤 scalar product matrix를 계산하고, Hungarian one-to-one matching으로 총 SP 합이 최대가 되도록 짝을 찾는다. 어떤 pair의 `SP < 0.8`이면 그 pair는 matched로 기록하지 않고 unmatched로 남긴다.

English: After clustering, count the unique subjects in each cluster and keep only clusters with `>= ceil(n_subjects / 3)` as common clusters. Normalize the step common centroids and the nonstep common centroids to unit vectors, compute the scalar-product matrix, and use Hungarian one-to-one matching to maximize the total SP sum. If a pair has `SP < 0.8`, do not record it as a valid match; leave it unmatched.

### Milestone 4 / 마일스톤 4 — Add paper-style structural metrics and compare them with the baseline

한국어: 네 번째 단계는 논문의 structural metrics를 현재 step-vs-nonstep 문제에 맞게 옮기는 것이다. 첫째, sparseness는 Hoyer 공식을 사용한다. `n = 16`으로 계산하고, 각 vector의 sparseness를 구한다. main report는 vector-level distribution을 보여 주되, appendix 성격으로 subject-averaged sparseness도 함께 남겨 baseline과 paper interpretation의 차이를 줄인다.

English: The fourth milestone ports the paper’s structural metrics into the current step-vs-nonstep setting. First, compute sparseness with the Hoyer formula. Use `n = 16` and calculate one sparseness value per synergy vector. The main report should show the vector-level distribution, but it should also include a subject-averaged sparseness summary as an appendix-style sensitivity check to reduce the gap between the baseline weighting and the paper’s subject-centered interpretation.

한국어: 둘째, cross-fit은 pooled all-by-all 비교로 구현한다. step trial의 `W`를 고정하고 모든 nonstep trial의 EMG를 재구성하는 `step→nonstep` cross-fit, 그리고 반대로 `nonstep→step` cross-fit을 구한다. benchmark는 같은 group 내부의 between-trial cross-fit이다. 즉 step trial의 `W`를 다른 step trial의 EMG에 fit한 `step→step`, nonstep trial의 `W`를 다른 nonstep trial의 EMG에 fit한 `nonstep→nonstep`을 같이 계산한다. 같은 trial을 자기 자신에게 fit하는 경우는 제외한다. 보고서에는 각 방향의 mean/median `R²`, within-group benchmark와의 차이, 그리고 effect direction을 적는다.

English: Second, implement cross-fit as a pooled all-by-all comparison. Compute `step→nonstep` by holding the step trial `W` fixed and reconstructing every nonstep trial EMG, then compute `nonstep→step` in the reverse direction. The benchmark is the between-trial within-group fit: `step→step` where a step trial `W` fits a different step trial EMG, and `nonstep→nonstep` where a nonstep trial `W` fits a different nonstep trial EMG. Exclude self-fits. The report must state the mean/median `R²` in each direction, the difference from the within-group benchmark, and the direction of the effect.

한국어: 셋째, merging/fractionation은 두 수준으로 구현한다. centroid 수준에서는 nonstep centroid 하나를 step centroids 여러 개의 non-negative combination으로 재구성하고, 반대 방향도 똑같이 계산한다. 개별 synergy 수준에서는 target trial의 각 synergy 하나를 source group의 각 source trial synergy set으로 차례대로 NNLS reconstruction한다. 둘 다 `Nb >= 2`, 모든 coefficient `>= 0.2`, reconstruction `SP >= 0.8`를 만족하면 merging instance로 기록한다. 반대 방향 해석은 fractionation이다. 개별 synergy 수준 결과는 source cluster membership을 기준으로 combination을 묶고, target trial 단위 MI를 계산해 report에 넣는다.

English: Third, implement merging/fractionation at two levels. At the centroid level, reconstruct one nonstep centroid as a non-negative combination of multiple step centroids, then do the reverse direction as well. At the individual-synergy level, reconstruct each target trial synergy against each source-trial synergy set from the source group using NNLS. At both levels, record a merging instance only if `Nb >= 2`, every coefficient is `>= 0.2`, and the reconstruction `SP >= 0.8`. The reverse-direction interpretation is fractionation. For the individual-synergy analysis, group the results by source-cluster membership combination and compute the target-trial-level MI for the report.

한국어: 넷째, baseline comparison은 `default_run`만 쓴다. baseline group representative W는 step과 nonstep을 분리해 따로 읽는다. paper-style common centroids와 baseline representative W는 group 안에서만 비교한다. 즉 step paper centroid는 baseline step representative와만, nonstep paper centroid는 baseline nonstep representative와만 비교한다. 이 비교도 scalar product matrix와 Hungarian matching을 사용하고, `SP < 0.8`이면 unmatched로 둔다. 절대 step baseline cluster와 nonstep paper centroid를 섞지 않는다.

English: Fourth, compare only against `default_run`. Read baseline representative W separately for the step and nonstep groups. Compare paper-style common centroids only within the same group: paper step centroids against baseline step representatives, and paper nonstep centroids against baseline nonstep representatives. Use the scalar-product matrix plus Hungarian matching here as well, and leave any `SP < 0.8` pair unmatched. Never mix a step baseline cluster with a nonstep paper centroid.

### Milestone 5 / 마일스톤 5 — Finish the prior-study report and make the result human-checkable

한국어: 마지막 단계는 `report.md`를 prior-study-replication 구조에 맞게 완성하는 것이다. `Prior Studies` 섹션은 업로드한 논문의 방법론, 실험 설계, 핵심 수치 결과, 결론을 plain language로 요약한다. `Methodological Adaptation` 섹션에는 반드시 표가 있어야 하며, 최소한 다음 항목을 포함해야 한다: raw filtering replay 생략, 15근육→16채널, session/group comparison→trial-pooled step/nonstep, duplicate-free constraint 추가, temporal activation 분석 제외. `Comparison with Prior Studies` 섹션에는 verdict를 반드시 적되, 이 연구가 running expertise study가 아니라 perturbation step/nonstep study라는 이유로 `Partially consistent`와 `Not tested`가 많이 나와도 괜찮다.

English: The final milestone completes `report.md` using the prior-study-replication structure. The `Prior Studies` section must summarize the uploaded paper’s methodology, experimental design, key numerical results, and conclusions in plain language. The `Methodological Adaptation` section must contain a table and must include at least these items: skipping raw filtering replay, 15-muscle to 16-channel adaptation, session/group comparison to trial-pooled step/nonstep comparison, adding the duplicate-free constraint, and excluding temporal activation analysis. The `Comparison with Prior Studies` section must contain verdicts. It is acceptable for many rows to be `Partially consistent` or `Not tested` because this is a perturbation step/nonstep study, not a running-expertise study.

한국어: 이 단계가 끝났을 때 사용자가 확인해야 할 것은 단순하다. `report.md`에 baseline trial counts, paper-style trial counts, step/nonstep common cluster counts, matched/unmatched centroid 결과, cross-fit summary, merging/fractionation summary, 그리고 baseline-vs-paper comparison table이 모두 있어야 한다. 분석 스크립트를 다시 실행하면 같은 report가 안전하게 덮어써져야 하고, analysis 폴더 밖의 pipeline 산출물은 절대 바뀌면 안 된다.

English: At the end of this milestone, the user’s verification is simple. `report.md` must contain baseline trial counts, paper-style trial counts, step/nonstep common-cluster counts, matched/unmatched centroid results, a cross-fit summary, a merging/fractionation summary, and a baseline-vs-paper comparison table. Re-running the analysis script must safely overwrite the report, and no pipeline artifact outside the analysis folder may change.


## Concrete Steps / 구체적 실행 단계

한국어: 아래 단계는 저장소 루트에서 실행한다. 모든 Python 실행은 conda env `module`을 사용한다.

English: Run the following steps from the repository root. Use conda env `module` for every Python command.

1. 한국어: analysis 작업공간을 만든다. English: Create the analysis workspace.

    mkdir -p analysis/paper_step_nonstep_synergy

2. 한국어: 참조 PDF를 analysis 폴더로 복사한다. English: Copy the reference PDF into the analysis folder.

    cp s41467-020-18210-4.pdf analysis/paper_step_nonstep_synergy/s41467-020-18210-4.pdf

   한국어: 로컬 환경에서 PDF의 원래 위치가 다르면, 같은 이름으로 analysis 폴더 안에 두기만 하면 된다.
   English: If the PDF lives elsewhere in the local environment, it is enough to place it in the analysis folder with the same name.

3. 한국어: 스크립트와 보고서 skeleton을 만든다. English: Create the script and the report skeleton.

    touch analysis/paper_step_nonstep_synergy/analyze_paper_step_nonstep_synergy.py
    touch analysis/paper_step_nonstep_synergy/report.md

4. 한국어: dry-run을 먼저 구현하고 실행한다. English: Implement and run the dry-run first.

    conda run --no-capture-output -n module python analysis/paper_step_nonstep_synergy/analyze_paper_step_nonstep_synergy.py \
      --run-dir outputs/runs/default_run \
      --dry-run

   한국어: 기대 출력은 아래와 비슷해야 한다. exact 숫자는 다를 수 있지만, 항목은 같아야 한다.
   English: The expected output should look like this. The exact counts may differ, but the categories must match.

    [M1] Found run directory: outputs/runs/default_run
    [M1] Found manifest: all_trial_window_metadata.csv
    [M1] Found time-series parquet: outputs/final.parquet
    [M1] Found baseline representative W: all_representative_W_posthoc.csv
    [M1] Selected trials: step=<N>, nonstep=<N>, unique_subjects=<N>
    [M1] Muscle columns found: 16
    [M1] Dry-run complete. No analysis executed.

5. 한국어: prototype NMF + prototype clustering을 실행한다. English: Run prototype NMF plus prototype clustering.

    conda run --no-capture-output -n module python analysis/paper_step_nonstep_synergy/analyze_paper_step_nonstep_synergy.py \
      --run-dir outputs/runs/default_run \
      --prototype \
      --prototype-trials-per-group 4 \
      --prototype-gap-ref-n 20 \
      --prototype-gap-ref-restarts 10 \
      --prototype-kmeans-restarts 25

   한국어: 기대 출력은 “duplicate-free clustering feasible” 또는 같은 의미의 메시지를 포함해야 한다.
   English: The expected output must include a message equivalent to “duplicate-free clustering feasible.”

6. 한국어: full analysis를 실행한다. English: Run the full analysis.

    conda run --no-capture-output -n module python analysis/paper_step_nonstep_synergy/analyze_paper_step_nonstep_synergy.py \
      --run-dir outputs/runs/default_run \
      --seed 42

   한국어: 기대 출력은 아래 요소를 포함해야 한다.
   English: The expected output must include the following kinds of messages.

    [M2] Trial-level paper NMF complete: trials=<N>
    [M3] Step clustering complete: optimal_k=<K>, common_clusters=<Kc>
    [M3] Nonstep clustering complete: optimal_k=<K>, common_clusters=<Kc>
    [M3] Step↔Nonstep matching complete: matched=<M>, unmatched_step=<U>, unmatched_nonstep=<U>
    [M4] Cross-fit complete
    [M4] Centroid-level merging/fractionation complete
    [M4] Individual-level MI complete
    [M4] Baseline comparison complete
    [M5] report.md updated

7. 한국어: 보고서 섹션 순서와 내용이 prior-study-replication 요구사항을 만족하는지 확인한다. English: Verify that the report follows the prior-study-replication section order and content requirements.

8. 한국어: analysis 폴더 안에 CSV/Excel이 새로 생기지 않았는지 확인한다. English: Confirm that no new CSV or Excel file was generated inside the analysis folder.

    find analysis/paper_step_nonstep_synergy -maxdepth 2 -type f | sort

   한국어: 허용되는 핵심 파일은 스크립트, 보고서, PDF 사본, 그리고 선택적으로 PNG figure뿐이다.
   English: The core allowed files are the script, the report, the copied PDF, and optionally PNG figures.


## Validation and Acceptance / 검증 및 합격 기준

한국어: 이 작업은 “코드가 생겼다”가 아니라 “사람이 결과를 확인할 수 있다”가 합격 기준이다. 아래 조건을 모두 만족해야 한다.

English: The acceptance standard is not “code exists,” but “a human can verify the result.” All of the following must be true.

- 한국어: `--dry-run`이 성공하고, 선택된 step/nonstep trial 수와 unique subject 수를 출력한다.
  English: `--dry-run` succeeds and prints selected step/nonstep trial counts and unique subject counts.

- 한국어: full run이 성공하고 `analysis/paper_step_nonstep_synergy/report.md`를 갱신한다.
  English: The full run succeeds and updates `analysis/paper_step_nonstep_synergy/report.md`.

- 한국어: `report.md`는 다음 11개 섹션을 이 순서대로 가진다: `Research Question`, `Prior Studies`, `Methodological Adaptation`, `Data Summary`, `Analysis Methodology`, `Results`, `Comparison with Prior Studies`, `Interpretation & Conclusion`, `Limitations`, `Reproduction`, `Figures`.
  English: `report.md` contains these 11 sections in this exact order: `Research Question`, `Prior Studies`, `Methodological Adaptation`, `Data Summary`, `Analysis Methodology`, `Results`, `Comparison with Prior Studies`, `Interpretation & Conclusion`, `Limitations`, `Reproduction`, `Figures`.

- 한국어: `Methodological Adaptation` 표는 raw preprocessing replay omission, 15→16 channels, trial-pooled design, duplicate-free adaptation, temporal activation exclusion을 모두 설명한다.
  English: The `Methodological Adaptation` table explains all of the following: raw preprocessing replay omission, 15→16 channels, trial-pooled design, duplicate-free adaptation, and temporal activation exclusion.

- 한국어: step↔nonstep common cluster matching은 반드시 SP matrix 기반 1:1 matching으로 계산되고, `SP < 0.8`인 항목이 억지로 매칭되지 않는다.
  English: Step↔nonstep common-cluster matching is computed using a one-to-one SP-matrix match, and any item with `SP < 0.8` is not forced into a match.

- 한국어: final cluster labels는 모든 trial에 대해 duplicate-free 조건을 만족한다. 즉 같은 `(subject, velocity, trial_num, analysis_step_class)` 안에서 동일 cluster label이 두 번 나오지 않는다.
  English: The final cluster labels satisfy the duplicate-free rule for every trial. In other words, the same cluster label never appears twice inside the same `(subject, velocity, trial_num, analysis_step_class)`.

- 한국어: baseline comparison은 group 내부에서만 일어난다. step paper centroid는 baseline step representative와만, nonstep paper centroid는 baseline nonstep representative와만 비교된다.
  English: Baseline comparison happens only within the same group. Paper step centroids are compared only with baseline step representatives, and paper nonstep centroids only with baseline nonstep representatives.

- 한국어: analysis 폴더 안에 Excel/CSV가 새로 생성되지 않는다.
  English: No new Excel or CSV file is generated inside the analysis folder.

- 한국어: pipeline 코드, `configs/`, `scripts/`, `src/`, `main.py`, raw data는 수정되지 않는다.
  English: The pipeline code, `configs/`, `scripts/`, `src/`, `main.py`, and raw data remain untouched.


## Idempotence and Recovery / 반복 실행 안전성과 복구

한국어: 이 analysis는 여러 번 다시 실행해도 안전해야 한다. `report.md`와 선택적 PNG figure는 매번 덮어써도 된다. baseline run 디렉터리는 read-only로 취급한다. 스크립트가 중간에 실패해도 `outputs/runs/default_run` 안의 파일은 절대 수정하지 않는다. 만약 run directory schema가 예상과 다르면, 스크립트는 즉시 명확한 오류를 내고 멈춰야 한다. 잘못된 schema를 억지로 해석해서 계속 진행하면 안 된다.

English: This analysis must be safe to re-run multiple times. `report.md` and optional PNG figures may be overwritten on each run. Treat the baseline run directory as read-only. Even if the script fails halfway, it must never modify anything inside `outputs/runs/default_run`. If the run-directory schema differs from what the script expects, the script must stop immediately with a clear error. It must not attempt to guess and continue with a misread schema.

한국어: prototype 단계가 실패하면 full 단계로 넘어가지 않는다. prototype settings를 줄여서 문제를 분리한 뒤 고치고 다시 시작한다. full run이 끝난 뒤 report가 부분적으로만 쓰여 있으면, 다음 실행에서 report 전체를 처음부터 다시 생성한다. 부분 append는 금지한다.

English: If the prototype stage fails, do not move on to the full stage. Reduce the prototype settings to isolate the problem, fix it, and restart. If a full run leaves behind a partially written report, the next run must regenerate the entire report from scratch. Partial append mode is forbidden.


## Artifacts and Notes / 산출물과 메모

한국어: 구현이 끝났을 때 analysis 폴더의 최소 형태는 아래와 같아야 한다.

English: At minimum, the analysis folder should look like this at the end.

    analysis/paper_step_nonstep_synergy/
      analyze_paper_step_nonstep_synergy.py
      report.md
      s41467-020-18210-4.pdf

한국어: 선택적으로 아래와 같은 figure가 추가될 수 있다. 하지만 figure는 필수가 아니며, 추가하더라도 CSV/Excel 대신 PNG만 허용한다.

English: The following figures may optionally be added. They are not required, and if they exist they must be PNG only, never CSV or Excel.

    analysis/paper_step_nonstep_synergy/figures/
      step_common_centroids.png
      nonstep_common_centroids.png
      step_nonstep_sp_heatmap.png
      paper_vs_baseline_sp_heatmap.png

한국어: report의 Results 섹션에는 최소한 다음 내용이 plain language로 있어야 한다: step/nonstep selected trial 수, unique subject 수, paper-style rank 분포, baseline-vs-paper rank 차이, step/nonstep common cluster 수, matched/unmatched centroid 목록, cross-fit 방향별 요약, centroid-level merging/fractionation, individual-level MI summary, baseline representative와의 correspondence 결과.

English: The `Results` section of the report must contain at least the following in plain language: the selected step/nonstep trial counts, the unique-subject count, the paper-style rank distribution, the baseline-vs-paper rank difference, the step/nonstep common-cluster counts, the matched/unmatched centroid list, the direction-wise cross-fit summary, centroid-level merging/fractionation, the individual-level MI summary, and the correspondence between paper centroids and baseline representatives.


## Interfaces and Dependencies / 인터페이스와 의존성

한국어: 구현자는 다음 라이브러리를 사용한다. `polars`는 I/O와 grouping의 기본 라이브러리다. `numpy`는 NMF, distance, scalar product 계산에 사용한다. `scipy.optimize.nnls`는 merging reconstruction에 사용한다. `scipy.optimize.linear_sum_assignment`는 duplicate-free trial assignment와 centroid matching 둘 다에 사용한다. `sklearn.cluster.KMeans`는 초기 centroid candidate를 만드는 용도로 사용할 수 있지만, duplicate-free repair와 gap statistic loop는 반드시 스크립트 로직에서 직접 관리한다. `pandas`는 꼭 필요할 때만 사용한다.

English: The implementation uses these libraries. `polars` is the default library for I/O and grouping. `numpy` is used for NMF, distance, and scalar-product calculations. `scipy.optimize.nnls` is used for merging reconstruction. `scipy.optimize.linear_sum_assignment` is used both for duplicate-free trial assignment and for centroid matching. `sklearn.cluster.KMeans` may be used only to propose initial centroids, but the duplicate-free repair and the gap-statistic loop must be controlled directly by the script. Use `pandas` only when truly necessary.

한국어: 스크립트 안에는 아래 dataclass 또는 동등한 구조가 최종적으로 존재해야 한다. 이름은 바꾸지 않는다.

English: The script must define the following dataclasses, or equivalent structures with these exact names. Do not rename them.

    PaperMethodConfig
    TrialSynergyResult
    ClusterSearchResult
    CommonClusterSummary
    CrossFitSummary
    MergeFractionSummary
    BaselineComparisonSummary

한국어: 스크립트 안에는 아래 함수들이 최종적으로 존재해야 한다. 시그니처의 세부 type annotation은 달라도 되지만, 함수 이름과 역할은 유지한다.

English: The script must contain the following functions at the end. The exact type annotations may vary, but the function names and responsibilities must remain.

    parse_args()
    load_baseline_inputs(run_dir, config)
    validate_final_parquet_schema(df, config)
    select_trials_from_manifest(manifest_df, config)
    build_trial_matrix_dict(final_df, manifest_df, config)
    run_paper_nmf_for_trial(X, config, seed)
    summarize_trial_synergies(trial_results, config)
    duplicate_free_kmeans(vectors, trial_keys, k, config, seed)
    compute_gap_statistic(vectors, trial_keys, k_values, config, seed)
    identify_common_clusters(cluster_df, manifest_df, config)
    match_cluster_centroids(step_centroids, nonstep_centroids, config)
    compute_sparseness(vector)
    run_cross_fit(source_trials, target_trials, config)
    detect_centroid_level_merging(source_centroids, target_centroids, config)
    detect_individual_level_merging(source_trials, target_trials, source_cluster_map, config)
    compare_with_baseline_representatives(paper_results, baseline_w_df, config)
    render_report(results, config, report_path)
    main()

한국어: `main()`은 milestone style로 구성한다. stdout에는 반드시 `[M1]`, `[M2]`, `[M3]`, `[M4]`, `[M5]` 접두사가 있어야 한다. 이 접두사는 사람이 로그를 읽을 때 어느 단계에서 멈췄는지 한눈에 알게 해 준다.

English: `main()` must follow the milestone style. Stdout must use the prefixes `[M1]`, `[M2]`, `[M3]`, `[M4]`, and `[M5]`. These prefixes let a human see instantly which stage failed or completed.

한국어: `report.md`는 prior-study-replication 구조를 따르며, 새 analysis가 논문 결과를 그대로 복제하지 않는 이유를 숨기지 말아야 한다. 오히려 adaptation rationale을 가장 분명하게 드러내야 한다. 이 문서는 사용자가 결과를 해석할 때 가장 먼저 읽는 artifact다.

English: `report.md` must follow the prior-study-replication structure and must not hide the fact that the analysis does not reproduce the paper verbatim. The adaptation rationale should be one of the clearest parts of the document. This file is the primary user-facing artifact for interpretation.


## Revision Note / 개정 메모

한국어: 이 문서는 요구사항 discovery 직후 작성한 초기 ExecPlan이다. 사용자가 고정한 선택 사항은 이미 `Decision Log`에 반영되어 있으며, 구현이 진행되면 `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective`를 반드시 함께 갱신한다.

English: This document is the initial ExecPlan written immediately after requirements discovery. The user’s locked choices are already reflected in the `Decision Log`. As implementation proceeds, `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be updated together.
