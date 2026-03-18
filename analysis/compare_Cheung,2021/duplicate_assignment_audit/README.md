# Duplicate Assignment Audit

이 폴더는 `analysis/compare_Cheung,2021`의 paper-like muscle synergy clustering 경로를 독립적으로 감사하기 위한 analysis 작업입니다. source of truth는 `analysis/compare_Cheung,2021/analyze_compare_cheung_synergy_analysis.py`이며, production pipeline의 forced reassignment 동작은 이번 작업 범위에 포함하지 않습니다.

현재 main pipeline의 source of truth는 pooled clustering 기반 baseline이다. 이 audit은 그 main pipeline을 바꾸지 않고, `compare_Cheung,2021` 분석 경로가 남기는 duplicate assignment burden만 별도로 점검한다.

## What This Analysis Answers

- 같은 trial 내부 서로 다른 synergy가 ordinary k-means 결과에서 같은 cluster label을 얼마나 자주 공유하는가
- gap statistic이 고른 `K`가 duplicate burden을 얼마나 허용하는가
- raw group-specific label과 downstream canonical label에서 duplicate burden이 어떻게 달라지는가
- duplicate pair가 실제로 서로 비슷한 synergy인지, 아니면 꽤 다른 synergy도 같은 cluster로 묶이는지

## Folder Layout

- `analyze_duplicate_assignment_audit.py`: compare_Cheung paper-like 경로를 재실행하고 report 및 결과물을 생성하는 메인 entrypoint
- `verify_duplicate_assignment_audit.py`: 생성된 report/result artifact의 내부 일관성을 검사하는 검증 스크립트
- `report.md`: 최신 감사 보고서
- `checksums.md5`: 최신 실행 기준으로 자동 갱신되는 MD5 manifest
- `results/`: CSV와 plot 산출물

## Run

repo root에서 실행합니다.

```bash
conda run --no-capture-output -n cuda python analysis/compare_Cheung,2021/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py --dry-run
conda run --no-capture-output -n cuda python analysis/compare_Cheung,2021/duplicate_assignment_audit/analyze_duplicate_assignment_audit.py
```

기본 runtime은 현재 체크인된 `analysis/compare_Cheung,2021/report.md`와 맞추기 위해 다음 override를 사용합니다.

- `--paper-kmeans-restarts 10`
- `--paper-gap-ref-n 5`
- `--paper-gap-ref-restarts 3`

compare_Cheung script의 코드 기본값은 `1000 / 500 / 100`이므로, paper-like report와 완전히 같은 runtime으로 재현하고 싶은 경우 override를 유지해야 합니다.

## Verify

```bash
conda run --no-capture-output -n cuda python analysis/compare_Cheung,2021/duplicate_assignment_audit/verify_duplicate_assignment_audit.py
```

이 검증은 아래를 확인합니다.

- 필수 report/result/plot 파일 존재 여부
- `checksums.md5`와 실제 산출물의 MD5 일치 여부
- `overall_metrics.csv`의 headline 수치와 `report.md` 본문 일치 여부
- 이번 compare_Cheung-only scope에서 `reassignment_stats.csv`가 생성되지 않았는지
- raw output에 duplicate가 실제로 남아 있는지
- compare_Cheung source script가 production uniqueness-enforcement helper를 직접 참조하지 않는지

reference 파일이 별도로 존재하지 않아 외부 reference와의 direct MD5 comparison은 하지 못했다. 대신 `analyze_duplicate_assignment_audit.py`가 실행될 때마다 현재 analysis 산출물의 checksum을 `checksums.md5`에 다시 기록하고, `verify_duplicate_assignment_audit.py`가 이 manifest가 stale하지 않은지 직접 확인한다.

## Outputs

생성 산출물은 `analysis/compare_Cheung,2021/duplicate_assignment_audit/results/` 아래에 저장됩니다.

- `overall_metrics.csv`
- `per_unit_metrics.csv`
- `duplicate_pairs.csv`
- `per_cluster_stats.csv`
- `k_sensitivity.csv`
- `plots/k_vs_gap_statistic.png`
- `plots/k_vs_duplicate_unit_rate.png`
- `plots/k_vs_excess_duplicate_ratio.png`
- `plots/group_duplicate_unit_rate.png`
- `plots/duplicate_vs_nonduplicate_similarity.png`

이번 scope에서는 compare_Cheung 경로 안에 forced reassignment가 없기 때문에 `reassignment_stats.csv`는 생성하지 않습니다.
