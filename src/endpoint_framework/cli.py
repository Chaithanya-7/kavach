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


if __name__ == "__main__":
    app()
