# 90퍼센트 VAF 컷오프를 확장 민감도 분석으로 방어하기

이 ExecPlan은 살아 있는 문서다. 작업이 진행되는 동안 `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective` 섹션을 계속 최신 상태로 유지해야 한다.

이 계획은 저장소 지침인 `.agents/PLANS.md`를 따르며, 해당 파일의 요구사항에 맞게 관리해야 한다.

## Purpose / Big Picture

이 작업이 끝나면, 독자는 하나의 분석 폴더만 다시 실행해서 EMG synergy 파이프라인이 왜 `VAF >= 0.90`을 쓰는지 지금보다 훨씬 강한 근거를 볼 수 있어야 한다. 현재 분석은 `0.95`가 비용이 크다는 점은 보여주지만, `0.85`부터 `0.89`보다 `0.90`이 왜 의미 있게 나은지는 아직 충분히 보여주지 못한다. 이 계획의 목표는 기존 `analysis/vaf_threshold_sensitivity` 워크플로를 확장해서 `0.85`부터 `0.95`까지 1퍼센트 단위로 비교하고, 각 단계에서 복잡도가 얼마나 늘어나는지, clustering이 언제부터 쪼개지기 시작하는지, 그리고 `0.90`이 더 낮거나 더 높은 cutoff보다 step 대 nonstep 구조를 더 해석 가능하게 보존하는지를 검증하는 것이다.

사용자가 눈으로 확인할 수 있는 결과는 더 풍부해진 JSON 산출물, 업데이트된 보고서, 그리고 checksum으로 검증된 artifact다. 초보자도 저장소 루트에서 스크립트를 실행하고 보고서를 열어 보면 “왜 90퍼센트인가?”에 대한 직접적인 답을 볼 수 있어야 한다.

## Progress

- [x] 2026-03-19T00:47:35+09:00 사용자 요구사항을 확정했다. 작업 위치는 `analysis/vaf_threshold_sensitivity`로 유지하고, `85`부터 `95`까지 1단위 sweep를 수행하며, 시간이 더 걸리더라도 `0.90`을 가장 정직하게 방어할 수 있는 근거를 찾기로 했다.
- [x] 2026-03-19T00:58:00+09:00 현재 분석 스크립트, 보고서, clustering 로직, NMF rank 선택 경로에 대한 baseline 검토를 마쳤다.
- [x] 2026-03-19T01:37:00+09:00 분석 스크립트를 확장해 `85`부터 `95`까지 sweep를 수행하고, 각 분석 단위의 모든 rank 후보를 캐시한 뒤 threshold별 bundle을 다시 선택하도록 바꾸었으며, 구조화된 artifact와 checksum 기록을 유지했다.
- [x] 2026-03-19T01:37:00+09:00 pooled member cosine, shared cluster coverage, tiny-cluster burden, `89/90/91/92` 인접 threshold transition을 포함하는 downstream-validity 비교를 추가했다.
- [x] 2026-03-19T01:50:00+09:00 기존 구조와 문체를 유지하면서 `analysis/vaf_threshold_sensitivity/report.md`와 `README.md`를 갱신했고, screening-profile broad sweep과 exact-profile rerun 경로를 구분해 문서화했다.
- [x] 2026-03-19T01:56:00+09:00 `--dry-run`, `py_compile`, checksum spot-check를 완료했고, screening-profile broad sweep artifact와 문서 표가 일치함을 확인했다.
- [ ] default clustering profile은 더 느리기 때문에 `0.89/0.90/0.91` exact-profile local rerun을 별도 out-dir에서 계속 실행 중이다.
- [ ] 최종 diff에 대해 필요한 review agent를 실행하고, 구체적 지적이 있으면 수정 후 재검증하고, 최소 5줄의 한국어 커밋 메시지로 커밋한다.

## Surprises & Discoveries

- Observation: 현재 분석은 `0.90`을 선택하는 근거보다 `0.95`를 배제하는 근거를 더 강하게 제공한다.
  Evidence: 저장된 보고서에서 pooled clustering은 `0.90`부터 uniqueness 기반 escalation이 필요해지고, `0.95`에서는 `trialwise`가 `k_gap_raw=17`에서 `k_selected=62`까지 상승한다.

