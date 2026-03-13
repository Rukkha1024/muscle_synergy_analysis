# Align `compare_Cheung,2021` with the PDF for plain k-means and NMF / `compare_Cheung,2021`를 PDF 기준 plain k-means와 NMF에 맞춰 재정렬하기

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

이 문서는 `.agents/PLANS.md`를 따르는 수정 ExecPlan이다. 구현 단계에서는 이 문서를 기준으로 진행하고, 저장소 규칙에 따라 `analysis/` 바깥의 pipeline 코드는 건드리지 않는다. 또한 `AGENTS.md`의 요구에 따라 구현 시작 전 issue 문서를 만들고, 구현 후 explorer/reviewer 점검과 검증을 완료한 뒤 마무리한다.

This document is a revision ExecPlan that follows `.agents/PLANS.md`. During implementation it becomes the source of truth, pipeline code outside `analysis/` must remain untouched, and the repository rules in `AGENTS.md` still apply. Before implementation starts, issue documents must exist. After implementation, explorer/reviewer checks and validation must be completed before the task is closed.

## Purpose / 목적

한국어: 이 수정이 끝나면 `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`는 현재 프로젝트의 step/nonstep trial selection과 analysis window는 유지하되, k-means와 NMF의 핵심 규칙을 기존 “project adaptation”보다 논문 PDF에 더 가깝게 수행한다. 특히 clustering은 더 이상 trial 내부 중복 제거를 강제하지 않고, 논문처럼 `K = 2..20`의 plain k-means와 gap statistic으로 최종 K를 고른다. README와 보고서 설명도 이 변경을 반영해, 무엇이 논문과 같고 무엇이 아직 adaptation인지 사용자가 바로 구분할 수 있어야 한다.

English: After this revision, `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py` will keep the project’s current step/nonstep trial selection and analysis windows, but the core k-means and NMF rules will move closer to the PDF than the current project-style adaptation. In particular, clustering will no longer enforce within-trial uniqueness. Instead, it will follow the paper-style plain k-means over `K = 2..20` and use the gap statistic to choose the final K. The README and report text must also be updated so a user can immediately distinguish which parts now match the paper and which parts remain adaptations.

## Progress / 진행 상황

- [x] (2026-03-13T00:00+09:00) 한국어: 사용자와 수정 목표를 고정했다. duplicate-free 재배정은 제거하고, `K=2..20` plain k-means + gap statistic으로 바꾼다. 16채널은 유지하고, NMF의 나머지 규칙은 논문식으로 정렬한다. `R²` 정의와 README 설명도 수정 범위에 포함한다.
- [x] (2026-03-13T00:00+09:00) English: The revision scope is locked with the user. Remove duplicate-free reassignment, switch to plain k-means over `K=2..20` plus the gap statistic, keep 16 channels, align the remaining NMF rules with the paper, and include the `R²` definition and README explanation in the revision scope.
- [x] (2026-03-13T17:10+09:00) 한국어: `docs/issue/issue004.md`와 `docs/dev/issue/issue004.ko.md`를 만들고, 이번 PDF 정렬 수정 작업을 추적하기 시작했다.
- [x] (2026-03-13T17:10+09:00) English: Created `docs/issue/issue004.md` and `docs/dev/issue/issue004.ko.md` to track this PDF-alignment revision.
- [x] (2026-03-13T17:18+09:00) 한국어: 스크립트에서 duplicate-free clustering, prototype gate, `--paper-full` 분기를 제거하고 plain k-means + centered-`R²` 경로로 교체했다. README와 generated report wording도 새 로직에 맞춰 정렬했다.
- [x] (2026-03-13T17:18+09:00) English: Replaced duplicate-free clustering, the prototype gate, and the `--paper-full` branch with a plain-k-means plus centered-`R²` path. Updated the README and generated report wording so they match the new logic.
- [x] (2026-03-13T17:27+09:00) 한국어: `py_compile`, `--dry-run`, 그리고 축소 clustering override를 사용한 full run을 반복 실행했다. 수정 전 checksum은 `checksums_before_pdf_alignment.md5`로 보존했고, 수정 후 산출물 checksum은 의도된 방법 변경 때문에 달라졌다.
- [x] (2026-03-13T17:27+09:00) English: Repeated `py_compile`, `--dry-run`, and full runs with reduced clustering overrides. Preserved the pre-revision checksum snapshot in `checksums_before_pdf_alignment.md5`, and the post-revision artifact checksums changed as expected because the method changed.
- [x] (2026-03-13T17:49+09:00) 한국어: 축소 override full run을 두 번 다시 실행해 `checksums_validation_final_run1.md5`와 `checksums_validation_final_run2.md5`가 동일함을 확인했고, 현재 `checksums.md5`에 대해 `md5sum -c`도 통과했다.
- [x] (2026-03-13T17:49+09:00) English: Re-ran the reduced-override full analysis twice, confirmed that `checksums_validation_final_run1.md5` and `checksums_validation_final_run2.md5` are identical, and verified that `md5sum -c` passes against the current `checksums.md5`.
- [x] (2026-03-13T18:00+09:00) 한국어: explorer pass로 active execution path를 다시 확인했고, 최종 reviewer pass에서 scoped diff에 concrete finding이 없다는 sign-off를 받았다. 이제 issue 문서와 commit만 마감하면 된다.
- [x] (2026-03-13T18:00+09:00) English: The explorer pass reconfirmed the active execution path, and the final reviewer pass signed off with no concrete findings in the scoped diff. Only the issue close-out and commit remain.

