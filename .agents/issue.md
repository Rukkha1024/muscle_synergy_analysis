# Issues (replace_V3D)

Policy:
- This file records **the problem itself** only (symptom / impact / repro file or log).
- Record **solutions/workarounds** in the global skill: `$replace-v3d-troubleshooting`.

---
## 2026-02-25

- [PIPELINE] `main.py`는 `scripts/apply_post_filter_from_meta.py`를 생략하더라도 기본값이 `--meta_prefilter` 활성화라, 사용자가 기대한 "필터링 없이 raw output"이 아니라 trial subset이 미리 필터링된 CSV가 생성될 수 있음(요구사항 혼동 위험).
- [SCHEMA] `--no-meta_prefilter`로 raw batch export를 수행하면 `step_TF/state/mixed/age_group` 등의 group label 컬럼이 CSV에 포함되지 않아, step vs nonstep 분석이 CSV 단독으로는 바로 실행되지 않음(키 기반 label 결합이 필요).
- [ANALYSIS] raw 표본에서 `xCOM_BOS_norm` step/nonstep 차이를 해석할 때, 분해 검정 결과 `BOS_rangeX_300ms`도 유의하여(분모 변화) ratio 차이를 분자 변화만으로 단정할 수 없는 해석 혼입 위험이 확인됨.
- [ANALYSIS] raw(무필터) 분석에서 foot length 정규화(DV1_norm)를 수행하려면 `meta` 시트의 `발길이_왼/오른`이 필요하나, 일부 subject에서 해당 행 값이 비어 있어 `DV1_norm`은 subset 분석으로만 가능함(절대 cm는 가능).
- [DOC/ANALYSIS] 보고서에서 `xCOM_BOS_norm`(BOS-range 정규화)과 foot-length 정규화(DV1/DV2)가 함께 등장할 때 정규화 기준이 명시되지 않으면, 독자가 "foot length 정규화인지 단순 cm인지"를 혼동해 결과 해석이 어긋날 위험이 있음.

## 2026-02-24

- [ANALYSIS] `analysis/xCOM&BOS_normalization`에서 통계모델이 `DV ~ step_TF * velocity_c + (1|subject)`로 고정되어 있어, 사용자 요구사항인 "변수별 step/nonstep 유의성만 확인"과 직접적으로 일치하지 않고 결과 해석이 상호작용 중심으로 분산되는 문제가 있었음.
- [DOC] `.agents/skills/analysis-report/SKILL.md`와 `.agents/skills/analysis-reviewer/SKILL.md`가 figure/visualization 생성 및 PNG 커밋 절차를 기본 강제해, "visualization 불필요" 요구와 충돌하는 문서 정책 문제가 있었음.
- [ANALYSIS] `analysis/xCOM&BOS_normalization` 신규 분석에서 anthropometric 입력을 `transpose_meta`에서 직접 읽으면 일부 분석 대상(subject 누락, 0값)에서 `foot length/height` 분모가 비정상(`0` 또는 결측)으로 되어 xCOM/BOS 정규화식이 붕괴되는 문제가 있었음.
- [ANALYSIS] `analysis/xCOM&BOS_normalization`의 `step_onset` 이벤트 구성 시, step trial 1건(`조민석-30-1`)은 원본 이벤트 시트의 `step_onset`이 비어 있어 trial-level `step_onset_eval`이 결측으로 남고 표본 수가 `125 -> 124`로 축소되는 문제가 발생함.

## 2026-02-23

