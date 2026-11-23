import pytest

from endpoint_framework.scenarios import list_scenarios, get_scenario
from endpoint_framework.scenarios.registry import ScenarioConfigError, load_user_scenarios

VALID = """
- id: SC-100
  name: Custom file read
  description: benign file read
  layer: user_mode
  mitre_attack: T1005
"""


def _write(tmp_path, text):
    p = tmp_path / "scenarios.yaml"
    p.write_text(text)
    return p


def teardown_function():
    load_user_scenarios.__globals__["_USER"].clear()  # keep other tests isolated


def test_missing_file_is_noop(tmp_path):
    assert load_user_scenarios(tmp_path / "nope.yaml") == 0
    assert get_scenario("SC-001")  # built-ins still present


def test_load_adds_scenario(tmp_path):
    n = load_user_scenarios(_write(tmp_path, VALID))
    assert n == 1
    assert get_scenario("SC-100").name == "Custom file read"
    assert "SC-100" in {s.id for s in list_scenarios()}


def test_idempotent_reload(tmp_path):
    p = _write(tmp_path, VALID)
    load_user_scenarios(p)
    load_user_scenarios(p)  # must not raise duplicate
    assert len([s for s in list_scenarios() if s.id == "SC-100"]) == 1


def test_destructive_rejected(tmp_path):
    bad = VALID + "  destructive: true\n"
    with pytest.raises(ScenarioConfigError, match="destructive"):
        load_user_scenarios(_write(tmp_path, bad))


def test_clash_with_builtin_rejected(tmp_path):
    clash = "- id: SC-001\n  name: x\n  description: x\n  layer: user_mode\n"
    with pytest.raises(ScenarioConfigError, match="clashes"):
        load_user_scenarios(_write(tmp_path, clash))


def test_not_a_list_rejected(tmp_path):
    with pytest.raises(ScenarioConfigError, match="list"):
        load_user_scenarios(_write(tmp_path, "id: SC-100\n"))
