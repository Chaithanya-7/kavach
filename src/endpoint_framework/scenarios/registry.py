"""Scenario registry: validated lookup over the catalog.

Enforces the safety invariant in one place: no scenario may be destructive, and
IDs must be unique. Extra scenarios can be registered without touching the CLI.
"""

from __future__ import annotations

from endpoint_framework.scenarios.base import Layer, Scenario
from endpoint_framework.scenarios.catalog import CATALOG


class ScenarioError(KeyError):
    """Unknown scenario id."""


def _build() -> dict[str, Scenario]:
    index: dict[str, Scenario] = {}
    for sc in CATALOG:
        if sc.destructive:
            raise ValueError(f"{sc.id} is marked destructive; the framework runs non-destructive scenarios only")
        if sc.id in index:
            raise ValueError(f"duplicate scenario id: {sc.id}")
        index[sc.id] = sc
    return index


_INDEX = _build()


def list_scenarios(layer: Layer | None = None) -> list[Scenario]:
    items = list(_INDEX.values())
    if layer is not None:
        items = [s for s in items if s.layer is layer]
    return sorted(items, key=lambda s: s.id)


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return _INDEX[scenario_id]
    except KeyError:
        raise ScenarioError(scenario_id) from None
