"""Simulated scenario-selection environment for DQN training.

The agent repeatedly picks a scenario; the goal it is rewarded for is *coverage
and information gain* — executing each distinct scenario and covering each
Windows layer efficiently — never evading or disabling anything.

SIMULATED: feedback here is synthetic and seeded, used only to train/unit-test
the agent before it is connected to real experiment feedback (Stage 6).
"""

from __future__ import annotations

import numpy as np


class ScenarioSelectionEnv:
    def __init__(self, layer_ids: list[int], max_steps: int | None = None, seed: int = 0) -> None:
        self.layers = np.asarray(layer_ids, dtype=np.int64)
        self.n = len(layer_ids)
        self.max_steps = max_steps if max_steps is not None else 2 * self.n
        self.rng = np.random.default_rng(seed)
        self.reset()

    @property
    def state_dim(self) -> int:
        return self.n

    @property
    def action_dim(self) -> int:
        return self.n

    def reset(self) -> np.ndarray:
        self.executed = np.zeros(self.n, dtype=np.float32)
        self.covered_layers: set[int] = set()
        self.steps = 0
        return self._state()

    def _state(self) -> np.ndarray:
        return self.executed.copy()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict]:
        self.steps += 1
        if self.executed[action]:
            reward = -1.0  # redundant experiment: penalised
        else:
            self.executed[action] = 1.0
            reward = 1.0  # new information from a not-yet-run scenario
            layer = int(self.layers[action])
            if layer not in self.covered_layers:
                self.covered_layers.add(layer)
                reward += 0.5  # bonus for covering a new Windows layer
        done = bool(self.executed.all()) or self.steps >= self.max_steps
        return self._state(), reward, done, {"coverage": float(self.executed.mean())}
