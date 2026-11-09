import pytest
from typer.testing import CliRunner

from endpoint_framework.cli import app
from endpoint_framework.scenarios import get_scenario, list_scenarios
from endpoint_framework.scenarios.base import Layer
from endpoint_framework.scenarios.registry import ScenarioError, _build

runner = CliRunner()


def test_catalog_nonempty_and_sorted():
    items = list_scenarios()
    assert items and [s.id for s in items] == sorted(s.id for s in items)


def test_no_destructive_scenarios():
    assert all(not s.destructive for s in list_scenarios())


def test_layer_filter():
    net = list_scenarios(Layer.NETWORK)
    assert net and all(s.layer is Layer.NETWORK for s in net)


def test_get_and_unknown():
    assert get_scenario("SC-001").id == "SC-001"
    with pytest.raises(ScenarioError):
        get_scenario("SC-999")


def test_registry_rejects_duplicate_or_destructive(monkeypatch):
    from endpoint_framework.scenarios import registry
    bad = get_scenario("SC-001").model_copy(update={"destructive": True})
    monkeypatch.setattr(registry, "CATALOG", [bad])
    with pytest.raises(ValueError, match="destructive"):
        _build()


def test_cli_list_and_info():
    r = runner.invoke(app, ["scenarios", "list"])
    assert r.exit_code == 0 and "SC-001" in r.output
    r = runner.invoke(app, ["scenarios", "info", "sc-001"])
    assert r.exit_code == 0 and "Process creation" in r.output
    r = runner.invoke(app, ["scenarios", "info", "SC-999"])
    assert r.exit_code == 2
