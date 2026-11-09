import pytest

from endpoint_framework.analysis.clustering import cluster_experiments
from endpoint_framework.analysis.metrics import compute_metrics
from endpoint_framework.rl.agent import DQNAgent
from endpoint_framework.rl.environment import ScenarioSelectionEnv
from endpoint_framework.rl.trainer import train
from endpoint_framework.storage import Database, ExperimentState, ScenarioRun


def _exp_with_runs(db, profile, rows):
    e = db.create_experiment(profile)
    for sid, status in rows:
        db.add_scenario_run(ScenarioRun(experiment_id=e.id, scenario_id=sid, status=status,
                                        duration_s=0.01, telemetry_status="observed"))
    return e


def test_metrics_counts(tmp_path):
    db = Database(tmp_path / "f.db")
    e = _exp_with_runs(db, "baseline", [("SC-001", "completed"), ("SC-010", "skipped"), ("SC-003", "failed")])
    m = compute_metrics(db, e.id)
    assert m.total == 3 and m.completed == 1 and m.skipped == 1 and m.failed == 1
    assert m.layer_coverage.get("user_mode") == 1
    db.close()


def test_clustering_not_meaningful_with_few(tmp_path):
    db = Database(tmp_path / "f.db")
    _exp_with_runs(db, "a", [("SC-001", "completed")])
    assert cluster_experiments(db).meaningful is False
    db.close()


def test_clustering_runs_with_enough(tmp_path):
    db = Database(tmp_path / "f.db")
    for i in range(4):
        _exp_with_runs(db, f"p{i}", [("SC-001", "completed"), ("SC-030", "completed" if i % 2 else "failed")])
    r = cluster_experiments(db)
    assert r.meaningful and r.labels is not None and len(r.labels) == 4
    db.close()


def test_shap_attribution_sums_over_features(tmp_path):
    from endpoint_framework.analysis.explainability import explain_agent
    env = ScenarioSelectionEnv([0, 0, 1, 1, 2, 2, 3, 3, 0, 1], seed=0)
    agent = DQNAgent(env.state_dim, env.action_dim, seed=0)
    train(env, agent, episodes=20, seed=0)
    sids = [f"SC-{i:03d}" for i in range(env.action_dim)]
    attr = explain_agent(agent, sids, n_background=20, n_explain=10, seed=0)
    assert set(attr.importances) == set(sids)
    assert all(v >= 0 for v in attr.importances.values())
    assert attr.method == "shap.GradientExplainer"
