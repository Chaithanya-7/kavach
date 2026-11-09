"""Command-line interface (Typer + Rich)."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Optional

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


if __name__ == "__main__":
    app()
