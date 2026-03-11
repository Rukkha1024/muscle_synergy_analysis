# CUDA/WSL2 Environment Snapshot

This file is a hardware and GPU stack snapshot only.
The repository's official execution environment is `cuda`, so normal pipeline commands should use `conda run -n cuda python ...`.
Use this document when you need the local CUDA machine details for GPU parity work against the reference repository.

- Snapshot date: 2026-03-05T16:31:25+09:00
- Purpose: Preserve exact CUDA-related versions on this WSL2 machine to avoid future incompatibilities during GPU parity work.

## Summary

- OS/WSL: Ubuntu 24.04.3 LTS on WSL2 (kernel 6.6.87.2-microsoft-standard-WSL2)
- GPU/Driver: NVIDIA GeForce RTX 5070, Driver 576.88, NVIDIA-SMI 575.64.01
- Driver CUDA: 12.9 (per nvidia-smi)
- CUDA Toolkit (nvcc): 12.8.93 (Conda env), path: `/home/alice/miniconda3/envs/cuda/bin/nvcc`
- System CUDA libs: No `/usr/local/cuda*` detected; CUDA toolkit/runtime is provided by conda env `cuda` (nvcc/cudart/nvrtc). `ldconfig` only shows system cuDNN 9 libraries.
- cuDNN: System libraries present (major `9` under `/lib/x86_64-linux-gnu`); headers not installed; CuPy does not detect cuDNN; PyTorch uses bundled cuDNN (91002)
- NCCL: Conda `nccl 2.27.7.1`; CuPy shows Build 22706 / Runtime 22707
- Nsight: `nsys` / `ncu` not found in PATH
- Python: 3.11.13 (conda env `cuda`), GPU libs → torch 2.8.0+cu128 (CUDA 12.8, cuDNN 9.1.2), cupy 13.5.1, cudf 25.06.00, cuml 25.06.00, rmm 25.06.00, numba 0.61.2

## System

```text
PRETTY_NAME="Ubuntu 24.04.3 LTS"
Linux DESKTOP-2HCKVI9 6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun  5 18:30:46 UTC 2025 x86_64 GNU/Linux
```

## GPU / Driver

```text
NVIDIA-SMI 575.64.01  | Driver Version: 576.88 | CUDA Version: 12.9
GPU: NVIDIA GeForce RTX 5070, 12227 MiB
```

## CUDA Toolkit

```text
nvcc path: /home/alice/miniconda3/envs/cuda/bin/nvcc
Cuda compilation tools, release 12.8, V12.8.93
Found CUDA dirs: (none under /usr/local)
```

## CUDA/Core Libraries (from ldconfig)

```text
libcudnn_ops.so.9 → /lib/x86_64-linux-gnu/libcudnn_ops.so.9
libcudnn_heuristic.so.9 → /lib/x86_64-linux-gnu/libcudnn_heuristic.so.9
libcudnn_graph.so.9 → /lib/x86_64-linux-gnu/libcudnn_graph.so.9
libcudnn_engines_runtime_compiled.so.9 → /lib/x86_64-linux-gnu/libcudnn_engines_runtime_compiled.so.9
libcudnn_engines_precompiled.so.9 → /lib/x86_64-linux-gnu/libcudnn_engines_precompiled.so.9
libcudnn_cnn.so.9 → /lib/x86_64-linux-gnu/libcudnn_cnn.so.9
libcudnn_adv.so.9 → /lib/x86_64-linux-gnu/libcudnn_adv.so.9
libcudnn.so.9 → /lib/x86_64-linux-gnu/libcudnn.so.9

(note) No /usr/local/cuda* toolkit detected; conda-provided CUDA libs are not registered in ldconfig on this host.
```

## Nsight Tools

```text
nsys: command not found
ncu: command not found
```

## Python GPU Stack

```text
Python: 3.11.13 (conda env: cuda)

torch: 2.8.0+cu128
  - torch.cuda.is_available: True
  - torch.version.cuda: 12.8
  - torch.backends.cudnn.version: 91002
  - device[0]: NVIDIA GeForce RTX 5070, capability (12, 0)

cupy: 13.5.1
  - runtime version: 12090 (driver), 12080 (locally installed)
  - cuFFT: 11303; NVRTC: 12.8
  - cuDNN: None detected in Python environment
  - NCCL: Build 22706 / Runtime 22707

cudf: 25.06.00
cuml: 25.06.00
rmm:  25.06.00
numba: 0.61.2 (numba-cuda 0.11.0), CUDA runtime: (12, 8)
```

### pip (GPU-related)

```text
cudf==25.6.0
cuml==25.6.0
cupy==13.5.1
numba==0.61.2
numba-cuda==0.11.0
rmm==25.6.0
torch==2.8.0
torchnmf==0.3.5
```

### Conda (GPU-related)

```text
Active env: cuda  (/home/alice/miniconda3/envs/cuda)
cuda-cudart 12.8.90, cuda-nvcc 12.8.93, cuda-nvrtc 12.8.93
cuda-python 12.9.1, cuda-version 12.8
nccl 2.27.7.1
cudf 25.06.00, cuml 25.06.00, rmm 25.06.00
cupy 13.5.1, numba 0.61.2, numba-cuda 0.11.0
```

## PATHs

```text
python:  /home/alice/miniconda3/envs/cuda/bin/python
pip:     /home/alice/miniconda3/envs/cuda/bin/pip
PATH has: /home/alice/miniconda3/envs/cuda/bin (precedence)
LD_LIBRARY_PATH: /home/alice/miniconda3/envs/cuda/lib:
```

## Notes / Tips

- This snapshot uses a Conda-provided CUDA 12.8 toolkit/runtime (no `/usr/local/cuda*` toolkit detected).
- Driver supports CUDA 12.9; local toolkit is 12.8. Keep this pairing when reproducing.
- cuDNN 9 system libs are present but not detected by CuPy; PyTorch links its own cuDNN (91002).
- For repeatability of this snapshot, keep the `cuda` conda env unchanged and avoid upgrading CUDA/driver/cuDNN unintentionally.
- For repository development and verification, continue using the `cuda` conda env unless a GPU-specific parity task explicitly requires this snapshot.

## Refresh Commands

Run these to re-snapshot later:

(Tip) Either `conda activate cuda` first, or prefix commands with `conda run -n cuda ...`.

```bash
conda run -n cuda python .claude/check_cuda_env.py
nvidia-smi
nvcc --version
ldconfig -p | egrep -i 'cudart|cublas|cufft|curand|cusolver|cusparse|nccl|nvrtc|cudnn'
python - <<'PY'
import torch, cupy, sys
print('torch', torch.__version__, 'cuda', torch.version.cuda, 'cudnn', torch.backends.cudnn.version())
print('cupy', cupy.__version__); cupy.show_config()
PY
conda list | egrep -i '^(cuda|cudnn|nccl|cuml|cudf|rmm|cupy|pytorch|torch|numba)'
python -m pip list --format=freeze | egrep -i '^(torch|torchvision|torchaudio|cupy|cuml|cudf|rmm|numba)'
```
