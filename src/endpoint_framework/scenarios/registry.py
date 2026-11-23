"""Scenario registry: validated lookup over the catalog plus user-defined scenarios.

Enforces the safety invariant in one place: no scenario may be destructive, and
IDs must be unique. Extra non-destructive scenarios can be added from
configs/scenarios.yaml without touching the catalog or the CLI.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from endpoint_framework.scenarios.base import Layer, Scenario
from endpoint_framework.scenarios.catalog import CATALOG


class ScenarioError(KeyError):
    """Unknown scenario id."""


class ScenarioConfigError(Exception):
    """Invalid configs/scenarios.yaml."""


def _build() -> dict[str, Scenario]:
    index: dict[str, Scenario] = {}
    for sc in CATALOG:
        if sc.destructive:
            raise ValueError(f"{sc.id} is marked destructive; the framework runs non-destructive scenarios only")
        if sc.id in index:
            raise ValueError(f"duplicate scenario id: {sc.id}")
        index[sc.id] = sc
    return index


_BUILTIN = _build()
_USER: dict[str, Scenario] = {}


def load_user_scenarios(path: Path) -> int:
    """(Re)load user scenarios from a YAML file. Idempotent; returns how many were loaded."""
    _USER.clear()
    if not path.is_file():
        return 0
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as e:
        raise ScenarioConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, list):
        raise ScenarioConfigError(f"{path} must contain a list of scenarios")
    for entry in data:
        try:
            sc = Scenario.model_validate(entry)
        except ValidationError as e:
            raise ScenarioConfigError(f"Invalid scenario in {path}:\n{e}") from e
        if sc.destructive:
            raise ScenarioConfigError(f"{sc.id} is destructive; only non-destructive scenarios are allowed")
        if sc.id in _BUILTIN:
            raise ScenarioConfigError(f"{sc.id} clashes with a built-in scenario id")
        if sc.id in _USER:
            raise ScenarioConfigError(f"duplicate scenario id in {path}: {sc.id}")
        _USER[sc.id] = sc
    return len(_USER)


def _index() -> dict[str, Scenario]:
    return {**_BUILTIN, **_USER}


def list_scenarios(layer: Layer | None = None) -> list[Scenario]:
    items = list(_index().values())
    if layer is not None:
        items = [s for s in items if s.layer is layer]
    return sorted(items, key=lambda s: s.id)


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return _index()[scenario_id]
    except KeyError:
        raise ScenarioError(scenario_id) from None
