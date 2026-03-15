대상 repo:
https://github.com/Rukkha1024/muscle_synergy_analysis

작업 목표:
gap-statistic 전환 이후 남아 있는 legacy / dead code / naming / config 중복을 정리하는 cleanup만 수행하라.
이번 작업은 “기능 추가”가 아니라 “의미 정리와 유지보수성 개선”이 목적이다.
mixed-velocity 기반 same-intensity step vs non-step 비교라는 현재 논문/파이프라인의 과학적 의도는 절대 바꾸지 마라.
trial selection, windowing, NMF rank 선택, surrogate step_onset 규칙, mixed velocity 정의는 이번 범위 밖이다.

중요:
- 먼저 repo의 AGENTS.md를 읽고 그 절차를 따르라.
- complex refactor로 간주하고 ExecPlan을 먼저 작성하라.
- 사용자 승인 전에는 코드 수정하지 마라.
- conda env는 AGENTS 기준 `module`을 사용하라.
- 관련 없는 파일은 절대 건드리지 말고, `git checkout`으로 남의 변경을 되돌리지 마라.
- `src/`와 `analysis/`의 경계를 지켜라.
- `analysis/` 파일을 건드릴 때는 먼저 relevant skill을 최소 1개 사용하라. 기본은 `data-context`.
- markdown/README를 수정할 때는 `document-writer` skill을 사용하라.
- prose는 `writing-clearly-and-concisely` 기준으로 다듬어라.

이번 cleanup의 핵심 범위:
1) `src/synergy_stats/clustering.py`
2) `src/synergy_stats/gap.py`
3) `configs/synergy_stats_config.yaml`
4) `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`
5) `tests/test_synergy_stats/test_clustering_contract.py`
6) 필요 시 `tests/test_synergy_stats/test_end_to_end_contract.py`
7) `README.md`

구체적인 cleanup 요구사항:

A. legacy duplicate-repair 경로 정리
- `_enforce_unique_trial_labels`와 `_minimum_cost_unique_assignment`가 실제 production path에서 더 이상 필요 없는지 먼저 repo 전체에서 검색하라.
- 정말 호출되지 않고 의미도 죽은 코드면 삭제하라.
- 만약 일부 legacy analysis나 test에서만 아직 필요하면, production path와 분리된 deprecated compatibility helper로 명확히 격리하라.
- 어떤 경우든 main gap-statistic path에서는 post-hoc forced reassignment가 절대 호출되지 않음을 코드 구조로 명확히 보여라.
- dead code를 남겨야 한다면 왜 남겨야 하는지 plan과 final report에 분명히 써라.

B. duplicate policy의 single source of truth 만들기
- 현재 duplicate policy는 사실상 `require_zero_duplicate_solution: true` + `duplicate_resolution: "none"`가 본체다.
- `disallow_within_trial_duplicate_assignment`는 deprecated alias처럼 보이므로, repo 전체에서 실제 사용처를 먼저 조사하라.
- 남은 사용처가 없다면:
  - `configs/synergy_stats_config.yaml`에서 이 키를 제거하라.
  - `clustering.py`의 fallback parsing도 제거하라.
- 남은 사용처가 있다면:
  - 한 릴리즈 동안만 호환되는 deprecated 입력으로 축소하라.
  - README와 code comment에 deprecated임을 명시하라.
  - parsing은 한 곳에서만 처리하고, 의미가 갈라지지 않게 하라.

C. compare_Cheung wrapper naming 정리
- `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`는 shared helper를 import하면서도 local wrapper 이름을 `compute_gap_statistic`로 유지하고 있다.
- 이 이름은 shared helper와 혼동되므로, local wrapper 이름을 `compute_cheung_gap_statistic` 또는 동등하게 더 명확한 이름으로 바꿔라.
- call site도 같이 정리하라.
- 목적은 “paper-specific orchestration wrapper”와 “shared core implementation”을 이름만 보고도 구분 가능하게 만드는 것이다.
- 여기서는 동작을 바꾸지 말고 naming clarity만 개선하라.