## Surprises & Discoveries / 예상 밖 발견 사항

- Observation: 현재 `compare_Cheung` 구현은 논문식 gap statistic 외에도 trial 내부 duplicate-free Hungarian repair를 직접 포함하고 있다.
  Evidence: `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`의 `duplicate_free_kmeans()`가 `linear_sum_assignment`로 라벨을 강제 재배정한다.

- Observation: 현재 `compare_Cheung`의 `R²` 계산식은 논문과 완전히 같지 않다.
  Evidence: 현재 `_r2_score()`는 `sst = sum(X*X)` 형태를 사용한다. 논문 방법 설명은 각 muscle mean을 뺀 뒤의 총 변동을 기준으로 `R²`를 정의하는 해석이 더 자연스럽다.

- Observation: 현재 README는 “paper-style adaptation” 설명과 “duplicate-free 유지” 설명이 섞여 있어, 사용자가 논문 원형과 현재 구현을 혼동하기 쉽다.
  Evidence: `analysis/compare_Cheung,2021/README.md`는 duplicate-free constraint를 유지한다고 명시하고 있고, 이는 이번 수정 목표와 충돌한다.

- Observation: 현재 분석 입력은 이미 전처리된 perturbation EMG이며, 논문은 raw running EMG를 사용했다.
  Evidence: 실제 분석은 config 기반 normalized parquet와 baseline metadata를 읽는다. 따라서 완전한 raw-preprocessing 재현은 불가능하고, 이 차이는 수정 후에도 README에 남겨야 한다.

- Observation: 논문 정렬 기본값을 그대로 두면 local full run이 매우 무거워서, 검증은 CLI override를 사용한 축소 run으로 먼저 확인하는 편이 현실적이다.
  Evidence: paper-aligned default counts는 observed `1000`, reference `500 x 100`이라 전체 k-means 호출 수가 매우 커진다. 이번 검증은 `--kmeans-restarts 10 --gap-ref-n 5 --gap-ref-restarts 3`로 줄인 run에서 end-to-end 통과와 checksum 재현성을 확인했다.

## Decision Log / 결정 로그

- Decision: clustering은 논문처럼 `K=2..20` plain k-means + gap statistic으로 되돌리고, within-trial duplicate-free 제약은 완전히 제거한다.
  Rationale: 사용자가 가장 중요한 변경으로 이 항목을 명시했고, 논문 본문에도 duplicate-free 재배정은 핵심 규칙으로 제시되지 않는다.
  Date/Author: 2026-03-13 / GPT-5.4 Pro

