"""Command-line interface (Typer + Rich)."""

from __future__ import annotations

import platform
import shlex
from pathlib import Path
from typing import Optional

import click
import typer
from rich.console import Console
from rich.table import Table

from endpoint_framework import __version__
from endpoint_framework.core.config import (
    DEFAULT_CONFIG_RELPATH,
    ConfigError,
    LoadedConfig,
    default_config_yaml,
    load_config,
)
from endpoint_framework.core.environment import Status, run_all_checks
from endpoint_framework.core.log import get_logger, setup_logging
from endpoint_framework.scenarios import get_scenario, list_scenarios
from endpoint_framework.scenarios.base import Layer
from endpoint_framework.scenarios.registry import ScenarioError
from endpoint_framework.ui import render_banner, render_menu

app = typer.Typer(
    name="framework",
    help="Adaptive Cross-Layer Endpoint Defense Evaluation Framework (authorized lab use only).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)

STATUS_STYLE = {Status.PASS: "green", Status.WARN: "yellow", Status.FAIL: "red", Status.SKIP: "dim"}


def _version_cb(value: bool) -> None:
    if value:
        console.print(f"framework {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to framework.yaml (default: ./configs/framework.yaml or $FRAMEWORK_CONFIG)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logs on the console."),
    version: bool = typer.Option(False, "--version", callback=_version_cb, is_eager=True, help="Show version and exit."),
) -> None:
    ctx.obj = {"config_path": config, "verbose": verbose}


def _load(ctx: typer.Context) -> LoadedConfig:
    try:
        loaded = load_config(ctx.obj["config_path"])
    except ConfigError as e:
        err_console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(code=2)
    log_file = loaded.resolve(loaded.config.logging.file) if loaded.source else None
    setup_logging(loaded.config.logging.level, log_file, ctx.obj["verbose"])
    return loaded


