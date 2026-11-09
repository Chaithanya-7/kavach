"""Research figures from stored data (matplotlib, headless Agg backend)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display in a CLI/CI environment
import matplotlib.pyplot as plt  # noqa: E402


def _rolling(x: list[float], w: int = 10) -> list[float]:
    if len(x) < w:
        return x
    out = []
    for i in range(len(x)):
        lo = max(0, i - w + 1)
        out.append(sum(x[lo : i + 1]) / (i - lo + 1))
    return out


def training_curve(metrics_json: Path, out_png: Path) -> Path:
    """DQN reward-convergence curve from train()'s metrics file."""
    data = json.loads(metrics_json.read_text(encoding="utf-8"))
    returns = data["episode_returns"]
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(returns, alpha=0.35, label="episode return")
    ax.plot(_rolling(returns), color="C1", label="10-episode mean")
    ax.axhline(data["random_eval_mean"], color="C3", ls="--", label="random baseline")
    ax.set_xlabel("episode")
    ax.set_ylabel("return")
    ax.set_title("DQN training (simulated feedback)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


def benchmark_bar(steps_by_mode: dict[str, int | None], out_png: Path) -> Path:
    """Steps-to-full-coverage per strategy (lower is better); 'never' shown as 0-height hatched."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    modes = list(steps_by_mode)
    vals = [steps_by_mode[m] if steps_by_mode[m] is not None else 0 for m in modes]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(modes, vals, color=["C0", "C1", "C2"])
    for b, m in zip(bars, modes):
        if steps_by_mode[m] is None:
            b.set_hatch("//")
    ax.set_ylabel("scenarios until all layers covered")
    ax.set_title("Strategy benchmark (lower is better)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


def coverage_bar(layer_coverage: dict[str, int], out_png: Path) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    layers = list(layer_coverage) or ["(none)"]
    counts = [layer_coverage.get(k, 0) for k in layers]
    ax.bar(layers, counts, color="C0")
    ax.set_ylabel("completed scenarios")
    ax.set_title("Scenario coverage by Windows layer")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png