- Observation: 현재 NMF 코드는 threshold를 처음 만족하는 rank에서 바로 멈추기 때문에, 기존 민감도 분석만으로는 인접 threshold 사이의 효율 tradeoff를 설명하기 어렵다.
  Evidence: `src/synergy_stats/nmf.py`는 rank를 순차적으로 올리다가 `vaf >= vaf_threshold`가 되는 즉시 반복을 종료한다.

- Observation: clustering 코드는 이미 더 강한 방어 논리에 필요한 raw signal을 계산하고 있다. 예를 들면 gap curve와 `K`별 duplicate-trial burden이 그렇다.
  Evidence: `src/synergy_stats/clustering.py`는 `gap_by_k`, `duplicate_trial_count_by_k`, `k_gap_raw`, `k_selected`, `k_min_unique`를 반환한다.

- Observation: `0.90`을 방어하는 가장 강한 문장은 “최소 burden”이 아니라 “두 mode 모두에서 ceiling-hit이 시작되기 직전의 마지막 threshold”였다.
  Evidence: screening-profile broad sweep에서 ceiling-hit rate는 `0.90`까지 `trialwise`와 `concatenated` 모두 `0.0000`이고, `0.91`부터 각각 `0.0080`, `0.0222`로 처음 발생한다.

- Observation: 첫 보고서 초안은 재현 커맨드보다 screening-profile 숫자를 더 앞서 갔기 때문에, reproducibility framing을 다시 맞춰야 했다.
  Evidence: review agent가 `report.md` 표가 reduced-restart broad sweep artifact와 일치하지만 재현 블록이 plain default command만 보여 준다고 지적했다.

## Decision Log

- Decision: 작업 위치를 새 분석 폴더가 아니라 `analysis/vaf_threshold_sensitivity` 내부로 유지한다.
  Rationale: 사용자가 이 범위를 명시적으로 승인했고, 기존 스크립트가 이미 main pipeline의 NMF와 clustering 경로를 그대로 재실행하고 있기 때문이다.
  Date/Author: 2026-03-19 / Codex

- Decision: cutoff는 `85`부터 `95`까지 모든 정수값을 sweep한다.
  Rationale: 사용자가 1단위 간격을 요청했고, 현재의 `80/85/90/95` 간격만으로는 `0.90`이 실제 elbow인지 단순한 임의 선택인지 판단하기 어렵기 때문이다.
  Date/Author: 2026-03-19 / Codex

- Decision: “90퍼센트가 이겨야 한다”는 요구는 탐색 목표로 해석하고, 근거를 과장해도 된다는 허가로 해석하지 않는다.
  Rationale: cherry-picking에 의존한 방어는 디펜스 상황에서 약하다. underfit, practical balance, over-fragmentation을 실제로 가를 수 있는 진단을 추가하는 편이 더 강한 전략이다.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

구현은 핵심 목표까지 도달했다. 스크립트는 각 분석 단위에서 가능한 모든 rank 후보를 한 번씩 계산하고, threshold마다 처음 조건을 만족하는 최소 bundle을 다시 선택하도록 바뀌었다. 이 덕분에 threshold rule 자체를 바꾸지 않고도 인접 cutoff 비교와 pooled-structure 진단을 추가할 수 있었다. 산출물에는 burden summary, adjacent-threshold transition summary, pooled-structure validity summary, richer `run_metadata`가 포함된다.

현재 broad sweep screening 결과는 기존 4-point 비교보다 `0.90` 방어에 훨씬 유용하다. 가장 방어하기 쉬운 문장은 `0.90`이 두 mode 모두에서 ceiling-hit artifact를 아직 피하는 가장 높은 tested cutoff라는 것이다. 다만 이것이 `0.90`이 가장 가벼운 cutoff라는 뜻은 아니며, `0.89`가 더 parsimonious하다는 사실은 그대로 유지된다. 따라서 방어 논리는 minimum complexity가 아니라 strictness와 artifact avoidance의 균형 위에 놓여 있다.

