"""Environment readiness checks used by ``framework doctor``.

Checks only *observe* the host. They never change system settings, enable
providers, or touch security-product configuration.
"""

from __future__ import annotations

import importlib.util
import platform
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum

from endpoint_framework.core.config import LoadedConfig

MIN_PYTHON = (3, 11)
WIN11_MIN_BUILD = 22000

# Event logs the telemetry layer (Stage 4) will read. Presence only is checked here.
EVENT_LOGS: dict[str, str] = {
    "Sysmon": "Microsoft-Windows-Sysmon/Operational",
    "Security": "Security",
    "Defender": "Microsoft-Windows-Windows Defender/Operational",
}


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"  # not applicable on this host (e.g. Windows check on Linux dev box)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str


def is_windows() -> bool:
    return sys.platform == "win32"


def windows_build(version_string: str) -> int | None:
    """'10.0.22631' -> 22631. Windows 11 still reports major 10; the build number tells them apart."""
    parts = version_string.split(".")
    try:
        return int(parts[2])
    except (IndexError, ValueError):
        return None


def check_python() -> CheckResult:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    return CheckResult(
        "Python version",
        Status.PASS if ok else Status.FAIL,
        f"{platform.python_version()} (need >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})",
    )


def check_os() -> CheckResult:
    if not is_windows():
        return CheckResult(
            "Operating system",
            Status.WARN,
            f"{platform.system()} {platform.release()}: development only; experiments require Windows 11",
        )
    build = windows_build(platform.version())
    if build is not None and build >= WIN11_MIN_BUILD:
        return CheckResult("Operating system", Status.PASS, f"Windows 11 (build {build})")
    return CheckResult("Operating system", Status.WARN, f"Windows build {build}: Windows 11 is the supported target")


def check_admin() -> CheckResult:
    if not is_windows():
        return CheckResult("Administrator", Status.SKIP, "not Windows")
    import ctypes

    try:
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except OSError as e:
        return CheckResult("Administrator", Status.WARN, f"could not determine: {e}")
    # Not a failure: most work runs unprivileged; only the Security log needs elevation.
    return CheckResult(
        "Administrator",
        Status.PASS if admin else Status.WARN,
        "elevated" if admin else "not elevated (Security log reads will be unavailable)",
    )


def check_module(module: str, label: str, windows_only: bool = False) -> CheckResult:
    if windows_only and not is_windows():
        return CheckResult(label, Status.SKIP, "not Windows")
    found = importlib.util.find_spec(module) is not None
    return CheckResult(label, Status.PASS if found else Status.FAIL, "importable" if found else f"'{module}' not installed")


def check_event_log(label: str, channel: str) -> CheckResult:
    name = f"Event log: {label}"
    if not is_windows():
        return CheckResult(name, Status.SKIP, "not Windows")
    try:
        proc = subprocess.run(
            ["wevtutil", "gl", channel], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return CheckResult(name, Status.WARN, f"wevtutil failed: {e}")
    if proc.returncode != 0:
        # Missing channel, or access denied (Security without elevation). Unavailable != "no detections".
        msg = (proc.stderr or proc.stdout).strip().splitlines()
        return CheckResult(name, Status.WARN, f"unavailable: {msg[0] if msg else 'rc=' + str(proc.returncode)}")
    enabled = "enabled: true" in proc.stdout.lower()
    return CheckResult(
        name,
        Status.PASS if enabled else Status.WARN,
        f"{channel} present, {'enabled' if enabled else 'DISABLED'}",
    )


def check_config(loaded: LoadedConfig) -> CheckResult:
    src = str(loaded.source) if loaded.source else "built-in defaults (run 'framework init')"
    return CheckResult("Configuration", Status.PASS if loaded.source else Status.WARN, src)


def check_workspace(loaded: LoadedConfig) -> CheckResult:
    missing = [str(p) for p in loaded.output_dirs if not p.is_dir()]
    if missing:
        return CheckResult("Workspace dirs", Status.WARN, f"missing: {', '.join(missing)}")
    return CheckResult("Workspace dirs", Status.PASS, str(loaded.root))


def check_lab(loaded: LoadedConfig) -> CheckResult:
    lab = loaded.config.lab
    if lab.authorized:
        return CheckResult("Lab authorization", Status.PASS, f"'{lab.name}' marked as isolated, authorized lab")
    return CheckResult(
        "Lab authorization", Status.WARN, "lab.authorized is false: scenario execution will be refused"
    )


def run_all_checks(loaded: LoadedConfig) -> list[CheckResult]:
    results = [
        check_python(),
        check_os(),
        check_admin(),
        check_module("typer", "Dependency: typer"),
        check_module("rich", "Dependency: rich"),
        check_module("pydantic", "Dependency: pydantic"),
        check_module("yaml", "Dependency: pyyaml"),
        check_module("win32evtlog", "Dependency: pywin32", windows_only=True),
    ]
    results += [check_event_log(label, ch) for label, ch in EVENT_LOGS.items()]
    results += [check_config(loaded), check_workspace(loaded), check_lab(loaded)]
    return results
