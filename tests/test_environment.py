import sys

import pytest

from endpoint_framework.core import environment as env
from endpoint_framework.core.config import load_config


@pytest.mark.parametrize("v,expected", [("10.0.22631", 22631), ("10.0.19045", 19045), ("garbage", None)])
def test_windows_build_parse(v, expected):
    assert env.windows_build(v) == expected


def test_python_check_passes_here():
    assert env.check_python().status is env.Status.PASS


def test_windows_checks_skip_off_windows(monkeypatch):
    monkeypatch.setattr(env, "is_windows", lambda: False)
    assert env.check_admin().status is env.Status.SKIP
    assert env.check_event_log("Sysmon", "x").status is env.Status.SKIP
    assert env.check_os().status is env.Status.WARN


def test_missing_module_fails():
    assert env.check_module("definitely_not_a_module_xyz", "x").status is env.Status.FAIL


def test_disabled_event_log_is_warn_not_pass(monkeypatch):
    class P:
        returncode, stdout, stderr = 0, "name: Security\nenabled: false\n", ""

    monkeypatch.setattr(env, "is_windows", lambda: True)
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: P())
    assert env.check_event_log("Security", "Security").status is env.Status.WARN


def test_unavailable_event_log_is_warn(monkeypatch):
    class P:
        returncode, stdout, stderr = 15007, "", "Failed to read configuration for log x. The specified channel could not be found."

    monkeypatch.setattr(env, "is_windows", lambda: True)
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: P())
    r = env.check_event_log("Sysmon", "x")
    assert r.status is env.Status.WARN and "unavailable" in r.detail


def test_lab_gate_defaults_to_warn(workspace):
    assert env.check_lab(load_config()).status is env.Status.WARN


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows host only")
def test_real_windows_checks_run():
    results = env.run_all_checks(load_config())
    assert all(r.status is not env.Status.SKIP for r in results if r.name.startswith("Event log"))