검증 상태는 “사용 가능하지만 완전한 종료는 아님”에 가깝다. `--dry-run`과 `py_compile`은 통과했고, screening-profile broad sweep artifact의 checksum spot-check도 일치했다. 다만 default clustering profile로 돌리는 느린 `0.89/0.90/0.91` exact-profile rerun은 이 업데이트 시점에도 계속 실행 중이므로, 현재 보고서는 완료된 default-profile replication이 아니라 screening-profile defense임을 명시한다.

## Context and Orientation

핵심 작업 위치는 `analysis/vaf_threshold_sensitivity`다. 기존 스크립트 `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py`는 main EMG pipeline을 재사용해서 trial을 선택하고, non-negative matrix factorization(NMF)을 수행하고, 추출된 synergy weight vector 전체를 step과 nonstep을 합친 pooled space에서 clustering한다. “VAF”는 “variance accounted for”의 약자로, 입력 EMG 에너지 중 재구성 신호가 설명하는 비율을 뜻한다. VAF threshold를 높이면 충분한 재구성율에 도달할 때까지 synergy component를 더 추가해야 한다. “Gap statistic”은 원시 cluster 수 `K`를 제안하는 clustering 기준이다. “Zero-duplicate feasibility”는 같은 trial에서 나온 여러 component가 여전히 같은 pooled cluster에 중복 배정되면 그 `K`를 거부하는 프로젝트 규칙이다. 이 저장소에서는 `src/synergy_stats/clustering.py`가 gap에서 선택된 `K` 이상 구간에서 첫 zero-duplicate 해를 찾는다.

NMF rank 선택 로직은 `src/synergy_stats/nmf.py`에 있다. rank `1`, 그다음 `2` 식으로 증가시키며 `configs/synergy_stats_config.yaml`의 `max_components_to_try`까지 시도한다. 기본 설정은 `vaf_threshold: 0.90`과 `max_components_to_try: 8`이다.

현재 보고서 `analysis/vaf_threshold_sensitivity/report.md`에는 threshold별 요약, subject별 표, 짧은 해석이 이미 들어 있다. 하지만 비교 대상이 `80`, `85`, `90`, `95` 네 점뿐이고, 실제 방어에 중요한 세 가지 질문은 아직 정량화하지 못했다. 바로 더 높은 threshold에서 ceiling에 얼마나 자주 닿는지, duplicate를 없애기 위해 clustering complexity가 얼마나 필요한지, 그리고 선택된 cutoff가 downstream step 대 nonstep 해석력을 실제로 개선하는지다.

## Plan of Work

먼저 분석 스크립트를 확장해서 threshold 처리가 네 개의 거친 기본값에 묶이지 않도록 만든다. 기본 threshold 목록을 `85`부터 `95`까지 전체 sweep로 바꾸고, 기존 summary 출력을 유지하면서 JSON에 더 풍부한 진단값을 저장한다. 이 진단에는 최소한 다음 내용이 들어가야 한다.

1. NMF complexity burden. 각 mode와 threshold마다 lower threshold 대비 component inflation, `max_components_to_try` 상한에 걸린 ceiling-hit 개수와 비율, 그리고 “평균 component 하나 증가당 추가 확보 VAF” 같은 reconstruction efficiency 지표를 계산한다.

2. Clustering burden. 현재의 선택 `K` 요약값은 유지하되, gap curve, `K`별 duplicate-trial count, `k_gap_raw`에서 `k_selected`까지 얼마나 상승했는지, 그리고 해당 threshold가 escalation 또는 extension 구간에 들어가는지를 함께 저장하고 요약한다.

3. `0.90` 주변의 근거. endpoint만 비교하지 않고 `89 -> 90`, `90 -> 91`처럼 인접 threshold를 직접 비교해서, 보고서가 `0.90`의 local neighborhood를 설명할 수 있게 한다.