- Decision: 16채널 입력은 유지하고, NMF 규칙만 논문식으로 맞춘다.
  Rationale: 사용자가 16채널 유지 의사를 분명히 밝혔고, 현재 데이터셋 구조도 16채널이 기준이다.
  Date/Author: 2026-03-13 / GPT-5.4 Pro

- Decision: `R²` 정의 차이도 수정 범위에 포함하고, low-level convergence detail처럼 논문이 직접 말하지 않는 부분만 구현 세부로 남긴다.
  Rationale: 사용자가 `R²` 정의 수정까지 승인했다. 논문에 없는 세부 동작은 “구현 선택”으로 문서화하되, 논문에 있는 수식과 선택 규칙은 맞춘다.
  Date/Author: 2026-03-13 / GPT-5.4 Pro

- Decision: README뿐 아니라 script가 생성하거나 하드코딩한 method summary 문장도 함께 수정한다.
  Rationale: README만 바꾸고 report/script 설명이 예전 상태로 남으면 다시 혼동이 생긴다.
  Date/Author: 2026-03-13 / GPT-5.4 Pro

- Decision: 검증은 “논문과 입력 데이터가 완전히 같아졌다”가 아니라 “논문이 명시한 NMF와 plain k-means 규칙이 현재 데이터셋 위에 정확히 반영되었다”를 기준으로 한다.
  Rationale: 입력 데이터와 전처리 자체가 논문과 다르므로, acceptance는 method alignment와 reproducibility에 둬야 한다.
  Date/Author: 2026-03-13 / GPT-5.4 Pro

## Outcomes & Retrospective / 결과 및 회고

한국어: 구현, 검증, explorer/reviewer 점검이 모두 끝났다. 새 k-means/NMF 규칙은 실제 스크립트 기본값에 반영되었고, README와 generated report는 duplicate-free 설명을 제거한 새 방법론을 공유한다. 수정 전후 checksum 비교 결과, `report.md`와 모든 figure가 바뀌었으며 이는 centered-`R²`와 plain k-means 전환에 따른 의도된 결과다. 또한 축소 override full run을 두 번 반복한 validation checksum manifest가 서로 일치해, 현재 checked-in artifacts는 재현 가능함을 확인했다.

English: Implementation, validation, and explorer/reviewer checks are now complete. The new k-means/NMF rules are active in the script defaults, and the README plus generated report now share the revised method without the duplicate-free explanation. The before-versus-after checksum comparison shows that `report.md` and every figure changed, which is the expected outcome of switching to centered `R²` and plain k-means. The reduced-override full run also produced identical validation checksum manifests across repeated executions, confirming reproducibility for the checked-in artifacts.

## Context and Orientation / 현재 맥락과 구조 설명

한국어: 이 작업의 핵심 파일은 `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`다. 이 스크립트는 baseline trial truth를 `outputs/runs/default_run/all_trial_window_metadata.csv`에서 읽고, config에 연결된 normalized EMG parquet와 event workbook으로 trial matrix를 다시 구성한 뒤, paper-style 분석 결과와 baseline representative synergy를 비교한다. 현재 문제는 이 스크립트가 논문식 gap statistic 위에 project-specific duplicate-free repair를 더하고 있고, NMF의 `R²` 계산식도 논문과 완전히 같지 않다는 점이다.

English: The central file for this work is `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`. The script reads baseline trial truth from `outputs/runs/default_run/all_trial_window_metadata.csv`, reconstructs trial matrices from the config-linked normalized EMG parquet and event workbook, then compares the paper-style analysis results with the baseline representative synergies. The current problem is that the script adds a project-specific duplicate-free repair layer on top of the paper-style gap statistic, and its NMF `R²` calculation is not fully aligned with the paper.

한국어: 이 수정에서는 pipeline 자체를 바꾸지 않는다. `src/` 아래의 baseline clustering logic도 바꾸지 않는다. 수정 범위는 analysis script, analysis README, report 설명, revision ExecPlan, issue 문서, 검증 checksum 기록으로 제한한다. baseline run은 비교 대상이지 수정 대상이 아니다.