- [ANALYSIS] `analysis/initial_posture_strategy_lmm/analyze_initial_posture_strategy_lmm.py`에서 force 절대 onset 재계산 경로 적용 시, forceplate inertial subtraction QC가 4 trial에서 실패 경고(`non-strict`)를 출력해 force 변수 해석 시 trial-level 품질 확인이 필요해졌음.
- [DOC] `analysis/initial_posture_strategy_lmm/report.md`에서 유의 변수만 표시할 때, 분석 대상 전체 변수 목록(검정 가능/불가능 포함)이 누락되면 결과 해석의 기준집합이 불명확해지는 문제가 있었음.
- [ANALYSIS] `analysis/initial_posture_strategy_lmm`에서 `platform_onset` 단일시점 비교를 수행할 때, 배치 CSV의 onset-zero export 특성 때문에 각도/GRF/토크/COP_onset0 계열이 구조적으로 0 상수가 되어 LMM에서 \"비유의\"가 아니라 \"검정불가\"로 분리 처리해야 하는 문제가 발생함.
- [DOC] `analysis/step_vs_nonstep_lmm/report.md`에서 Van Wouwe 관련 설명이 여러 섹션으로 분산되면, 방법/결과/비교 대응을 한 화면에서 추적하기 어려워 해석 전달력이 떨어지는 문제가 있음.
- [ANALYSIS] `analysis/step_vs_nonstep_lmm`에서 Van Wouwe 2021의 `xCOM/BOS_300ms ↔ htrunk,max` subject-specific regression을 현재 파이프라인의 step/nonstep pooled LMM으로 직접 치환할 수 없어, 변수명이 유사해도 통계적 해석 단위(개인별 기울기 vs 집단 평균 차이)가 불일치하는 문제가 있음.
- [ANALYSIS] `analysis/step_vs_nonstep_lmm`의 nonstep `end_frame` 보정에서 `(subject, velocity)` step 정보가 없을 때 전체 step global 평균을 사용하면, 타 subject/타 velocity 정보가 유입되어 trial window 기준이 교차 오염될 수 있었음.
- [ANALYSIS] `analysis/step_vs_nonstep_lmm/analyze_step_vs_nonstep_lmm.py`의 관절각 DV 정의가 `Hip_R/Knee_R/Ankle_R` 고정이라, `step_R/step_L`가 혼재한 데이터에서도 기능적 stance limb 비교가 아닌 우측 고정 비교로 집계되어 side 해석이 왜곡될 수 있었음.
- [FORCEPLATE] `scripts/run_batch_all_timeseries_csv.py`의 forceplate 관성 제거 단계에서 C3D Stage01 변환 신호와 `shared_files` 템플릿 부호 기준이 어긋나 onset 이후 `GRF/GRM/COP` 대오차(상수 오프셋 포함)가 발생했음.
- [VERIFY] 위 부호 정렬 수정 후에도 `scripts/verify_forceplate_stage01_parity.py --round_decimals 9 --abs_tol 1e-9` 기준에서는 미세 수치 차(`~1e-6` 수준, COP 일부 `~1e-3`)로 `mismatch_total`/`md5_equal` 엄격 조건을 만족하지 못함.
- [PIPELINE] `main.py --overwrite` full batch 실행이 `data/all_data/251128_방주원_perturb_200_005.c3d`의 `T10` 마커 누락으로 중단되어, 변경 검증(출력 재생성/MD5 비교)이 기본 설정만으로는 완료되지 않음.
- [FORCEPLATE] `shared_files` Stage01 대비 `replace_V3D` 배치 출력에서 COP 축 부호 해석이 반대로 나타나(`COP_X/COP_Y` sign inversion) 좌표 해석 및 보고서 방향성(`+X anterior`, `+Y left`)과 수치 결과 간 불일치가 발생함.
- [VIZ] `scripts/plot_grid_timeseries.py`의 기본 `--y_zero_onset=True` 적용 시 `MOS_*`/`BOS_*`까지 onset-zeroing 되어, MoS 부호 해석(경계 내/외)과 BoS 절대면적 해석이 시각화에서 왜곡됨.
- [SCHEMA] 배치 payload에 legacy alias(`MOS_*_dir`) 경로가 남아 있으면 canonical-only 결과 컬럼 정책과 충돌해, 동일 지표의 과거 명칭이 코드 경로에 잔존하게 됨.
- [ANALYSIS] `analysis/step_vs_nonstep_lmm/analyze_step_vs_nonstep_lmm.py`가 `Rscript.exe` Windows 절대경로 고정에 의존해 WSL에서 직접 실행 시 LMM 단계가 실패(`FileNotFoundError`)하고, 최신 `output/all_trials_timeseries.csv` 기준 재분석 결과를 재현할 수 없었음.
- [ANALYSIS] `analysis/step_vs_nonstep_lmm/report.md`의 정량 결과가 현재 입력(`output/all_trials_timeseries.csv`)과 불일치한 상태(예: 184 trial, 13/32 유의)로 남아 있어, 실행 산출(figures/stdout)과 문서 해석 간 정합성이 깨져 있었음.
- [ANALYSIS] `analysis/step_vs_nonstep_lmm`의 nonstep-only `(subject, velocity)` 그룹에서는 `step_onset_local` 평균을 만들 수 없어 `end_frame`가 결측이 되었고, 그 결과 5 nonstep trials(3 subjects)가 분석 표본에서 제외되어 subject 수(24→21)가 축소되는 문제가 있었음.
- [VIZ] `scripts/plot_grid_timeseries.py`의 기본 piecewise x축이 `onset 전 / onset~offset / offset 이후` 3구간 워핑을 연속 적용해, total_mean 기준에서는 신호 모양이 과도하게 압축/신장되어 시각적 왜곡(비교성 저하)이 발생했음.

