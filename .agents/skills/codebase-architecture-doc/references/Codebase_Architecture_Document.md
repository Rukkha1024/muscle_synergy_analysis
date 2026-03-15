# Codebase Architecture Document

> **Design Philosophy:** A domain-isolated research project structure optimized for AI Vibe Coding

---

## 1. Overview

### 1.1 Core Design Principles

| Principle | Description |
|-----------|-------------|
| **Domain Isolation** | `src/` is divided into domain-specific folders. When requesting a feature from AI, only the relevant domain folder is provided as context, preventing hallucination and code interference. |
| **Pipeline ↔ Analysis Separation** | `scripts/` (data pipeline) and `analysis/` (statistical analysis) operate in completely separate contexts. Analysis code depends solely on the pipeline's final output file. |
| **Centralized Configuration** | All parameters are managed in YAML files under `configs/`, eliminating hard-coded values. |
| **Explicit Execution Order** | Script filenames carry numeric prefixes to make pipeline flow immediately apparent. |
| **Main Orchestrator (`main.py`)** | The project root must include a `main.py` that orchestrates pipeline execution. The execution order is defined explicitly in `main.py` (a declared step list), rather than relying on ad-hoc shell chaining. |

---

## 2. Directory Structure

```
project_root/
├── main.py                    # Pipeline orchestrator (runs scripts in a defined order)
├── data/                       # Data storage
│   └── raw/                    # Original experiment data (read-only, never modify)
│
├── src/                        # Reusable core logic (fully isolated by domain)
│   └── {domain}/
│       ├── __init__.py
│       └── ...
│
├── configs/                    # Centralized configuration (separated by domain)
│   ├── {domain}_config.yaml
│   └── global_config.yaml
│
├── scripts/                    # EDA and data pipeline execution
│   ├── 01_{domain}.py
│   ├── 02_{domain}.py
│   └── 03_{domain}.py
│
├── analysis/                   # Hypothesis testing and statistical analysis
│   └── {topic}/
│
├── outputs/                    # Final artifacts from code execution
│   ├── figures/                # Visualization image files
│   ├── reports/                # Statistical result tables (.csv, .txt)
│   └── final.parquet           # Single refined file for statistical analysis
│
├── tests/                      # Unit tests mirroring src/ domain structure
│   └── test_{domain}/
│
├── archive/                    # Backup of deprecated code
└── pyproject.toml              # Project environment and dependency management
```

---

## 3. Directory Details

### 3.1 `data/` — Data Storage

```
data/
└── raw/          # Original experiment data
```

- **`raw/`**: Stores raw data collected from experiments. **Original files must never be modified under any circumstances.** Code in `src/` and `scripts/` reads from this directory for processing.

### 3.2 `src/` — Core Logic Modules (Domain Isolation)

```
src/
├── emg_pipeline/
│   ├── __init__.py
│   ├── filtering.py
│   └── onset_detection.py
├── synergy_stats/
│   ├── __init__.py
│   ├── nmf_extraction.py
│   └── similarity_metrics.py
└── ...
```

This is the module repository for reusable functions and classes used across the project. **Domain-level folder isolation** is the defining feature of this structure.

**How to leverage this in AI Vibe Coding:**

- When requesting a specific feature from AI, provide only the relevant domain folder (e.g., `src/emg_pipeline/`) as context.
- Since code from other domains never enters the context window, hallucination and cross-domain interference are eliminated.
- To add a new domain, simply create a new folder under `src/`.

### 3.3 `configs/` — Centralized Configuration

```
configs/
├── emg_config.yaml         # EMG processing parameters
├── synergy_config.yaml     # Synergy extraction parameters
└── global_config.yaml      # Global settings (paths, subject lists, etc.)
```

All parameters and environment settings are centrally managed as YAML files. **Domain-specific configs** and **global configs** are clearly separated, and hard-coding is prohibited.

**`global_config.yaml` example:**

```yaml
project:
  data_dir: "data/raw"
  output_dir: "outputs"
subjects:
  - S01
  - S02
  - S03
```

**`emg_config.yaml` example:**

```yaml
sampling_rate: 1000
bandpass:
  low: 20
  high: 450
rectification: "full_wave"
```

### 3.4 `scripts/` — Data Pipeline Execution

```
scripts/
├── 01_emg_processing.py
├── 02_synergy_extraction.py
└── 03_feature_aggregation.py
```

These are execution files that import modules from `src/` to run the actual data pipeline. Exploratory Data Analysis (EDA) is also performed in this directory.

**Naming convention:** `{order}_{domain}.py`

- **Numeric prefix** (01, 02, 03...) explicitly indicates execution order.
- **Domain name** immediately communicates what processing the script handles.