다음으로 threshold별 pooled clustering 결과를 사용해 downstream-validity 비교를 추가한다. 낮은 cutoff에서 지나치게 합쳐지는지, 높은 cutoff에서 지나치게 분절되는지를 보여줄 수 있어야 한다. 저장소에는 이미 `analysis/pooled_shared_specific_synergy/analyze_pooled_shared_specific_synergy.py`라는 좋은 pooled cluster 진단 예시가 있다. 가능하면 같은 스타일의 근거를 재사용한다. 예를 들면 cluster occupancy의 step 대 nonstep 분포, subject coverage, 그리고 과도한 병합 또는 분절을 드러내는 similarity나 balance 요약이 그것이다. 이 downstream 분석은 별도 파이프라인이 될 필요는 없고, cutoff별로 `0.90`이 가장 실용적인 절충점인지 답할 정도의 증거만 만들면 된다.

마지막으로 markdown 보고서를 처음부터 다시 쓰지 않고 필요한 섹션만 삽입한다. 현재 문서 구조, 용어, 표 스타일을 유지한다. 새 섹션에서는 세 가지 주장을 분명히 구분한다. 낮은 threshold가 왜 underfit일 수 있는지, `0.90`이 왜 practical balance인지, 더 높은 threshold가 왜 over-fragmentation 또는 saturation으로 이어지는지다. 만약 새 근거가 `0.90`을 부분적으로만 지지한다면, 강한 부분과 약한 부분을 구분해서 정직하게 적는다.

## Concrete Steps

아래 명령은 모두 저장소 루트 `/home/alice/workspace/26-03-synergy-analysis`에서 실행한다.

1. 현재 입력 경로와 baseline 분석 로딩을 검증한다.

       conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --dry-run

   기대 결과: 스크립트가 selected trial 수, subject 목록, threshold 목록을 출력하고 `Dry run complete.`로 종료한다.

2. `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py`를 확장해서 다음을 수행하게 한다.
   - 기본 threshold 목록을 `0.85`부터 `0.95`까지로 변경
   - `feature_rows`와 `cluster_result`에서 더 풍부한 threshold별 진단값 수집
   - 정말 도움이 되는 경우 threshold diagnostic figure 생성
   - `summary.json`, threshold별 `summary.json`, `checksums.md5` 계약 유지

3. 필요하면 같은 분석 폴더 안에 downstream pooled-structure summary용 소형 helper를 추가한다. 변경은 additive하고 self-contained하게 유지한다.

4. `analysis/vaf_threshold_sensitivity/report.md`에 새 결과를 반영하되, 기존 heading hierarchy와 주변 문체를 유지한다.

5. 보고서가 인용하는 broad sweep screening profile을 실행한다.

       conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py \
         --cluster-repeats 100 \
         --gap-ref-n 100 \
         --gap-ref-restarts 20 \
         --uniqueness-candidate-restarts 100

   기대 결과: threshold별 블록이 순서대로 출력되고, 각 threshold마다 `trialwise`와 `concatenated` 요약이 보이며, screening-profile artifact가 `analysis/vaf_threshold_sensitivity/artifacts/default_run` 아래에 기록된다.

6. 필요하면 `0.90` 주변 exact-profile local confirmation을 별도 out-dir로 실행한다.

       conda run --no-capture-output -n cuda python analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py --thresholds 0.89 0.90 0.91 --out-dir analysis/vaf_threshold_sensitivity/artifacts/exact_89_91

   기대 결과: `89/90/91` 근방에 대한 작은 exact-profile artifact 세트가 별도 out-dir에 기록된다.
7. checksum을 기록하고 검증한다.

       md5sum analysis/vaf_threshold_sensitivity/artifacts/default_run/summary.json
       md5sum analysis/vaf_threshold_sensitivity/artifacts/default_run/by_threshold/vaf_90/summary.json
       sed -n '1,120p' analysis/vaf_threshold_sensitivity/artifacts/default_run/checksums.md5

8. diff를 점검하고 필요한 review agent를 실행한 뒤 커밋한다.

## Validation and Acceptance

다음 조건이 모두 충족되어야 이 분석을 수락할 수 있다.