@app.command()
def init(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="Overwrite an existing configs/framework.yaml."),
) -> None:
    """Create configs/framework.yaml and the workspace directories in the current directory."""
    cfg_path = Path.cwd() / DEFAULT_CONFIG_RELPATH
    if cfg_path.exists() and not force:
        console.print(f"[yellow]Config already exists:[/yellow] {cfg_path} (use --force to overwrite)")
    else:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(default_config_yaml(), encoding="utf-8")
        console.print(f"[green]Wrote[/green] {cfg_path}")

    ctx.obj["config_path"] = cfg_path
    loaded = _load(ctx)
    for d in loaded.output_dirs:
        d.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]Ready[/green]  {d}")
    get_logger("cli").info("workspace initialized", extra={"root": str(loaded.root), "config": str(cfg_path)})
    console.print("\nNext: run [bold]framework doctor[/bold]. Edit [bold]lab.authorized[/bold] only inside an isolated test VM.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show the active configuration and workspace state."""
    loaded = _load(ctx)
    c = loaded.config
    t = Table(title="Framework status", show_header=False)
    t.add_column("Item", style="bold")
    t.add_column("Value")
    t.add_row("Version", __version__)
    t.add_row("Host", f"{platform.system()} {platform.release()} ({platform.version()})")
    t.add_row("Config", str(loaded.source) if loaded.source else "[yellow]built-in defaults (not initialized)[/yellow]")
    t.add_row("Workspace root", str(loaded.root))
    t.add_row("Random seed", str(c.seed))
    t.add_row("Lab", f"{c.lab.name} — " + ("[green]authorized[/green]" if c.lab.authorized else "[yellow]not authorized[/yellow]"))
    db = loaded.resolve(c.paths.database)
    t.add_row("Database", f"{db} ({'present' if db.exists() else 'not created yet'})")
    for d in loaded.output_dirs:
        t.add_row("Directory", f"{d} ({'ok' if d.is_dir() else '[yellow]missing[/yellow]'})")
    console.print(t)


@app.command()
def doctor(ctx: typer.Context) -> None:
    """Check environment readiness. Exits 1 if any check FAILs."""
    loaded = _load(ctx)
    results = run_all_checks(loaded)
    t = Table(title="Environment readiness")
    t.add_column("Check", style="bold")
    t.add_column("Status")
    t.add_column("Detail")
    for r in results:
        t.add_row(r.name, f"[{STATUS_STYLE[r.status]}]{r.status.value}[/]", r.detail)
    console.print(t)
    log = get_logger("doctor")
    for r in results:
        log.info("check", extra={"check": r.name, "status": r.status.value, "detail": r.detail})
    counts = {s: sum(r.status is s for r in results) for s in Status}
    console.print(" ".join(f"[{STATUS_STYLE[s]}]{s.value}: {n}[/]" for s, n in counts.items()))
    if counts[Status.FAIL]:
        raise typer.Exit(code=1)


def _pending(stage: str, what: str) -> None:
    """Honest placeholder: the command is wired but its engine is not built yet."""
    console.print(f"[yellow]pending[/yellow] — {what} is implemented in {stage}. No results were produced.")


def _require_lab(loaded: LoadedConfig) -> None:
    if not loaded.config.lab.authorized:
        err_console.print(
            "[red]Refused:[/red] lab.authorized is false. Set it to true in configs/framework.yaml only inside "
            "an isolated, authorized Windows test VM."
        )
        raise typer.Exit(code=2)


PROFILES = {"baseline": None, "user": Layer.USER_MODE, "network": Layer.NETWORK, "os": Layer.OS_SERVICE}


@app.command()
def run(
    ctx: typer.Context,
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Scenario id, e.g. SC-001."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help=f"Profile: {', '.join(PROFILES)}."),
) -> None:
    """Execute a controlled scenario (or profile), persist the experiment record. [Stage 3]"""
    loaded = _load(ctx)
    if bool(scenario) == bool(profile):
        err_console.print("[red]Provide exactly one of[/red] --scenario or --profile.")
        raise typer.Exit(code=2)
    if scenario:
        try:
            targets = [get_scenario(scenario.upper())]
        except ScenarioError:
            err_console.print(f"[red]Unknown scenario:[/red] {scenario}. Try 'framework scenarios list'.")
            raise typer.Exit(code=2)
        profile_name = scenario.upper()
    else:
        if profile not in PROFILES:
            err_console.print(f"[red]Unknown profile:[/red] {profile}. Choose: {', '.join(PROFILES)}.")
            raise typer.Exit(code=2)
        targets = list_scenarios(PROFILES[profile])
        profile_name = profile
    _require_lab(loaded)
    _execute_experiment(loaded, profile_name, targets)


def _execute_experiment(loaded: LoadedConfig, profile_name: str, targets: list) -> None:
    from endpoint_framework.scenarios.executor import execute
    from endpoint_framework.storage import Database, ExperimentState, ScenarioRun
    from endpoint_framework.storage.models import TelemetryStatus
    from datetime import datetime, timezone

    workspace = loaded.resolve(loaded.config.paths.experiments_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    db = Database(loaded.resolve(loaded.config.paths.database))
    exp = None
    try:
        exp = db.create_experiment(profile_name, seed=loaded.config.seed, host=platform.node())
        db.set_state(exp.id, ExperimentState.VALIDATED)
        db.set_state(exp.id, ExperimentState.RUNNING)
        console.print(f"Experiment [bold]{exp.id}[/bold] — profile [bold]{profile_name}[/bold], {len(targets)} scenario(s)")

        t = Table(title=f"{exp.id} results")
        t.add_column("Scenario", style="bold")
        t.add_column("Status")
        t.add_column("Duration")
        t.add_column("Detail")
        style = {"completed": "green", "failed": "red", "skipped": "yellow"}
        for sc in targets:
            res, dur = execute(sc, workspace)
            db.add_scenario_run(ScenarioRun(
                experiment_id=exp.id, scenario_id=sc.id, status=res.status,
                ended_at=datetime.now(timezone.utc).isoformat(), duration_s=round(dur, 4),
                detail=res.detail, telemetry_status=TelemetryStatus.PENDING.value,
            ))
            t.add_row(sc.id, f"[{style[res.status]}]{res.status}[/]", f"{dur:.3f}s", res.detail[:60])
        console.print(t)

        db.set_state(exp.id, ExperimentState.COLLECTING)  # telemetry collection: Stage 4, not wired on this host
        db.set_state(exp.id, ExperimentState.COMPLETED)
        console.print(f"[green]Stored[/green] {exp.id} (state COMPLETED). Telemetry correlation is pending Stage 4.")
    except Exception:
        if exp is not None:
            db.set_state(exp.id, ExperimentState.FAILED)
        raise
    finally:
        db.close()


@app.command()
def train(
    ctx: typer.Context,
    episodes: int = typer.Option(100, "--episodes", "-e", min=1, help="Training episodes."),
) -> None:
    """Train the DQN scenario-selection agent against SIMULATED feedback. [Stage 5]"""
    loaded = _load(ctx)
    import json

    from endpoint_framework.rl.agent import DQNAgent
    from endpoint_framework.rl.environment import ScenarioSelectionEnv
    from endpoint_framework.rl.trainer import train as train_loop

    seed = loaded.config.seed
    scenarios = list_scenarios()
    layer_ids = [list(Layer).index(s.layer) for s in scenarios]
    env = ScenarioSelectionEnv(layer_ids, seed=seed)
    agent = DQNAgent(env.state_dim, env.action_dim, seed=seed)

    console.print(f"Training DQN on [bold]{len(scenarios)}[/bold] scenarios for [bold]{episodes}[/bold] episodes "
                  f"(seed {seed}, [yellow]simulated feedback[/yellow])...")
    with console.status("training"):
        res = train_loop(env, agent, episodes=episodes, seed=seed)

    models = loaded.resolve(loaded.config.paths.outputs_dir) / "models"
    agent.save(models / "dqn.pt")
    metrics = {
        "episodes": res.episodes, "seed": res.seed, "simulated": res.simulated,
        "episode_returns": res.episode_returns, "losses": res.losses,
        "dqn_eval_mean": res.dqn_eval_mean, "random_eval_mean": res.random_eval_mean,
    }
    (models / "dqn_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    last10 = sum(res.episode_returns[-10:]) / min(10, len(res.episode_returns))
    t = Table(title="DQN training summary (simulated feedback)", show_header=False)
    t.add_column("", style="bold")
    t.add_column("")
    t.add_row("Episodes", str(res.episodes))
    t.add_row("Mean return (last 10)", f"{last10:.2f}")
    t.add_row("DQN greedy eval", f"{res.dqn_eval_mean:.2f}")
    t.add_row("Random baseline", f"{res.random_eval_mean:.2f}")
    verdict = "[green]DQN > random[/green]" if res.dqn_eval_mean > res.random_eval_mean else "[yellow]no gain yet[/yellow]"
    t.add_row("Verdict", verdict)
    t.add_row("Checkpoint", str(models / "dqn.pt"))
    console.print(t)


@app.command()
def evaluate(
    ctx: typer.Context,
    mode: str = typer.Option("adaptive", "--mode", "-m", help="Selection strategy: adaptive | random | fixed."),
) -> None:
    """Execute scenarios in an order chosen by a strategy, end-to-end. [Stage 6]"""
    loaded = _load(ctx)
    if mode not in {"adaptive", "random", "fixed"}:
        err_console.print("[red]--mode[/red] must be one of: adaptive, random, fixed.")
        raise typer.Exit(code=2)
    scenarios = list_scenarios()
    if mode == "fixed":
        ordered = scenarios
    elif mode == "random":
        import random as _random
        ordered = scenarios[:]
        _random.Random(loaded.config.seed).shuffle(ordered)
    else:  # adaptive: order comes from the trained DQN's greedy policy
        ckpt = loaded.resolve(loaded.config.paths.outputs_dir) / "models" / "dqn.pt"
        if not ckpt.is_file():
            err_console.print("[red]No DQN checkpoint[/red] — run 'framework train' before adaptive evaluation.")
            raise typer.Exit(code=2)
        ordered = _adaptive_order(loaded, scenarios, ckpt)
    _require_lab(loaded)
    console.print(f"Strategy [bold]{mode}[/bold] -> order: {', '.join(s.id for s in ordered)}")
    _execute_experiment(loaded, f"eval-{mode}", ordered)


def _adaptive_order(loaded: LoadedConfig, scenarios: list, ckpt) -> list:
    """Replay the trained DQN greedily on the simulated env to get a scenario order."""
    from endpoint_framework.rl.agent import DQNAgent
    from endpoint_framework.rl.environment import ScenarioSelectionEnv

    layer_ids = [list(Layer).index(s.layer) for s in scenarios]
    env = ScenarioSelectionEnv(layer_ids, seed=loaded.config.seed)
    agent = DQNAgent(env.state_dim, env.action_dim, seed=loaded.config.seed)
    agent.load(ckpt)
    state = env.reset()
    order: list = []
    done = False
    while not done:
        a = agent.act(state, epsilon=0.0)
        if scenarios[a] not in order:
            order.append(scenarios[a])
        state, _, done, _ = env.step(a)
    # append any the policy never selected, so every scenario still runs once
    order += [s for s in scenarios if s not in order]
    return order


@app.command()
def analyze(
    ctx: typer.Context,
    run_id: str = typer.Option(..., "--run", "-r", help="Experiment id, e.g. EXP-001."),
) -> None:
    """Run metrics, SHAP and K-means over stored experiments. [Stage 7]"""
    import json

    from endpoint_framework.analysis.clustering import cluster_experiments
    from endpoint_framework.analysis.metrics import compute_metrics
    from endpoint_framework.storage import Database

    loaded = _load(ctx)
    db = Database(loaded.resolve(loaded.config.paths.database))
    try:
        if db.get_experiment(run_id) is None:
            err_console.print(f"[red]Unknown experiment:[/red] {run_id}. Run one with 'framework run'.")
            raise typer.Exit(code=2)

        m = compute_metrics(db, run_id)
        t = Table(title=f"{run_id} metrics", show_header=False)
        t.add_column("", style="bold"); t.add_column("")
        t.add_row("Scenarios", str(m.total))
        t.add_row("Completed / failed / skipped", f"{m.completed} / {m.failed} / {m.skipped}")
        t.add_row("Completion rate", f"{m.completion_rate:.0%}")
        t.add_row("Telemetry observed", str(m.telemetry_observed))
        t.add_row("Mean duration", f"{m.mean_duration_s:.3f}s")
        t.add_row("Layer coverage", ", ".join(f"{k}:{v}" for k, v in m.layer_coverage.items()) or "none")
        console.print(t)

        analysis: dict = {"experiment_id": run_id, "metrics": m.__dict__}

        # SHAP over the trained DQN, if a checkpoint exists.
        models = loaded.resolve(loaded.config.paths.outputs_dir) / "models"
        ckpt = models / "dqn.pt"
        if ckpt.is_file():
            from endpoint_framework.analysis.explainability import explain_agent
            from endpoint_framework.rl.agent import DQNAgent

            scenarios = list_scenarios()
            agent = DQNAgent(len(scenarios), len(scenarios), seed=loaded.config.seed)
            agent.load(ckpt)
            attr = explain_agent(agent, [s.id for s in scenarios], seed=loaded.config.seed)
            top = sorted(attr.importances.items(), key=lambda kv: kv[1], reverse=True)[:5]
            console.print(f"\n[bold]SHAP feature importance[/bold] ({attr.method}, simulated):")
            for sid, v in top:
                console.print(f"  {sid}  {v:.4f}")
            analysis["shap"] = {"method": attr.method, "importances": attr.importances, "simulated": True}
        else:
            console.print("\n[yellow]No DQN checkpoint[/yellow] — run 'framework train' for SHAP attribution.")

        cl = cluster_experiments(db)
        if cl.meaningful:
            sil = f"{cl.silhouette:.3f}" if cl.silhouette is not None else "n/a"
            console.print(f"\n[bold]K-means[/bold]: k={cl.k}, silhouette={sil}")
            analysis["clustering"] = {"k": cl.k, "labels": cl.labels, "silhouette": cl.silhouette,
                                      "experiment_ids": cl.experiment_ids}
        else:
            console.print(f"\n[yellow]K-means not meaningful[/yellow]: {cl.reason}")
            analysis["clustering"] = {"meaningful": False, "reason": cl.reason}

        reports = loaded.resolve(loaded.config.paths.outputs_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        out = reports / f"{run_id}_analysis.json"
        out.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
        console.print(f"\n[green]Wrote[/green] {out}")
    finally:
        db.close()


@app.command()
def report(
    ctx: typer.Context,
    run_id: str = typer.Option(..., "--run", "-r", help="Experiment id, e.g. EXP-001."),
) -> None:
    """Generate CSV/JSON exports and research figures for an experiment. [Stage 8]"""
    from endpoint_framework.reporting.generator import export_experiment
    from endpoint_framework.storage import Database

    loaded = _load(ctx)
    db = Database(loaded.resolve(loaded.config.paths.database))
    try:
        if db.get_experiment(run_id) is None:
            err_console.print(f"[red]Unknown experiment:[/red] {run_id}.")
            raise typer.Exit(code=2)
        outputs = loaded.resolve(loaded.config.paths.outputs_dir)
        files = export_experiment(db, run_id, outputs / "reports", outputs / "models")
        t = Table(title=f"{run_id} report artifacts")
        t.add_column("Artifact", style="bold"); t.add_column("Path")
        for name, path in files.items():
            t.add_row(name, str(path))
        console.print(t)
    finally:
        db.close()


scenarios_app = typer.Typer(help="Browse the non-destructive cross-layer scenario catalog.", no_args_is_help=True)
app.add_typer(scenarios_app, name="scenarios")


@scenarios_app.command("list")
def scenarios_list(
    layer: Optional[Layer] = typer.Option(None, "--layer", "-l", help="Filter by Windows execution layer."),
) -> None:
    """List scenarios in the catalog."""
    items = list_scenarios(layer)
    t = Table(title=f"Scenario catalog ({len(items)})")
    t.add_column("ID", style="bold")
    t.add_column("Layer")
    t.add_column("Name")
    t.add_column("ATT&CK")
    for s in items:
        t.add_row(s.id, s.layer.value, s.name, s.mitre_attack or "—")
    console.print(t)


@scenarios_app.command("info")
def scenarios_info(scenario_id: str = typer.Argument(..., help="Scenario id, e.g. SC-001.")) -> None:
    """Show the full definition of one scenario."""
    try:
        s = get_scenario(scenario_id.upper())
    except ScenarioError:
        err_console.print(f"[red]Unknown scenario:[/red] {scenario_id}. Try 'framework scenarios list'.")
        raise typer.Exit(code=2)
    t = Table(show_header=False, title=f"{s.id} — {s.name}")
    t.add_column("Field", style="bold")
    t.add_column("Value")
    t.add_row("Layer", s.layer.value)
    t.add_row("Description", s.description)
    t.add_row("ATT&CK", s.mitre_attack or "—")
    t.add_row("Destructive", "[green]no[/green]" if not s.destructive else "[red]yes[/red]")
    t.add_row("Prerequisites", "\n".join(s.prerequisites) or "none")
    t.add_row("Expected events", "\n".join(f"{e.source} {e.event_id or ''}: {e.description}".strip() for e in s.expected_events) or "none defined")
    t.add_row("Timeout", f"{s.timeout_seconds}s")
    t.add_row("Success criteria", s.success_criteria)
    t.add_row("Cleanup", s.cleanup)
    console.print(t)
    console.print("[dim]Execution engine arrives in Stage 3; this is the definition only.[/dim]")


@app.command()
def menu() -> None:
    """Show the branded banner and the module menu."""
    render_banner(console)
    render_menu(console)


@app.command()
def shell(ctx: typer.Context) -> None:
    """Interactive console: type the commands from the menu at the prompt."""
    render_banner(console)
    render_menu(console)
    command = typer.main.get_command(app)
    while True:
        try:
            line = console.input("[bold red]kavach[/] [dim]>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        if line == "clear":
            console.clear()
            continue
        if line in {"menu", "help", "?"}:
            render_menu(console)
            continue
        try:
            command.main(args=shlex.split(line), prog_name="framework", standalone_mode=False)
        except SystemExit:
            pass  # a subcommand's typer.Exit; keep the shell alive
        except click.ClickException as e:
            e.show()
        except Exception as e:  # noqa: BLE001 - never let one bad command kill the console
            err_console.print(f"[red]error:[/red] {e}")


if __name__ == "__main__":
    app()
