"""SHAP feature attribution for the DQN policy.

GradientExplainer suits a differentiable torch Q-network. Features are the state
dimensions (which scenarios have been executed); attribution shows which of
those most influence the agent's Q-values. Attribution indicates influence on
the model's output, not a causal claim about defences.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from endpoint_framework.rl.agent import DQNAgent


@dataclass
class Attribution:
    method: str
    importances: dict[str, float]  # scenario_id -> mean |SHAP value|
    simulated: bool = True


def explain_agent(
    agent: DQNAgent,
    scenario_ids: list[str],
    n_background: int = 50,
    n_explain: int = 30,
    seed: int = 0,
) -> Attribution:
    import shap

    f = len(scenario_ids)
    rng = np.random.default_rng(seed)
    background = rng.integers(0, 2, size=(n_background, f)).astype(np.float32)
    samples = rng.integers(0, 2, size=(n_explain, f)).astype(np.float32)

    agent.policy.eval()
    explainer = shap.GradientExplainer(agent.policy, torch.from_numpy(background))
    shap_values = explainer.shap_values(torch.from_numpy(samples))

    # Normalise to mean |value| per feature across samples and action outputs.
    if isinstance(shap_values, list):
        arr = np.stack([np.abs(a) for a in shap_values])  # (actions, samples, features)
        imp = arr.mean(axis=(0, 1))
    else:
        arr = np.abs(np.asarray(shap_values))
        feat_axis = max((ax for ax in range(arr.ndim) if arr.shape[ax] == f), default=1)
        imp = arr.mean(axis=tuple(ax for ax in range(arr.ndim) if ax != feat_axis))
    imp = np.asarray(imp, dtype=float).reshape(-1)[:f]
    return Attribution(
        method="shap.GradientExplainer",
        importances={sid: float(v) for sid, v in zip(scenario_ids, imp)},
    )
