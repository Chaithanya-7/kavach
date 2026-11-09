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
