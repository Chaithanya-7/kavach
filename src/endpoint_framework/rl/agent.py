"""DQN agent: epsilon-greedy action, Bellman update, target network, checkpoints."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn

from endpoint_framework.rl.dqn import QNetwork
from endpoint_framework.rl.replay_buffer import ReplayBuffer


class DQNAgent:
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        seed: int = 0,
        lr: float = 1e-3,
        gamma: float = 0.95,
        hidden: int = 64,
    ) -> None:
        torch.manual_seed(seed)
        self.action_dim = action_dim
        self.gamma = gamma
        self.policy = QNetwork(state_dim, action_dim, hidden)
        self.target = QNetwork(state_dim, action_dim, hidden)
        self.target.load_state_dict(self.policy.state_dict())
        self.target.eval()
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=lr)
        self._rng = np.random.default_rng(seed)

    def act(self, state: np.ndarray, epsilon: float = 0.0) -> int:
        if self._rng.random() < epsilon:
            return int(self._rng.integers(self.action_dim))
        with torch.no_grad():
            q = self.policy(torch.as_tensor(state, dtype=torch.float32).unsqueeze(0))
        return int(q.argmax(dim=1).item())

    def learn(self, buffer: ReplayBuffer, batch_size: int) -> float:
        if len(buffer) < batch_size:
            return 0.0
        s, a, r, s2, done = buffer.sample(batch_size)
        q = self.policy(s).gather(1, a)
        with torch.no_grad():
            q_next = self.target(s2).max(dim=1, keepdim=True).values
            target = r + self.gamma * q_next * (1.0 - done)
        loss = nn.functional.mse_loss(q, target)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        return float(loss.item())

    def sync_target(self) -> None:
        self.target.load_state_dict(self.policy.state_dict())

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.policy.state_dict(), path)

    def load(self, path: Path) -> None:
        state = torch.load(path, map_location="cpu")
        self.policy.load_state_dict(state)
        self.target.load_state_dict(state)
