import pytest

from endpoint_framework.storage import Database, ExperimentState, ScenarioRun
from endpoint_framework.storage.database import StateError
from endpoint_framework.storage.models import can_transition


def test_create_and_sequential_ids(tmp_path):
    db = Database(tmp_path / "f.db")
    a = db.create_experiment("baseline")
    b = db.create_experiment("user")
    assert a.id == "EXP-001" and b.id == "EXP-002"
    assert [e.id for e in db.list_experiments()] == ["EXP-001", "EXP-002"]
    db.close()


def test_legal_transition_sequence(tmp_path):
    db = Database(tmp_path / "f.db")
    e = db.create_experiment("baseline")
    for s in [ExperimentState.VALIDATED, ExperimentState.RUNNING, ExperimentState.COLLECTING,
              ExperimentState.ANALYZING, ExperimentState.COMPLETED]:
        db.set_state(e.id, s)
    assert db.get_experiment(e.id).state == "COMPLETED"
    db.close()


def test_illegal_transition_rejected(tmp_path):
    db = Database(tmp_path / "f.db")
    e = db.create_experiment("baseline")
    with pytest.raises(StateError):
        db.set_state(e.id, ExperimentState.COMPLETED)  # skip the chain
    db.close()


def test_terminal_is_terminal():
    assert not can_transition(ExperimentState.COMPLETED, ExperimentState.RUNNING)
    assert can_transition(ExperimentState.RUNNING, ExperimentState.FAILED)


def test_scenario_runs_persist(tmp_path):
    db = Database(tmp_path / "f.db")
    e = db.create_experiment("baseline")
    db.add_scenario_run(ScenarioRun(experiment_id=e.id, scenario_id="SC-001", status="completed", event_count=3))
    runs = db.runs_for(e.id)
    assert len(runs) == 1 and runs[0].scenario_id == "SC-001" and runs[0].id is not None
    db.close()