스크립트는 여전히 `--dry-run`을 성공적으로 완료해야 하고, 저장소 루트에서 `cuda` conda 환경으로 문서화된 screening-profile rerun도 완료해야 한다. 재생성된 artifact에는 `85`부터 `95`까지의 전체 sweep가 포함되어야 한다. 보고서에는 endpoint 비교만이 아니라 `0.90` 주변 cutoff들에 대한 명시적 근거가 들어 있어야 한다. 최종 해석은 `0.90`이 reconstruction, clustering burden, interpretability의 균형으로 방어되는지 여부를 분명히 말해야 한다. 생성된 checksum은 새로 기록된 screening-profile artifact와 일치해야 한다. 만약 확장 진단이 `0.90`보다 더 강한 경쟁 cutoff를 드러낸다면, 그 사실을 숨기지 않고 보고해야 한다.

## Idempotence and Recovery

분석 스크립트는 여러 번 다시 실행해도 안전해야 한다. 같은 artifact 경로를 재생성하는 것은 정상이며, 오래된 결과를 현재 결과로 덮어쓰는 동작을 기대한다. full run이 중간에 실패하면 원인인 스크립트 문제를 수정한 뒤 같은 명령을 다시 실행하면 된다. 파괴적 migration 단계는 없다. worktree의 관련 없는 dirty file은 건드리지 않는다. 스크립트가 최종 artifact 계약에 없는 scratch file을 만들면 마무리 전에 삭제한다.

## Artifacts and Notes

중요한 최종 artifact는 broad screening profile 기준으로 `analysis/vaf_threshold_sensitivity/artifacts/default_run` 아래에 유지한다. `0.89/0.90/0.91` exact-profile local check는 `analysis/vaf_threshold_sensitivity/artifacts/exact_89_91` 같은 별도 out-dir에 둘 수 있다. figure를 추가한다면 `figures/` 같은 예측 가능한 하위 디렉터리에 두고, 의도한 deliverable에 포함되는 경우에만 checksum 파일에 넣는다.

최종 보고서는 초보자도 아래 세 질문에 답할 수 있게 만들어야 한다.

1. cutoff가 high eighties에서 `0.90`으로 올라갈 때 무엇이 좋아지는가?
2. cutoff가 `0.90`을 넘으면 무엇이 나빠지는가?
3. 왜 이 파이프라인에서는 `0.90`이 가장 방어 가능한 실용적 설정인가?

## Interfaces and Dependencies

이번 작업은 분석 폴더 안에서 NMF나 clustering을 새로 구현하지 않고, 저장소의 source-of-truth pipeline 코드를 계속 재사용해야 한다. 구체적으로는 다음 인터페이스를 사용한다.

- 입력 준비에는 `src.emg_pipeline.build_trial_records`, `load_emg_table`, `load_event_metadata`, `load_pipeline_config`, `merge_event_metadata`를 사용한다.
- trialwise NMF는 `src.synergy_stats.nmf`와 동일한 low-level rank fitting / VAF 계산 규칙을 쓰되, analysis script 안에서 모든 rank 후보를 캐시한 뒤 threshold별 최소 만족 bundle을 다시 선택한다.
- concatenated 분석 단위는 `src.synergy_stats.concatenated`와 같은 super-trial preparation 로직을 따르되, source trial averaged activation profile을 다시 나눠 threshold별 feature row를 구성한다.
- pooled clustering과 `K` 선택에는 `src.synergy_stats.clustering.cluster_feature_group`를 사용한다.
- 기본 rank/clustering bound는 `configs/synergy_stats_config.yaml`에서 읽는다.

새 helper function이 필요하면 우선 `analysis/vaf_threshold_sensitivity/analyze_vaf_threshold_sensitivity.py` 내부에 두고, 둘 이상의 기존 모듈이 진짜로 공유해야 할 때만 바깥으로 빼낸다.

Revision note: 2026-03-19에 `VAF >= 0.90` cutoff를 더 촘촘한 민감도 분석과 downstream structure 진단으로 방어하기 위해 생성했다.
