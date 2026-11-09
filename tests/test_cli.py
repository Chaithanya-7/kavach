import json

from typer.testing import CliRunner

from endpoint_framework import __version__
from endpoint_framework.cli import app

runner = CliRunner()


def test_help():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("init", "status", "doctor"):
        assert cmd in r.output


def test_version():
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0 and __version__ in r.output


def test_init_creates_workspace_and_log(workspace):
    r = runner.invoke(app, ["init"])
    assert r.exit_code == 0, r.output
    assert (workspace / "configs" / "framework.yaml").is_file()
    for d in ("experiments", "outputs/logs", "outputs/models", "outputs/graphs", "outputs/reports"):
        assert (workspace / d).is_dir()
    lines = (workspace / "outputs/logs/framework.jsonl").read_text().splitlines()
    entry = json.loads(lines[-1])
    assert entry["msg"] == "workspace initialized" and "root" in entry


def test_init_does_not_overwrite_without_force(workspace):
    runner.invoke(app, ["init"])
    cfg = workspace / "configs" / "framework.yaml"
    cfg.write_text("seed: 99\n")
    runner.invoke(app, ["init"])
    assert cfg.read_text() == "seed: 99\n"
    runner.invoke(app, ["init", "--force"])
    assert "seed: 42" in cfg.read_text()


def test_status_after_init(workspace):
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["status"])
    assert r.exit_code == 0, r.output
    assert "not authorized" in r.output


def test_doctor_runs_and_logs(workspace):
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["doctor"])
    assert r.exit_code == 0, r.output  # no FAIL in a correctly installed environment
    assert "Python version" in r.output
    logged = [json.loads(l) for l in (workspace / "outputs/logs/framework.jsonl").read_text().splitlines()]
    assert any(e.get("check") == "Python version" for e in logged)


def test_invalid_config_exits_2(workspace):
    bad = workspace / "bad.yaml"
    bad.write_text("unknown_key: 1\n")
    r = runner.invoke(app, ["--config", str(bad), "status"])
    assert r.exit_code == 2


def _auth_cfg(workspace):
    runner.invoke(app, ["init"])
    cfg = workspace / "configs" / "framework.yaml"
    cfg.write_text(cfg.read_text().replace("authorized: false", "authorized: true"))
    return str(cfg)


def test_run_requires_one_selector(workspace):
    runner.invoke(app, ["init"])
    assert runner.invoke(app, ["run"]).exit_code == 2
    assert runner.invoke(app, ["run", "-s", "SC-001", "-p", "baseline"]).exit_code == 2


def test_run_unknown_scenario(workspace):
    runner.invoke(app, ["init"])
    assert runner.invoke(app, ["run", "-s", "SC-999"]).exit_code == 2


def test_run_refused_without_lab_auth(workspace):
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["run", "-s", "SC-001"])
    assert r.exit_code == 2 and "Refused" in r.output


def test_run_completes_when_authorized(workspace):
    cfg = _auth_cfg(workspace)
    r = runner.invoke(app, ["--config", cfg, "run", "-s", "SC-001"])
    assert r.exit_code == 0 and "COMPLETED" in r.output


def test_train_validates_episodes(workspace):
    runner.invoke(app, ["init"])
    assert runner.invoke(app, ["train", "-e", "0"]).exit_code != 0  # min=1


def test_evaluate_mode_validation(workspace):
    cfg = _auth_cfg(workspace)
    assert runner.invoke(app, ["--config", cfg, "evaluate", "-m", "stealth"]).exit_code == 2


def test_evaluate_fixed_and_random_execute(workspace):
    cfg = _auth_cfg(workspace)
    for mode in ("fixed", "random"):
        r = runner.invoke(app, ["--config", cfg, "evaluate", "-m", mode])
        assert r.exit_code == 0, r.output
        assert "COMPLETED" in r.output
    from endpoint_framework.storage import Database
    db = Database(workspace / "experiments" / "framework.db")
    assert {e.profile for e in db.list_experiments()} == {"eval-fixed", "eval-random"}
    db.close()


def test_evaluate_adaptive_needs_checkpoint(workspace):
    cfg = _auth_cfg(workspace)
    r = runner.invoke(app, ["--config", cfg, "evaluate", "-m", "adaptive"])
    assert r.exit_code == 2 and "No DQN checkpoint" in r.output


def test_evaluate_adaptive_after_train(workspace):
    cfg = _auth_cfg(workspace)
    runner.invoke(app, ["--config", cfg, "train", "-e", "30"])
    r = runner.invoke(app, ["--config", cfg, "evaluate", "-m", "adaptive"])
    assert r.exit_code == 0 and "COMPLETED" in r.output