## 2026-02-22

- [ANALYSIS] `analysis/analysis.ipynb` 코드가 경로 탐색/전처리/집계/출력이 단일 셀에 직렬로 결합돼 있어, 재사용·검증·수정 시 변경 영향 범위를 빠르게 파악하기 어려웠음.
- [ANALYSIS] `analysis/analysis.ipynb`가 빈 코드셀 상태여서 `output/all_trials_timeseries.csv` 기반 step/nonstep 집계(비율/개수, 피험자 평균 trial 수)를 노트북에서 즉시 재현할 수 없었음.
- [ANALYSIS] `analysis/analysis.ipynb`에서 상대경로 `output/all_trials_timeseries.csv`를 고정 사용해, 노트북 작업 디렉터리가 `analysis/`일 때 `FileNotFoundError`가 발생함.
- [PIPELINE] 신규 후처리 필터 스크립트(`scripts/apply_post_filter_from_meta.py`) 실행 시 `polars.read_excel`이 `Could not determine dtype for column 10, falling back to string` 경고를 출력함(실행은 성공하나 로그 노이즈 발생).
- [PIPELINE] `main.py` 기본 실행(`--overwrite` 미지정)에서 기존 `output/all_trials_timeseries.csv`가 있으면 배치 단계에서 즉시 중단되어, 기대한 메타 필터 경로까지 도달하지 못하고 이전 축소 결과(예: 일부 subject만 남은 파일)가 그대로 유지될 수 있음.
- [CLI] `main.py`를 배치 전용으로 단순화한 뒤에도 argparse 기본 축약 해석 때문에 제거된 단일 실행 플래그 입력이 `--c3d_dir`로 오인식될 수 있어, 의도한 \"미지원 플래그 즉시 오류\" 정책과 불일치하는 동작이 발생할 수 있음.

## 2026-02-19

- [ANALYSIS] `analysis/step_vs_nonstep_lmm/analyze_step_vs_nonstep_lmm.py` fails on direct full run in WSL (`conda run --no-capture-output -n module python ...`) because `RSCRIPT` is pinned to a Windows absolute path (`C:\\Users\\Alice\\miniconda3\\envs\\module\\lib\\R/bin/x64/Rscript.exe`), so baseline/full-run verification cannot complete without environment-specific runtime override.
- [VIZ] `scripts/plot_bos_com_xy_sample.py` did not initialize a Hangul-capable matplotlib font at module load time, so GIF exports with Korean subject names could emit `Glyph ... missing from current font` warnings and render unreadable tofu glyphs in title/metadata text.
- [ANALYSIS] In `analysis/why_stepping_before_threshold`, direct comparison between COP-based boundaries and COM/xCOM metrics is not valid due to coordinate-system incompatibility in the lab setup, making COP-driven boundary analyses non-interpretable for this dataset.
- [ANALYSIS] In `analysis/why_stepping_before_threshold`, switching from single-timepoint snapshots to window-mean aggregation (`platform_onset_local ~ step_onset_local`, nonstep end by subject mean step onset) materially changes model ranking and coefficient significance, so legacy snapshot conclusions cannot be reused for current methodology.
- [TOOLING] There was no standardized skill for end-to-end review/repair of existing `analysis/*` workflows (script reproducibility, quantitative consistency, and report alignment), causing repeated ad-hoc review patterns across analysis topics.
- [VIZ] In `scripts/plot_bos_com_xy_sample.py`, dual-mode BOS GIF outputs (`freeze` + `live`) and `__live` filename suffixes created redundant artifacts and mode-specific branching complexity, increasing maintenance overhead for live-only usage and complicating filename compatibility during batch regeneration.
- [DOC] `plot-bos-com-xy-gif` skill Quick Start examples still referenced PNG/freeze-era usage (`PNG+GIF`, `--no-save_png`) after `scripts/plot_bos_com_xy_sample.py` migrated to live-only GIF output, causing command/docs mismatch for first-time runs.

