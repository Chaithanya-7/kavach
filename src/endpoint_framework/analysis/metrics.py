"""Compute experiment metrics from stored scenario runs (observed data only)."""

from __future__ import annotations

from dataclasses import dataclass, field

from endpoint_framework.scenarios import get_scenario
from endpoint_framework.scenarios.registry import ScenarioError
from endpoint_framework.storage import Database


@dataclass
class ExperimentMetrics:
    experiment_id: str
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    telemetry_observed: int = 0
    mean_duration_s: float = 0.0
    layer_coverage: dict[str, int] = field(default_factory=dict)

    @property
    def completion_rate(self) -> float:
        return self.completed / self.total if self.total else 0.0


def compute_metrics(db: Database, experiment_id: str) -> ExperimentMetrics:
    runs = db.runs_for(experiment_id)
    m = ExperimentMetrics(experiment_id=experiment_id, total=len(runs))
    durations: list[float] = []
    for r in runs:
        m.completed += r.status == "completed"
        m.failed += r.status == "failed"
        m.skipped += r.status == "skipped"
        m.telemetry_observed += r.telemetry_status == "observed"
        if r.duration_s is not None:
            durations.append(r.duration_s)
        try:
            layer = get_scenario(r.scenario_id).layer.value
        except ScenarioError:
            layer = "unknown"
        if r.status == "completed":
            m.layer_coverage[layer] = m.layer_coverage.get(layer, 0) + 1
    m.mean_duration_s = sum(durations) / len(durations) if durations else 0.0
    return m