English: This revision does not modify the pipeline itself. It also does not modify the baseline clustering logic under `src/`. The change scope is limited to the analysis script, the analysis README, the report explanation, the revision ExecPlan, the issue documents, and validation checksum records. The baseline run remains the comparison target, not the thing being changed.

한국어: “plain k-means”는 trial key를 보지 않고 pooled synergy vectors만 가지고 centroid를 찾는 일반 k-means를 뜻한다. “gap statistic”은 실제 데이터의 clustering objective와 uniform reference data의 clustering objective를 비교해 적절한 K를 고르는 방법이다. “centered `R²`”는 reconstruction error를 raw energy가 아니라 평균을 뺀 총변동과 비교하는 방식이다. 이 세 용어를 이후 섹션에서도 같은 의미로 사용한다.

English: “Plain k-means” means standard k-means that finds centroids from pooled synergy vectors without using trial keys. “Gap statistic” means choosing K by comparing the clustering objective on the observed data against the objective on uniform reference data. “Centered `R²`” means measuring reconstruction error against total variance after subtracting the mean, not against raw signal energy. These terms keep the same meaning throughout the rest of this plan.

## Plan of Work / 작업 계획

한국어: 첫 번째 구현 단계는 tracking artifact를 정리하는 것이다. 새 issue 문서를 만들고, 기존 `analysis/compare_Cheung,2021/exceplan_compare_cheung_synergy_analysis.md`는 구현 이력을 보존하기 위해 그대로 둔다. 대신 이번 수정만 다루는 revision ExecPlan을 추가해, 초보자도 “왜 새 수정이 필요한지”를 독립적으로 읽을 수 있게 한다.

English: The first implementation step is to organize the tracking artifacts. Create the new issue documents, and keep the existing `analysis/compare_Cheung,2021/exceplan_compare_cheung_synergy_analysis.md` intact so it preserves the earlier implementation history. Add this revision ExecPlan so that a novice can independently understand why the new revision is needed.

한국어: 두 번째 단계는 analysis script의 method core를 교체하는 것이다. `duplicate_free_kmeans()`, trial-key 기반 재배정, prototype-only duplicate-free feasibility gate, 그리고 `k_min = max(cluster_k_min, trial_rank_max)` 같은 duplicate-free 전제 코드를 제거한다. 새 clustering path는 step/nonstep group별로 pooled vectors만 받아 `K = 2..20`을 평가하되, 벡터 수가 20보다 적으면 수학적으로 가능한 최대 K까지만 본다. 각 K에서는 plain k-means를 1000회 반복하고, 각 반복은 random centroid initialization과 squared-Euclidean objective를 사용하며, 가장 작은 objective 해를 observed solution으로 채택한다. reference data는 각 K에서 500개를 만들고, 각 reference set마다 plain k-means를 100회 반복해 가장 작은 objective를 고른다. 최종 K는 standard gap-statistic rule로 선택한다.

English: The second step is to replace the method core inside the analysis script. Remove `duplicate_free_kmeans()`, all trial-key-based reassignment, the prototype-only duplicate-free feasibility gate, and any lower-bound logic such as `k_min = max(cluster_k_min, trial_rank_max)` that exists only because of the duplicate-free rule. The new clustering path takes pooled vectors per step/nonstep group and evaluates `K = 2..20`, capped only by the mathematical sample limit when the number of vectors is below 20. For each K, run plain k-means 1000 times with random centroid initialization and the squared-Euclidean objective, then keep the smallest-objective observed solution. For the reference data, generate 500 datasets per K and run plain k-means 100 times on each reference dataset, again keeping the smallest objective. Select the final K with the standard gap-statistic rule.

