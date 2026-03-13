# 이슈 004: `compare_Cheung,2021`를 PDF 기준 plain k-means와 NMF에 맞춰 재정렬하기

**상태**: 완료
**생성일**: 2026-03-13

## 배경

`analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`는 현재 논문 기반 로직과 프로젝트 적응 로직이 섞여 있습니다. 가장 큰 차이는 clustering입니다. 지금 스크립트는 trial 내부 duplicate-free 재배정 경로를 강제하고, prototype gate를 두며, 논문 수준의 무거운 gap-statistic 반복 수는 별도 플래그를 통해서만 사용합니다. NMF 선택 규칙은 논문과 비슷하지만, 현재 `R²` 정의와 기본 반복 수는 사용자가 원하는 수준으로 아직 충분히 논문 정렬 상태가 아닙니다.

사용자는 이 분석이 저장소의 16채널 perturbation EMG 입력과 baseline trial/window truth는 유지하되, NMF와 k-means 단계는 PDF에 더 가깝게 수정되기를 원합니다. 따라서 `K = 2..20`의 plain k-means, 논문식 gap-statistic 반복 수, rank 선택용 centered-variance `R²` 해석이 필요합니다. README와 생성 report 문구도 함께 수정해서 코드와 문서 설명이 어긋나지 않게 해야 합니다.

## 완료 기준

- [x] `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`에 duplicate-free 재배정 clustering 경로와 호출이 남아 있지 않다.
- [x] clustering search는 각 group에서 `K = 2..20`의 plain k-means를 평가하고, lower bound는 샘플 수학 한계 외에는 올라가지 않는다.
- [x] observed data와 reference-data gap-statistic search의 기본 반복 수가 논문 기준으로 맞춰진다.
- [x] NMF는 16채널을 유지하면서 논문식 rank search, restart rule, `R² >= 0.80` 최소 rank 규칙, centered-variance `R²` 정의를 사용한다.
- [x] `analysis/compare_Cheung,2021/README.md`와 생성되는 `analysis/compare_Cheung,2021/report.md`가 duplicate-free나 `--paper-full` 같은 예전 설명 없이 새 방법을 일관되게 설명한다.
- [x] 수정된 분석이 dry-run과 full-run 모두 끝까지 실행되고, full-run 재실행 시 출력 checksum이 재현 가능하다.
- [x] explorer와 reviewer pass가 unresolved concrete finding 없이 끝난다.

## 작업 목록

- [x] 1. revision ExecPlan을 만들고, 승인된 PDF 정렬 수정 범위를 고정한다.
- [x] 2. duplicate-free clustering, prototype gate, paper-full runtime 분기를 plain k-means와 논문 기본 gap-statistic 반복 수로 교체한다.
- [x] 3. 16채널 적응은 유지하면서 NMF `R²` 계산을 승인된 centered-variance 해석으로 수정한다.
- [x] 4. README와 report의 방법 설명을 새 구현과 맞게 다시 쓰거나 재생성한다.
- [x] 5. dry-run/full-run 검증과 MD5 기록을 남기고, 수정 전 결과와 달라지는 점이 의도된 method revision임을 문서화한다.
- [x] 6. explorer/reviewer 점검을 마친 뒤 한국어 5줄 이상 커밋 메시지로 커밋한다.

## 참고 사항

- 새 PDF 정렬 수정은 이전 완료 ExecPlan과 분리해서 추적하기 위해 `analysis/compare_Cheung,2021/exceplan_compare_cheung_pdf_alignment_revision.md`를 추가했다.
- 분석 스크립트 기본값은 이제 논문 기준 clustering 반복 수(`kmeans_restarts=1000`, `gap_ref_n=500`, `gap_ref_restarts=100`)를 사용하고, 로컬 검증을 위해서만 CLI override를 허용한다.
- 검증은 아래 명령으로 완료했다.
  `python3 -m py_compile analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`
  `conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py --dry-run`
  `conda run --no-capture-output -n module python analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py --kmeans-restarts 10 --gap-ref-n 5 --gap-ref-restarts 3`
- 축소 반복 수 검증 run은 두 번 모두 같은 clustering summary를 냈다: `step optimal_k=11`, `nonstep optimal_k=6`, step-to-nonstep centroid match `=6`.
- `analysis/compare_Cheung,2021/checksums_validation_final_run1.md5`와 `analysis/compare_Cheung,2021/checksums_validation_final_run2.md5`는 동일하며, 현재 체크인된 산출물에 대해 `md5sum -c analysis/compare_Cheung,2021/checksums.md5`도 통과했다.
- explorer pass에서 active `main()` 경로에 예전 prototype 또는 `--paper-full` 분기가 남아 있지 않음이 다시 확인되었고, 최종 reviewer pass도 scoped diff에 대해 concrete finding이 없다고 보고했다.
- `analysis/compare_Cheung,2021/checksums_before_pdf_alignment.md5`에 수정 전 산출물을 보존했고, 현재 `analysis/compare_Cheung,2021/checksums.md5`는 NMF `R²`, clustering path, figure, report가 모두 바뀌었기 때문에 예상대로 달라졌다.
