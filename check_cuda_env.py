"""CUDA/GPU environment smoke check.

Prints versions for key programs and Python GPU libraries, then runs small
GPU computations (PyTorch, CuPy, cuML) to confirm CUDA is working end-to-end.
Exit code: 0 = PASS, 1 = FAIL.
"""

from __future__ import annotations

import importlib
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: str


def _run_cmd(cmd: list[str], *, timeout_s: int = 30) -> CheckResult:
    name = " ".join(cmd)
    prog = cmd[0]
    if shutil.which(prog) is None:
        return CheckResult(name=name, ok=False, details=f"not found: {prog}")

    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(name=name, ok=False, details=f"timeout after {timeout_s}s")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name=name, ok=False, details=f"{type(exc).__name__}: {exc}")

    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip()
    if completed.returncode != 0:
        details = output.splitlines()[-1] if output else f"returncode={completed.returncode}"
        return CheckResult(name=name, ok=False, details=details)

    return CheckResult(name=name, ok=True, details=output)


def _import_version(label: str, module_name: str) -> CheckResult:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name=label, ok=False, details=f"{type(exc).__name__}: {exc}")

    version = getattr(module, "__version__", None)
    if version is None and module_name == "yaml":
        # PyYAML may not expose __version__ in some environments.
        version = getattr(module, "__with_libyaml__", None)
    return CheckResult(name=label, ok=True, details=str(version))


def _torch_smoke_test() -> CheckResult:
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="torch smoke", ok=False, details=f"{type(exc).__name__}: {exc}")

    if not torch.cuda.is_available():
        return CheckResult(name="torch smoke", ok=False, details="torch.cuda.is_available() is False")

    try:
        device_name = torch.cuda.get_device_name(0)
        a = torch.rand((512, 512), device="cuda", dtype=torch.float32)
        b = torch.rand((512, 512), device="cuda", dtype=torch.float32)
        c = a @ b
        torch.cuda.synchronize()
        if tuple(c.shape) != (512, 512):
            return CheckResult(name="torch smoke", ok=False, details=f"unexpected shape: {tuple(c.shape)}")
        return CheckResult(name="torch smoke", ok=True, details=f"OK on {device_name}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="torch smoke", ok=False, details=f"{type(exc).__name__}: {exc}")


def _cupy_smoke_test() -> CheckResult:
    try:
        import cupy as cp
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="cupy smoke", ok=False, details=f"{type(exc).__name__}: {exc}")

    try:
        x = cp.arange(1_000_000, dtype=cp.float32)
        y = (x * x).sum()
        y_host = float(y.get())
        return CheckResult(name="cupy smoke", ok=True, details=f"OK (sum={y_host:.6e})")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="cupy smoke", ok=False, details=f"{type(exc).__name__}: {exc}")


def _cuml_smoke_test() -> CheckResult:
    try:
        import cupy as cp
        from cuml.cluster import KMeans
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="cuml smoke", ok=False, details=f"{type(exc).__name__}: {exc}")

    try:
        rng = cp.random.RandomState(0)
        x = rng.random_sample((2000, 8)).astype(cp.float32)
        model = KMeans(n_clusters=4, max_iter=100, n_init=1, random_state=0)
        labels = model.fit_predict(x)
        labels_arr = cp.asarray(labels)
        unique_count = int(cp.unique(labels_arr).size)
        if unique_count < 2:
            return CheckResult(name="cuml smoke", ok=False, details=f"degenerate labels (unique={unique_count})")
        return CheckResult(name="cuml smoke", ok=True, details=f"OK (unique labels={unique_count})")
    except TypeError:
        # Some cuML versions expose a smaller signature. Fall back to minimal init.
        try:
            rng = cp.random.RandomState(0)
            x = rng.random_sample((2000, 8)).astype(cp.float32)
            model = KMeans(n_clusters=4)
            labels = model.fit_predict(x)
            labels_arr = cp.asarray(labels)
            unique_count = int(cp.unique(labels_arr).size)
            if unique_count < 2:
                return CheckResult(name="cuml smoke", ok=False, details=f"degenerate labels (unique={unique_count})")
            return CheckResult(name="cuml smoke", ok=True, details=f"OK (unique labels={unique_count})")
        except Exception as exc:  # noqa: BLE001
            return CheckResult(name="cuml smoke", ok=False, details=f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="cuml smoke", ok=False, details=f"{type(exc).__name__}: {exc}")