한국어: 세 번째 단계는 NMF를 논문 설명에 더 가깝게 정렬하는 것이다. 채널 수는 16으로 유지하되 rank 탐색도 `1..16`으로 유지한다. 각 rank에서 random initialization을 20회 시도하고, 각 trial의 최종 rank는 `R² >= 0.80`을 처음 만족하는 최소 rank로 고른다. 중요한 수정은 `R²` 정의다. `_r2_score()`를 centered total variance 기반으로 바꾼다. 즉 reconstruction error `SSE`는 그대로 두되, `SST`는 각 muscle의 시간 평균을 뺀 뒤의 총 제곱합으로 계산한다. 논문이 직접 말하지 않은 low-level optimizer detail은 최소 변경 원칙으로 구현하되, README에 “논문이 명시한 것은 rank rule, restart rule, `R²` threshold이며, solver convergence detail은 구현 세부”라고 적는다.

English: The third step is to align the NMF stage more closely with the paper. Keep the 16-channel input, and therefore keep the rank search over `1..16`. At each rank, use 20 random initializations, and choose the final trial rank as the smallest rank that first reaches `R² >= 0.80`. The critical fix here is the `R²` definition. `_r2_score()` must be changed so it uses centered total variance. That means the reconstruction error `SSE` stays as-is, but `SST` is computed as the total sum of squares after subtracting each muscle’s temporal mean. If the paper does not specify a low-level optimizer detail, implementation should follow the minimal-change rule and the README must state that the paper specifies the rank rule, restart rule, and `R²` threshold, while the solver convergence detail remains an implementation choice.

한국어: 네 번째 단계는 generated narrative를 정리하는 것이다. script 안의 method summary 문장, `report.md`에 들어가는 clustering/NMF 설명, `analysis/compare_Cheung,2021/README.md`의 방법론 설명을 모두 같은 언어로 맞춘다. 수정 후 README는 최소한 네 가지를 분명히 말해야 한다. 첫째, clustering은 이제 duplicate-free가 아니라 논문식 plain k-means다. 둘째, NMF는 16채널을 유지한 논문식 rank/restart/centered-`R²` 규칙이다. 셋째, 여전히 raw running EMG 재현은 아니고 현재 프로젝트의 preprocessed perturbation EMG adaptation이다. 넷째, trial/window truth는 baseline pipeline metadata를 그대로 사용한다. 기존 Markdown 구조와 문체는 최대한 보존한다.

English: The fourth step is to clean up the generated narrative. The method-summary text inside the script, the NMF/clustering explanations that appear in `report.md`, and the methodology section in `analysis/compare_Cheung,2021/README.md` must all describe the same revised method. After the change, the README must say at least four things clearly. First, clustering is no longer duplicate-free and now uses the paper-style plain k-means. Second, NMF now follows the paper-style rank, restart, and centered-`R²` rules while still keeping 16 channels. Third, the analysis is still an adaptation to preprocessed perturbation EMG rather than a full raw-running-EMG reproduction. Fourth, trial and window truth still come directly from the baseline pipeline metadata. Preserve the existing Markdown structure and style as much as possible.

한국어: 다섯 번째 단계는 validation과 cleanup이다. dry-run이 성공해야 하고, full run이 끝까지 돌아야 하며, 생성된 figures와 report가 새 설명을 반영해야 한다. logic이 바뀌므로 기존 `analysis/compare_Cheung,2021/checksums.md5`는 새로 생성해야 한다. 동시에 수정 전 주요 산출물의 checksum도 보관해, 이전 결과와 달라지는 것이 의도된 method revision 때문임을 증명한다. 마지막으로 explorer와 reviewer sub-agent를 실행해 변경 경로와 diff를 독립 점검하고, 필요한 수정 후 한 번 더 review pass를 돌린다.

English: The fifth step is validation and cleanup. The dry-run must pass, the full run must complete, and the generated figures and report must reflect the new explanation. Because the logic changes, the existing `analysis/compare_Cheung,2021/checksums.md5` must be regenerated. At the same time, pre-change checksums must be preserved so that the difference from the previous outputs is explicitly documented as an intended method revision. Finally, run explorer and reviewer sub-agents to inspect the touched code paths and the diff independently, then perform one more review pass if any concrete issue is found.

