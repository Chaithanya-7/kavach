"""SQLite persistence for experiments and scenario runs (stdlib sqlite3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from endpoint_framework.storage.models import (
    Experiment,
    ExperimentState,
    ScenarioRun,
    _now,
    can_transition,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id          TEXT PRIMARY KEY,
    profile     TEXT NOT NULL,
    state       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    seed        INTEGER NOT NULL,
    host        TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS scenario_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id    TEXT NOT NULL REFERENCES experiments(id),
    scenario_id      TEXT NOT NULL,
    status           TEXT NOT NULL,
    started_at       TEXT NOT NULL,
    ended_at         TEXT,
    duration_s       REAL,
    detail           TEXT NOT NULL DEFAULT '',
    telemetry_status TEXT NOT NULL DEFAULT 'pending',
    event_count      INTEGER NOT NULL DEFAULT 0
);
"""


class StateError(Exception):
    """Illegal experiment state transition."""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- experiments ---
    def next_experiment_id(self) -> str:
        n = self._conn.execute("SELECT COUNT(*) AS c FROM experiments").fetchone()["c"]
        return f"EXP-{n + 1:03d}"

    def create_experiment(self, profile: str, seed: int = 42, host: str = "") -> Experiment:
        exp = Experiment(id=self.next_experiment_id(), profile=profile, seed=seed, host=host)
        self._conn.execute(
            "INSERT INTO experiments (id, profile, state, created_at, updated_at, seed, host, note)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (exp.id, exp.profile, exp.state, exp.created_at, exp.updated_at, exp.seed, exp.host, exp.note),
        )
        self._conn.commit()
        return exp

    def set_state(self, experiment_id: str, dst: ExperimentState) -> None:
        exp = self.get_experiment(experiment_id)
        if exp is None:
            raise KeyError(experiment_id)
        src = ExperimentState(exp.state)
        if src is not dst and not can_transition(src, dst):
            raise StateError(f"{experiment_id}: {src.value} -> {dst.value} is not allowed")
        self._conn.execute(
            "UPDATE experiments SET state = ?, updated_at = ? WHERE id = ?", (dst.value, _now(), experiment_id)
        )
        self._conn.commit()

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        row = self._conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        return Experiment(**dict(row)) if row else None

    def list_experiments(self) -> list[Experiment]:
        rows = self._conn.execute("SELECT * FROM experiments ORDER BY id").fetchall()
        return [Experiment(**dict(r)) for r in rows]

    # --- scenario runs ---
    def add_scenario_run(self, run: ScenarioRun) -> ScenarioRun:
        cur = self._conn.execute(
            "INSERT INTO scenario_runs (experiment_id, scenario_id, status, started_at, ended_at,"
            " duration_s, detail, telemetry_status, event_count) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                run.experiment_id, run.scenario_id, run.status, run.started_at, run.ended_at,
                run.duration_s, run.detail, run.telemetry_status, run.event_count,
            ),
        )
        self._conn.commit()
        run.id = cur.lastrowid
        return run

    def runs_for(self, experiment_id: str) -> list[ScenarioRun]:
        rows = self._conn.execute(
            "SELECT * FROM scenario_runs WHERE experiment_id = ? ORDER BY id", (experiment_id,)
        ).fetchall()
        return [ScenarioRun(**dict(r)) for r in rows]
