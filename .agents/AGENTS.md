나를 코딩 아키텍처 구조, 통계에 대해 바보라고 생각하고 대해라. 
----
# Work Procedure
Always follow this procedure when performing tasks:
1. **Plan the changes**: Before making any code modifications, create a detailed plan outlining what will be changed and why
2. **Get user confirmation**: Present the plan to the user and wait for explicit confirmation before proceeding
3. **Modify code**: Make the necessary code changes according to the confirmed plan
4. **Git Commit**: Commit changes with a Korean commit message that reflects the user's intent, at least **5 lines** long.
5. **Run and Verify**: Execute the code and perform MD5 checksum comparison between new outputs and reference files if pipelines or logic were changed.
6. **Finalize**:
   - Clearly specify which skills were used in the final response.
   - Remove unnecessary files and folders.

----
# ExecPlans
When writing complex features or significant refactors, use an ExecPlan (as described in .agent/PLANS.md) from design to implementation.

## Phase 1: Requirements Discovery
Use `.agents/REQUIREMENTS_TEMPLATE.md` to guide a discovery session with the user. Ask questions in batches of 3-5. If answers are vague, push back. Do NOT proceed until the user confirms the completed brief.

## Phase 2: Plan Authoring
Write an ExecPlan(`.agents\execplans`, korean & english ver.) per `.agents/PLANS.md`. Present it to the user. Do NOT implement until the user approves.

## Phase 3: Implementation
Follow the approved ExecPlan. Proceed through milestones autonomously without prompting the user. Keep all living document sections up to date. Commit frequently. If blocked, stop and ask.

----
# **Codebase Rule: Configuration Management**

- Do not restore or roll back files/code that you did not modify yourself. Never attempt to "fix" or revert changes in files unrelated to your current task, including using `git checkout`.
- Use `polars` then `pandas` library.
- Leverage Parallel Agent Execution: you can use multiple agents to handle different parts of the task concurrently. Proactively launch multiple independent tasks (search, read, validation) simultaneously to reduce turnaround time.
- Organize and separate each scripts by biomechanical variable categories: EMG, COM, torque, joint, GRF&COP
- Use "document-writer" skill when modifing or creating mardown file. 

----
# Architecture Rule

Follow $codebase-architecture-doc

| Principle | Description |
|-----------|-------------|
| **Domain Isolation** | `src/` is divided into domain-specific folders. When requesting a feature from AI, only the relevant domain folder is provided as context, preventing hallucination and code interference. |
| **Pipeline ↔ Analysis Separation** | `scripts/` (data pipeline) and `analysis/` (statistical analysis) operate in completely separate contexts. Analysis code depends solely on the pipeline's final output file. |
| **Centralized Configuration** | All parameters are managed in YAML files under `configs/`, eliminating hard-coded values. |
| **Explicit Execution Order** | Script filenames carry numeric prefixes to make pipeline flow immediately apparent. |

----

# Pipeline Rules: Perturbation Task (Condensed)

## 1) Keys (do not mix)
- Base unit (cache/filename/group): `subject-velocity-trial`
- EMG event/feature unit: `subject-velocity-trial-emg_channel`

## 2) Onset timing workflow (EMG)
<Current Sequence>
1. Calculate onset timing using TKEO or TH.
2. Override with user's manual values.
</Current Sequence>

- Applicable targets (all trial×channel): `non-TKEO(TH)`, `TKEO-TH`, `TKEO-AGLR`
- Manual values are based on **absolute/original_DeviceFrame (1000 Hz)** and take precedence over algorithm results.

## 3) Time axis & domains
- `original_DeviceFrame`: Absolute provenance (1000 Hz). Never overwrite.
- `DeviceFrame`: `original_DeviceFrame - platform_onset` (based on platform_onset=0).
- Mocap ↔ Device (100 Hz ↔ 1000 Hz) conversion/ratio must be managed via `config.yaml` only (No hardcoding).
- Event domains (absolute vs device) are specified in `config.yaml > windowing.event_domains` (Defaults to absolute if undefined).

## 4) Windowing/event join rules (Prevention of recurrence)
- Event columns referenced in windowing must be **generated + joined before the calculation (e.g., iEMG/RMS)**.
- EMG windowing (iEMG/RMS) **uses per-channel event (trial×channel) as is**.
  - Trial-level reduction (`windowing.channel_event_reduce`) applies **only to trial-level calculations** like CoP/CoM.

## 5) Minimum validation (per run)
- `subject`, `velocity`, `trial_num` non-null
- time index monotonic per `subject-velocity-trial`
- window event values exist and are within the corresponding trial range
