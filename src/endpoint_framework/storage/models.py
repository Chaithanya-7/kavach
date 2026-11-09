"""Experiment records. Plain dataclasses; the database stores them as rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ExperimentState(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    RUNNING = "RUNNING"
    COLLECTING = "COLLECTING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Allowed forward transitions; FAILED/CANCELLED are reachable from any live state.
_NEXT: dict[ExperimentState, set[ExperimentState]] = {
    ExperimentState.CREATED: {ExperimentState.VALIDATED},
    ExperimentState.VALIDATED: {ExperimentState.RUNNING},
    ExperimentState.RUNNING: {ExperimentState.COLLECTING},
    ExperimentState.COLLECTING: {ExperimentState.ANALYZING, ExperimentState.COMPLETED},
    ExperimentState.ANALYZING: {ExperimentState.COMPLETED},
}
_TERMINAL = {ExperimentState.COMPLETED, ExperimentState.FAILED, ExperimentState.CANCELLED}


def can_transition(src: ExperimentState, dst: ExperimentState) -> bool:
    if src in _TERMINAL:
        return False
    if dst in {ExperimentState.FAILED, ExperimentState.CANCELLED}:
        return True
    return dst in _NEXT.get(src, set())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelemetryStatus(str, Enum):
    OBSERVED = "observed"
    NOT_OBSERVED = "not_observed"
    SOURCE_UNAVAILABLE = "source_unavailable"
    COLLECTION_FAILURE = "collection_failure"
    PENDING = "pending"  # execution happened but telemetry layer (Stage 4) not wired on this host


@dataclass
class ScenarioRun:
    experiment_id: str
    scenario_id: str
    status: str  # "completed" | "failed"
    started_at: str = field(default_factory=_now)
    ended_at: str | None = None
    duration_s: float | None = None
    detail: str = ""
    telemetry_status: str = TelemetryStatus.PENDING.value
    event_count: int = 0
    id: int | None = None  # set by the database


@dataclass
class Experiment:
    id: str
    profile: str
    state: str = ExperimentState.CREATED.value
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    seed: int = 42
    host: str = ""
    note: str = ""
