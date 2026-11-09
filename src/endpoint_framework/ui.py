"""Branded console UI: banner + module menu (cosmetic layer over the real commands)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from endpoint_framework import __version__

BANNER = r"""
██╗  ██╗ █████╗ ██╗   ██╗ █████╗  ██████╗██╗  ██╗
██║ ██╔╝██╔══██╗██║   ██║██╔══██╗██╔════╝██║  ██║
█████╔╝ ███████║██║   ██║███████║██║     ███████║
██╔═██╗ ██╔══██║╚██╗ ██╔╝██╔══██║██║     ██╔══██║
██║  ██╗██║  ██║ ╚████╔╝ ██║  ██║╚██████╗██║  ██║
╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
"""

SUBTITLE = "Adaptive Cross-Layer Endpoint Defense Evaluation Framework"

# Each row: (command to type, description). Grouped like a module console, but every
# entry maps to a real, non-destructive command — no exploit or anti-forensics modules.
MENU: dict[str, list[tuple[str, str]]] = {
    "SCENARIO MODULES": [
        ("scenarios list", "List the cross-layer scenario catalog"),
        ("scenarios info SC-001", "Show one scenario's full definition"),
        ("run --scenario SC-001", "Execute a controlled scenario, lab-gated [Stage 3]"),
    ],
    "ANALYSIS MODULES": [
        ("train --episodes 100", "Train the DQN scenario selector [Stage 5]"),
        ("evaluate --mode adaptive", "Evaluate a selection strategy [Stage 6]"),
        ("analyze --run EXP-001", "Metrics + SHAP + K-means [Stage 7]"),
        ("report --run EXP-001", "CSV/JSON exports + research figures [Stage 8]"),
    ],
    "SYSTEM MODULES": [
        ("doctor", "Environment readiness checks"),
        ("status", "Active configuration and workspace"),
        ("init", "Create config + workspace directories"),
    ],
    "CORE": [
        ("menu", "Show this menu"),
        ("clear", "Clear the screen"),
        ("exit", "Leave the console"),
    ],
}


def render_banner(console: Console) -> None:
    console.print(Text(BANNER, style="bold red"))
    console.print(Text(f"  {SUBTITLE}   v{__version__}", style="bold"))
    console.print(Text("  [!] For authorized, non-destructive lab use only.", style="yellow"))
    console.print()


def render_menu(console: Console) -> None:
    for group, rows in MENU.items():
        t = Table(show_header=False, box=None, padding=(0, 2, 0, 1))
        t.add_column("cmd", style="bold green", no_wrap=True)
        t.add_column("desc")
        for cmd, desc in rows:
            t.add_row(cmd, desc)
        console.print(Panel(t, title=f"[bold]{group}[/bold]", title_align="left", border_style="red"))