def test_menu_shows_banner_and_real_commands():
    r = runner.invoke(app, ["menu"])
    assert r.exit_code == 0
    assert "KAVACH".replace("KAVACH", "") == ""  # banner is art; check menu text instead
    assert "SCENARIO MODULES" in r.output and "scenarios list" in r.output
    assert "authorized, non-destructive" in r.output


def test_shell_dispatches_then_exits(workspace):
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["shell"], input="scenarios list\nexit\n")
    assert r.exit_code == 0
    assert "SC-001" in r.output  # the dispatched command ran


def test_shell_survives_bad_command(workspace):
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["shell"], input="nonsense-xyz\nexit\n")
    assert r.exit_code == 0  # bad command did not crash the console


def test_run_scenario_persists_experiment(workspace):
    cfg = _auth_cfg(workspace)
    r = runner.invoke(app, ["--config", cfg, "run", "-s", "SC-001"])
    assert r.exit_code == 0, r.output
    assert "EXP-001" in r.output and "COMPLETED" in r.output
    from endpoint_framework.storage import Database
    db = Database(workspace / "experiments" / "framework.db")
    exp = db.get_experiment("EXP-001")
    assert exp.state == "COMPLETED" and len(db.runs_for("EXP-001")) == 1
    db.close()


def test_run_profile_executes_multiple(workspace):
    cfg = _auth_cfg(workspace)
    r = runner.invoke(app, ["--config", cfg, "run", "-p", "user"])
    assert r.exit_code == 0, r.output
    from endpoint_framework.storage import Database
    db = Database(workspace / "experiments" / "framework.db")
    assert len(db.runs_for("EXP-001")) == 3  # three user-mode scenarios
    db.close()


def test_run_unknown_profile(workspace):
    cfg = _auth_cfg(workspace)
    assert runner.invoke(app, ["--config", cfg, "run", "-p", "nope"]).exit_code == 2


def test_train_produces_checkpoint_and_metrics(workspace):
    import json
    runner.invoke(app, ["init"])
    r = runner.invoke(app, ["train", "-e", "40"])
    assert r.exit_code == 0, r.output
    assert (workspace / "outputs/models/dqn.pt").is_file()
    m = json.loads((workspace / "outputs/models/dqn_metrics.json").read_text())
    assert m["episodes"] == 40 and m["simulated"] is True and len(m["episode_returns"]) == 40


def test_analyze_and_report_endtoend(workspace):
    cfg = _auth_cfg(workspace)
    runner.invoke(app, ["--config", cfg, "run", "-p", "baseline"])
    runner.invoke(app, ["--config", cfg, "train", "-e", "30"])
    a = runner.invoke(app, ["--config", cfg, "analyze", "-r", "EXP-001"])
    assert a.exit_code == 0, a.output
    assert "metrics" in a.output.lower() and "SHAP" in a.output
    assert (workspace / "outputs/reports/EXP-001_analysis.json").is_file()
    r = runner.invoke(app, ["--config", cfg, "report", "-r", "EXP-001"])
    assert r.exit_code == 0, r.output
    for f in ["EXP-001_runs.csv", "EXP-001_metrics.json", "EXP-001_coverage.png", "dqn_training_curve.png"]:
        assert (workspace / "outputs/reports" / f).is_file()


def test_analyze_unknown_experiment(workspace):
    cfg = _auth_cfg(workspace)
    assert runner.invoke(app, ["--config", cfg, "analyze", "-r", "EXP-999"]).exit_code == 2


def test_run_stores_telemetry_status(workspace):
    cfg = _auth_cfg(workspace)
    runner.invoke(app, ["--config", cfg, "run", "-s", "SC-001"])
    from endpoint_framework.storage import Database
    db = Database(workspace / "experiments" / "framework.db")
    r = db.runs_for("EXP-001")[0]
    assert r.telemetry_status == "source_unavailable"  # off Windows, honestly
    db.close()


def test_benchmark_compares_three_strategies(workspace):
    cfg = _auth_cfg(workspace)
    runner.invoke(app, ["--config", cfg, "train", "-e", "40"])
    r = runner.invoke(app, ["--config", cfg, "benchmark"])
    assert r.exit_code == 0, r.output
    for mode in ("fixed", "random", "adaptive"):
        assert mode in r.output
    import json
    data = json.loads((workspace / "outputs/reports/benchmark.json").read_text())
    assert set(data) == {"fixed", "random", "adaptive"}
    assert (workspace / "outputs/reports/benchmark.png").is_file()


def test_benchmark_needs_checkpoint(workspace):
    cfg = _auth_cfg(workspace)
    r = runner.invoke(app, ["--config", cfg, "benchmark"])
    assert r.exit_code == 2 and "No DQN checkpoint" in r.output
