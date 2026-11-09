import sys
from pathlib import Path

import pytest

from endpoint_framework.scenarios import get_scenario, list_scenarios
from endpoint_framework.scenarios.executor import execute


@pytest.mark.parametrize("sid", ["SC-001", "SC-002", "SC-003", "SC-020", "SC-030", "SC-031"])
def test_cross_platform_scenarios_complete(sid, tmp_path):
    res, dur = execute(get_scenario(sid), tmp_path)
    assert res.status == "completed" and dur >= 0 and res.detail


def test_file_scenario_cleans_up(tmp_path):
    execute(get_scenario("SC-003"), tmp_path)
    assert list(tmp_path.iterdir()) == []  # temp probe deleted


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows skip path")
def test_windows_only_scenarios_skip_on_linux(tmp_path):
    for sid in ["SC-010", "SC-011"]:
        res, _ = execute(get_scenario(sid), tmp_path)
        assert res.status == "skipped" and "Windows" in res.detail


def test_every_scenario_has_an_executor(tmp_path):
    # no scenario falls through to the "no executor registered" path
    for sc in list_scenarios():
        res, _ = execute(sc, tmp_path)
        assert res.status in {"completed", "failed", "skipped"}
        assert "no executor registered" not in res.detail