## 2026-02-18

- [JOINT] In `src/replace_v3d/joint_angles/v3d_joint_angles.py`, shank X-axis was previously derived from ankle medial/lateral pair (`LFoot_3-LANK`, `RANK-RFoot_3`) using the same directional information as foot X-axis, causing `Ankle_L_Z_deg`/`Ankle_R_Z_deg` to collapse near zero (micro-degree scale) in joint-angle outputs.
- [VIZ] In `scripts/plot_bos_com_xy_sample.py`, runs against CSV files without `xCOM_X`/`xCOM_Y` cannot render xCOM overlays; without explicit fallback handling this can break expected single-pass GIF generation for mixed historical outputs.
- [VERIFY] Running a repo script copied to `/tmp` can fail with `ModuleNotFoundError: No module named '_bootstrap'`, which blocks baseline/reference GIF generation outside the repository script path.
- [VIZ] For freeze/live BOS comparison in GIF, if axis limits are not fixed from COM + BOS (bbox/hull/union) full-range, one mode can appear clipped or visually rescaled, reducing interpretability across modes.
- [VIZ] GIF export can emit matplotlib warnings for Korean glyphs (`Glyph xxxx missing from font(s) DejaVu Sans`), and Hangul text (e.g., subject names) may render as tofu/missing characters in titles or side-panel metadata.
- [IO] In `scripts/plot_bos_com_xy_sample.py`, when output folders are created with the raw `subject` value, a subject string containing OS-reserved path characters can fail directory creation/saving.

## 2026-02-17

- [ENV] In non-interactive WSL2 shells, `conda` may not be on PATH, causing `conda run -n module ...` to fail (symptom: `conda: command not found`).
- [ENV] When running `main.py --overwrite --skip_unmatched` or `scripts/run_batch_all_timeseries_csv.py`, the OpenMP runtime may abort with `OMP: Error #179: Function Can't open SHM2 failed` (interrupts batch CSV regeneration).
- [ENV] When running `scripts/plot_grid_timeseries.py`, `/home/alice/.config/matplotlib` and fontconfig cache paths are not writable, causing temporary cache warnings on every execution.
- [VIZ] In `scripts/plot_grid_timeseries.py`, the overwrite policy for regenerating files with the same filename is not explicitly documented in code or logs, making it difficult to determine from execution logs alone whether figures were actually overwritten after regeneration.

## 2026-02-16

- [DATA] `data/all_data/251128_방주원_perturb_200_005.c3d`: marker `T10` missing → joint-angle computations may fail in batch pipelines that expect the full marker set.
- [QC] Some trimmed C3D files are exactly 1 frame shorter than the expected interval `[platform_onset-100, platform_offset+100]` (`delta_frames=-1`). (No violations beyond ±1 frame were observed.)
- [VIZ] `scripts/plot_grid_timeseries.py`: The `linewidth/alpha` of the same overlay plot differs between `--sample` and `all` rendering modes, causing `all` results to appear excessively faint (poor readability). Line representation categories effectively branch on factors beyond color/style. (Repro example: `output/figures/grid_timeseries/by_subject/강비은/y0/grf_cop__subject-강비은__velocity-30__all.png`)

## 2026-02-15

- [ENV] In some execution environments, destructive git commands may be blocked by runtime policy (e.g., `git reset --hard`, `git branch -D`).
- [DATA] If a C3D filename token is not mapped by `resolve_subject_from_token()`, the batch/driver may fail (e.g., token `KUO` → alias not registered in `data/perturb_inform.xlsm`).