## Concrete Steps / 구체 단계

한국어: 구현자는 아래 순서로 작업한다. 모든 명령은 repo root인 `/home/alice/workspace/26-03-synergy-analysis`에서 실행한다.

English: The implementer follows the steps below. All commands run from the repository root `/home/alice/workspace/26-03-synergy-analysis`.

    1. 새 issue 문서를 만들고 checksum snapshot을 남긴다.
    2. analysis script의 duplicate-free 관련 함수와 CLI를 plain-kmeans 기준으로 교체한다.
    3. README와 report 설명을 수정하거나 재생성한다.
    4. dry-run을 실행한다.
       conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py --dry-run
    5. full run을 실행한다.
       conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py
    6. 같은 명령을 한 번 더 실행해 재현성 checksum을 만든다.
    7. explorer와 reviewer를 실행해 코드 경로, regression, 설명 문구 일관성을 점검한다.
    8. 한국어 5줄 이상 커밋 메시지로 커밋한다.

## Validation and Acceptance / 검증 및 완료 기준

한국어: 이 수정의 acceptance는 “논문과 입력 데이터가 완전히 같아졌다”가 아니라 “논문이 명시한 NMF와 plain k-means 규칙이 현재 데이터셋 위에 정확히 반영되었다”이다. 구현 후 아래 조건을 모두 만족해야 한다.

English: Acceptance for this revision does not mean “the method is now identical to the paper in every dataset detail.” It means “the paper-specified NMF and plain k-means rules are correctly reflected on top of the current dataset.” After implementation, all of the conditions below must hold.

- `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`에 trial-key 기반 duplicate-free 재배정 함수와 그 호출 경로가 남아 있지 않아야 한다.
- The analysis script must no longer contain a trial-key-based duplicate-free reassignment path.

- clustering 후보 K는 각 group에 대해 `2..20`을 기준으로 평가해야 하며, lower bound가 trial rank maximum 때문에 올라가면 안 된다. 다만 샘플 수가 부족한 경우의 수학적 상한 보정은 허용된다.
- Candidate K must be evaluated from `2..20` per group, without raising the lower bound because of trial-rank maxima. Only the mathematical cap from insufficient sample count is allowed.

- plain k-means observed search는 1000 repeats, reference gap search는 500 reference datasets × 100 repeats를 기본값으로 사용해야 한다.
- The default plain-k-means observed search must use 1000 repeats and the reference gap search must use 500 reference datasets times 100 repeats.

- NMF는 16채널 입력을 유지하면서 `1..16`, 20 restarts, centered `R²`, `R² >= 0.80` minimum-rank rule을 사용해야 한다.
- NMF must keep the 16-channel input while using `1..16`, 20 restarts, centered `R²`, and the minimum-rank rule at `R² >= 0.80`.

- `analysis/compare_Cheung,2021/README.md`는 duplicate-free 설명을 제거하고, 새 plain-kmeans/NMF 규칙과 남아 있는 adaptation 범위를 명확히 설명해야 한다.
- The README must remove the duplicate-free explanation and clearly describe the new plain-kmeans/NMF rules and the remaining adaptation scope.

- `analysis/compare_Cheung,2021/report.md`와 script-generated method summary는 README와 충돌하지 않아야 한다.
- The report and any script-generated method summary must not conflict with the README.

- full run을 두 번 실행했을 때 새 출력 checksum이 재현 가능해야 한다.
- Running the full analysis twice must produce reproducible output checksums.

- 이전 결과와 checksum이 달라지는 경우, 그 차이는 method revision 때문에 예상된 변화로 문서에 설명되어야 한다.
- If the new checksums differ from the previous outputs, the difference must be documented as an expected consequence of the method revision.

## Idempotence and Recovery / 멱등성과 복구

한국어: 이 수정은 analysis 폴더 안에서만 이뤄져야 하므로, rerun은 안전해야 한다. dry-run과 full run은 같은 경로의 `report.md`, figures, checksum 파일을 덮어써도 된다. 만약 run이 중간에 실패하면, analysis 산출물만 삭제하거나 다시 덮어써서 재시도한다. baseline pipeline 산출물과 `src/` 코드는 복구 대상으로 건드리지 않는다.

