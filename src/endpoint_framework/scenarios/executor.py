"""Execute non-destructive scenarios and return a result record.

Every action is benign and self-cleaning. Windows-only actions (registry,
scheduled task) raise Unsupported on other hosts so the run is honestly recorded
as 'skipped', never as a fake success.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from endpoint_framework.core.log import get_logger
from endpoint_framework.scenarios.base import Scenario

log = get_logger("executor")
_IS_WIN = sys.platform == "win32"


class Unsupported(Exception):
    """The scenario cannot run on this host (e.g. a Windows-only action on Linux)."""


@dataclass
class ExecResult:
    status: str  # "completed" | "failed" | "skipped"
    detail: str


def _run(cmd: list[str], timeout: int) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} rc={p.returncode}: {(p.stderr or p.stdout).strip()[:200]}")
    return p.stdout.strip()


# --- benign actions (return a short detail string; raise on failure/unsupported) ---

def _process(timeout: int) -> str:
    cmd = ["cmd", "/c", "whoami"] if _IS_WIN else ["/bin/sh", "-c", "id -un"]
    return f"ran {cmd[0]} -> {_run(cmd, timeout)!r}"


def _process_chain(timeout: int) -> str:
    # one shell spawning a child, to produce a parent->child lineage
    if _IS_WIN:
        return f"chain -> {_run(['cmd', '/c', 'cmd /c whoami'], timeout)!r}"
    return f"chain -> {_run(['/bin/sh', '-c', 'sh -c \"id -un\"'], timeout)!r}"


def _file(workspace: Path, timeout: int) -> str:
    f = workspace / "sc_tmp_probe.txt"
    try:
        f.write_text("kavach non-destructive probe\n", encoding="utf-8")
        f.write_text("modified\n", encoding="utf-8")
        size = f.stat().st_size
    finally:
        f.unlink(missing_ok=True)  # cleanup
    return f"created+modified+deleted {f.name} ({size} bytes)"


def _service_query(timeout: int) -> str:
    cmd = ["sc", "query", "Schedule"] if _IS_WIN else ["systemctl", "--version"]
    try:
        out = _run(cmd, timeout)
    except FileNotFoundError as e:
        raise Unsupported(f"{cmd[0]} not available: {e}") from e
    return f"read-only query via {cmd[0]} ({len(out.splitlines())} lines)"


def _registry(timeout: int) -> str:
    if not _IS_WIN:
        raise Unsupported("registry scenario requires Windows")
    key = r"HKCU\Software\KavachTest"
    _run(["reg", "add", key, "/v", "probe", "/t", "REG_SZ", "/d", "1", "/f"], timeout)
    _run(["reg", "delete", key, "/f"], timeout)  # cleanup
    return f"created and deleted value under {key}"


def _schtask(timeout: int) -> str:
    if not _IS_WIN:
        raise Unsupported("scheduled-task scenario requires Windows")
    name = "KavachProbeTask"
    _run(["schtasks", "/create", "/tn", name, "/tr", "cmd /c exit", "/sc", "once",
          "/st", "23:59", "/f"], timeout)
    _run(["schtasks", "/delete", "/tn", name, "/f"], timeout)  # cleanup
    return f"created and deleted scheduled task {name}"


def _tcp(timeout: int) -> str:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(timeout)
    port = srv.getsockname()[1]
    cli = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    conn, _ = srv.accept()
    cli.close()
    conn.close()
    srv.close()  # cleanup
    return f"loopback TCP connect to 127.0.0.1:{port}"


def _dns(timeout: int) -> str:
    host = "localhost"  # designated lab target; no external traffic
    socket.setdefaulttimeout(timeout)
    infos = socket.getaddrinfo(host, None)
    return f"resolved {host} -> {infos[0][4][0]}"


def execute(scenario: Scenario, workspace: Path) -> tuple[ExecResult, float]:
    """Run a scenario's benign action. Returns (result, duration_seconds)."""
    t0 = time.monotonic()
    to = scenario.timeout_seconds
    try:
        if scenario.id in {"SC-001"}:
            detail = _process(to)
        elif scenario.id == "SC-002":
            detail = _process_chain(to)
        elif scenario.id == "SC-003":
            detail = _file(workspace, to)
        elif scenario.id == "SC-010":
            detail = _registry(to)
        elif scenario.id == "SC-011":
            detail = _schtask(to)
        elif scenario.id == "SC-012":
            detail = _service_query(to)
        elif scenario.id in {"SC-020", "SC-021"}:
            detail = _process(to)
        elif scenario.id == "SC-030":
            detail = _tcp(to)
        elif scenario.id == "SC-031":
            detail = _dns(to)
        else:
            raise Unsupported(f"no executor registered for {scenario.id}")
        dur = time.monotonic() - t0
        log.info("scenario executed", extra={"scenario": scenario.id, "detail": detail})
        return ExecResult("completed", detail), dur
    except Unsupported as e:
        return ExecResult("skipped", str(e)), time.monotonic() - t0
    except (subprocess.TimeoutExpired, RuntimeError, OSError) as e:
        log.warning("scenario failed", extra={"scenario": scenario.id, "error": str(e)})
        return ExecResult("failed", str(e)), time.monotonic() - t0