D. README / doc cleanup
- README에서 duplicate policy, K 의미, metadata field 설명이 코드/설정과 정확히 일치하는지 확인하라.
- deprecated alias를 제거했다면 README에서도 완전히 제거하라.
- deprecated alias를 남겼다면 README에서 “backward-compatible deprecated input” 정도로만 최소한 언급하라.
- README 문장은 implementation detail이 아니라 현재 저장소의 실제 behavior를 설명해야 한다.
- 문서와 코드 의미가 어긋나는 표현을 전부 정리하라.

E. test cleanup 및 보강
- 현재 테스트가 repair-based behavior를 전제하지 않는지 다시 전수 확인하라.
- 다음 케이스를 최소한 보장하라:
  1. success_gap_unique
  2. success_gap_escalated_unique
  3. failed_invalid_k_range
  4. failed_no_zero_duplicate_at_or_above_gap_k
- schema test는 계속 유지하되, metadata key가 실제 export schema와 일치하는지 재확인하라.
- cleanup 후에도 테스트 이름과 docstring이 현재 정책을 정확히 반영하게 고쳐라.
- 테스트 추가는 “정책의 의미를 고정”하는 방향으로 하라. 단순 line coverage 목적의 테스트는 피하라.

F. repo-wide stale wording 탐색
- repo 전체에서 아래 키워드를 검색하고 stale wording을 정리하라:
  - `reassign`
  - `repair`
  - `duplicate_free`
  - `disallow_within_trial_duplicate_assignment`
  - `_enforce_unique_trial_labels`
  - `_minimum_cost_unique_assignment`
- 단, compare_professor 같은 비교용 분석은 의도적으로 legacy 개념을 설명할 수 있으니 무조건 지우지 말고, “현재 production path 설명인지, 과거 비교 분석 설명인지”를 구분해서 처리하라.

G. behavior guardrail
- cleanup은 기본적으로 output-preserving이어야 한다.
- 다만 deprecated alias 제거처럼 입력 contract가 바뀌는 경우는 “의도된 interface cleanup”으로 문서화하라.
- scientific behavior는 바꾸지 말고, 코드 구조/이름/설정/문서를 정리하는 수준에서 끝내라.

작업 절차:
1. 관련 파일과 호출 경로를 먼저 조사하라.
2. cleanup 범위를 dead code 제거 / deprecated alias 처리 / naming cleanup / doc cleanup / test cleanup으로 분리한 plan을 작성하라.
3. plan에서 “삭제할 것 / 남길 것 / 이유 / 리스크 / 검증 방법”을 분명히 써라.
4. 사용자 승인 후 구현하라.
5. 구현 후 변경 요약을 작성하라.
6. 테스트와 필요한 검증을 실행하라.
7. logic path가 바뀌었다고 판단되면 fixture pipeline과 MD5 비교까지 수행하라.
8. 마지막에 불필요한 파일과 임시 산출물을 정리하라.
9. 한국어 5줄 이상 commit message로 commit하라.

실행 검증:
- 최소 실행:
  - `conda run --no-capture-output -n module python -m pytest tests/test_synergy_stats/test_clustering_contract.py -q`
  - `conda run --no-capture-output -n module python -m pytest tests/test_synergy_stats/test_end_to_end_contract.py -q`
- cleanup 결과가 interface/logic에 영향을 준다면 추가로:
  - fixture run 1회
  - reference와 MD5 비교
- README를 수정했다면 문서 설명과 실제 config/code path가 맞는지 다시 cross-check하라.

최종 보고 형식:
- 무엇을 삭제했는지
- 무엇을 남겼는지
- 왜 남겼는지
- output-preserving인지 아닌지
- 어떤 테스트를 돌렸는지
- 남은 후속 cleanup이 있는지
- 사용한 skill 목록

이번 작업의 성공 기준:
- production path에서 legacy repair 개념이 코드/설정/문서에서 혼동 없이 정리됨
- duplicate policy의 source of truth가 하나로 정리됨
- compare_Cheung의 wrapper naming이 shared helper와 혼동되지 않음
- 테스트가 새 정책을 더 명시적으로 고정함
- 논문용 mixed-velocity same-intensity comparison 의도는 그대로 유지됨