**Usage pattern:**

```python
# scripts/01_emg_processing.py
from src.emg_pipeline.filtering import bandpass_filter
from src.emg_pipeline.onset_detection import detect_onset
import yaml

with open("configs/emg_config.yaml") as f:
    config = yaml.safe_load(f)

# Pipeline execution logic ...
```

**Main orchestrator (`main.py`)**

- The project root must include a `main.py` that runs the pipeline end-to-end.
- The orchestrator defines the pipeline step order explicitly in `main.py` (a declared step list).
- Individual `scripts/NN_*.py` files may still be executed directly when appropriate, but `main.py` is the place where cross-step orchestration and ordering are documented.

### 3.5 `analysis/` — Hypothesis Testing and Statistical Analysis

```
analysis/
├── step_vs_nonstep/
│   ├── analyze_step_vs_nonstep.py
└── age_group_comparison/
    └── analyze_age_group_comparison.py
```

An **independent analysis space** that loads `outputs/final.parquet` (or the final refined file) to test research hypotheses.

**Key rules:**

- **No Jupyter Notebooks.** All code is written as pure Python or R scripts only.
- **References only the single final output file from the pipeline.** There are no dependencies on `src/` or `scripts/`.
- By **completely separating the contexts** of pipeline coding and statistical analysis coding, confusion during AI collaboration is prevented.

**Folder naming:** `{topic}`

- Timestamps and topic names enable tracking of the analysis history.

### 3.6 `outputs/` — Final Artifacts

```
outputs/
├── figures/           # Charts and graph image files
├── reports/           # Statistical result tables (.csv, .txt)
└── final.parquet      # Single refined file for statistical analysis
```

Stores all artifacts generated after `scripts/` and `analysis/` code execution.

- **`figures/`**: Visualization graphs and chart image files.
- **`reports/`**: Statistical result tables (.csv, .txt, etc.) produced by `analysis/`.
- **`final.parquet`**: The final output of the `scripts/` pipeline, serving as the single refined file fed directly into statistical analysis in `analysis/`. This acts as **the sole interface connecting the pipeline and analysis**.

### 3.7 Other Directories and Files

**`tests/`** — Unit Tests

```
tests/
├── test_emg_pipeline/
│   └── test_filtering.py
└── test_synergy_stats/
    └── test_nmf_extraction.py
```

Test code that verifies the correct operation of modules inside `src/`. Maintains **the same domain subfolder structure as `src/`** to keep the mapping clear.

**`archive/`** — Legacy Code Backup

Stores deprecated code and scripts that are no longer in use but kept for future reference.

**`pyproject.toml`** — Project Environment Management

The standard configuration file specifying Python package dependencies and virtual environment settings.

---

## 4. Data Flow

```
data/raw/  ──→  main.py (orchestrator; defined step order)
                    │
                    ▼
              scripts/ (uses src/ modules, references configs/ parameters)
                    │
                    ▼
              outputs/final.parquet
                    │
                    ▼
              analysis/ (independent analysis)
                    │
                    ▼
         outputs/figures/ + outputs/reports/
```

1. `main.py` orchestrates pipeline execution and triggers the `scripts/` steps in a defined order.
2. During processing, it utilizes domain-specific modules from `src/` and parameters from `configs/`.
3. The pipeline's final result is written to `outputs/final.parquet`.
4. `analysis/` reads only this single file to perform statistical analysis.
5. Analysis artifacts (graphs, tables) are saved to `outputs/figures/` and `outputs/reports/`.

---

## 5. AI Vibe Coding Guidelines

### 5.1 Context Provision Strategy

| Task Type | Context to Provide to AI |
|-----------|--------------------------|
| Modify EMG filtering functions | `src/emg_pipeline/` + `configs/emg_config.yaml` |
| Improve synergy extraction logic | `src/synergy_stats/` + `configs/synergy_config.yaml` |
| Write pipeline scripts | Target `scripts/` file + relevant `src/{domain}/` |
| Orchestrate the end-to-end pipeline | `main.py` + the target `scripts/` steps (+ relevant `src/{domain}/` + `configs/*.yaml`) |
| Write statistical analysis code | `analysis/{target folder}/` + `outputs/final.parquet` schema info |
| Write test code | `tests/test_{domain}/` + corresponding `src/{domain}/` |

### 5.2 Rules to Follow

1. Providing multiple domains to AI simultaneously risks code interference.
2. Analysis code must be completely independent from the pipeline.
3. **All parameters must be managed in `configs/`.** Magic numbers in code are prohibited.
4. `data/raw/` is read-only.
5. **When adding a new domain,** create `src/{new_domain}/`, `configs/{new_domain}_config.yaml`, and `tests/test_{new_domain}/` together.