English: This revision stays inside the analysis folder, so reruns must be safe. The dry-run and full run may overwrite `report.md`, figures, and checksum files in the same analysis path. If a run fails midway, the retry path is simply to delete or overwrite the analysis artifacts and rerun. Baseline pipeline artifacts and code under `src/` are not part of any rollback path.

## Artifacts and Notes / 산출물과 비고

한국어: 구현 후 최소한 다음 파일이 갱신되어야 한다. `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`, `analysis/compare_Cheung,2021/README.md`, `analysis/compare_Cheung,2021/report.md`, `analysis/compare_Cheung,2021/checksums.md5`, 새 revision ExecPlan 파일, issue 문서. commit hash와 reviewer 결과도 함께 기록한다.

English: After implementation, at minimum the following files must be updated: `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`, `analysis/compare_Cheung,2021/README.md`, `analysis/compare_Cheung,2021/report.md`, `analysis/compare_Cheung,2021/checksums.md5`, the new revision ExecPlan file, and the issue documents. The commit hash and reviewer result should also be recorded.

## Interfaces and Dependencies / 인터페이스와 의존성

한국어: 구현은 `polars`를 기본 I/O 라이브러리로 유지하고, 현재 script가 이미 사용하는 `numpy`, `pandas`, `scipy`, `sklearn.cluster.KMeans`를 계속 사용한다. 새 plain-kmeans helper가 추가된다면 그 함수는 trial key를 인자로 받지 않아야 하며, 최소한 `vectors`, `k`, `repeats`, `seed`를 받아 `(labels, centroids, objective)`를 반환해야 한다. `_r2_score()`는 centered-variance 해석으로 바뀌어야 하며, 함수명은 그대로 두어도 된다.

English: The implementation keeps `polars` as the primary I/O library and continues using the already-present `numpy`, `pandas`, `scipy`, and `sklearn.cluster.KMeans`. If a new plain-kmeans helper is introduced, it must not accept trial keys. At minimum it should take `vectors`, `k`, `repeats`, and `seed`, then return `(labels, centroids, objective)`. `_r2_score()` must be changed to the centered-variance interpretation, while the function name may stay the same.

한국어: CLI는 간결해야 한다. duplicate-free prototype을 위해 만들어진 `--prototype`, `--skip-prototype`, `--prototype-*`, `--paper-full` 같은 dual-mode 플래그는 제거하거나 plain-paper default에 맞게 단순화하는 것이 원칙이다. 구현 후 사용자는 기본 실행만으로 PDF-aligned method를 쓰게 되어야 한다.

English: The CLI should stay simple. Dual-mode flags that only exist for the current duplicate-free prototype path, such as `--prototype`, `--skip-prototype`, `--prototype-*`, or `--paper-full`, should be removed or simplified in favor of a plain-paper default. After implementation, the user should get the PDF-aligned method from the default run.

## Change Note / 변경 메모

한국어: 이 revision ExecPlan은 기존 `compare_Cheung` 구현이 “paper-style adaptation + duplicate-free repair” 상태에서 멈춘 뒤, 사용자 요청에 따라 “duplicate-free를 제거하고, k-means와 NMF를 PDF 설명에 더 가깝게 재정렬”하기 위해 추가되었다. clustering lower bound, plain k-means repeat counts, gap-statistic reference counts, centered `R²`, README/report 문구 정합성이 이번 수정의 핵심이다.

English: This revision ExecPlan is added because the earlier `compare_Cheung` implementation stopped at a “paper-style adaptation plus duplicate-free repair” state, and the user now wants the method re-aligned with the PDF by removing duplicate-free logic and bringing k-means and NMF closer to the paper. The key revision targets are the clustering lower bound, plain-kmeans repeat counts, gap-statistic reference counts, centered `R²`, and README/report wording consistency.