def _parse_nvcc_release(nvcc_output: str) -> str | None:
    match = re.search(r"release\s+(\d+\.\d+)", nvcc_output)
    return match.group(1) if match else None


def _print_kv(key: str, value: str) -> None:
    print(f"{key:<22} {value}")


def main() -> int:
    print("# CUDA/GPU Environment Check")
    _print_kv("platform", platform.platform())
    _print_kv("python exe", sys.executable)
    _print_kv("python version", sys.version.splitlines()[0])

    print("\n## Programs")
    program_checks: list[CheckResult] = []
    program_checks.append(_run_cmd(["nvidia-smi"]))
    program_checks.append(_run_cmd(["nvcc", "--version"]))
    program_checks.append(_run_cmd(["git", "--version"]))
    program_checks.append(_run_cmd(["gcc", "--version"]))
    program_checks.append(_run_cmd([sys.executable, "-m", "pip", "--version"]))

    for res in program_checks:
        status = "OK" if res.ok else "FAIL"
        details_line = res.details.splitlines()[0] if res.details else ""
        print(f"- {status:4} {res.name}: {details_line}")

    print("\n## Python Libraries (import + version)")
    libs_to_check = [
        ("torch", "torch"),
        ("torchnmf", "torchnmf"),
        ("cupy", "cupy"),
        ("cuml", "cuml"),
        ("cudf", "cudf"),
        ("rmm", "rmm"),
        ("numba", "numba"),
        ("numpy", "numpy"),
        ("polars", "polars"),
        ("pandas", "pandas"),
        ("scipy", "scipy"),
        ("scikit-learn", "sklearn"),
        ("matplotlib", "matplotlib"),
        ("seaborn", "seaborn"),
        ("openpyxl", "openpyxl"),
        ("PyYAML", "yaml"),
        ("joblib", "joblib"),
    ]
    lib_results = [_import_version(label, mod) for (label, mod) in libs_to_check]
    for res in lib_results:
        status = "OK" if res.ok else "FAIL"
        print(f"- {status:4} {res.name}: {res.details}")

    print("\n## Optional Tools")
    for tool in ["nsys", "ncu"]:
        path = shutil.which(tool)
        if path is None:
            print(f"- INFO {tool}: not found")
            continue
        version_res = _run_cmd([tool, "--version"])
        version_line = version_res.details.splitlines()[0] if version_res.details else ""
        status = "OK" if version_res.ok else "FAIL"
        print(f"- {status:4} {tool}: {path} ({version_line})")

    print("\n## GPU Smoke Tests")
    smoke_results = [
        _torch_smoke_test(),
        _cupy_smoke_test(),
        _cuml_smoke_test(),
    ]
    for res in smoke_results:
        status = "OK" if res.ok else "FAIL"
        print(f"- {status:4} {res.name}: {res.details}")

    print("\n## Version Consistency (warnings only)")
    warnings: list[str] = []
    try:
        import torch

        torch_cuda = torch.version.cuda
        if torch_cuda is not None:
            warnings.append(f"torch.version.cuda = {torch_cuda}")
    except Exception:
        torch_cuda = None

    nvcc_out = next((r.details for r in program_checks if r.name.startswith("nvcc ")), "")
    nvcc_release = _parse_nvcc_release(nvcc_out)
    if nvcc_release is not None:
        warnings.append(f"nvcc release = {nvcc_release}")
        if torch_cuda is not None and str(torch_cuda) != str(nvcc_release):
            warnings.append("WARNING: torch CUDA != nvcc release (may be OK, but mismatched toolchain)")

    for w in warnings:
        print(f"- {w}")

    required_failures: list[CheckResult] = []
    required_failures.extend([r for r in program_checks if not r.ok and r.name.startswith(("nvidia-smi", "nvcc"))])
    required_failures.extend(
        [r for r in lib_results if not r.ok and r.name in {"torch", "torchnmf", "cupy", "cuml", "cudf", "rmm"}]
    )
    required_failures.extend([r for r in smoke_results if not r.ok])

    print("\n## Summary")
    if required_failures:
        print("FAIL")
        for r in required_failures:
            print(f"- {r.name}: {r.details}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
