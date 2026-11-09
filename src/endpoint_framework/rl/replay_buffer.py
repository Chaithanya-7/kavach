"""Fixed-size experience replay buffer."""

from __future__ import annotations

import random
from collections import deque

import numpy as np
import torch


class ReplayBuffer:
    def __init__(self, capacity: int, seed: int = 0) -> None:
        self.buf: deque = deque(maxlen=capacity)
        self._rng = random.Random(seed)

    def __len__(self) -> int:
        return len(self.buf)

    def push(self, s: np.ndarray, a: int, r: float, s2: np.ndarray, done: bool) -> None:
        self.buf.append((s, a, r, s2, done))

    def sample(self, batch_size: int) -> tuple[torch.Tensor, ...]:
        batch = self._rng.sample(self.buf, batch_size)
        s, a, r, s2, done = zip(*batch)
        return (
            torch.as_tensor(np.array(s), dtype=torch.float32),
            torch.as_tensor(a, dtype=torch.int64).unsqueeze(1),
            torch.as_tensor(r, dtype=torch.float32).unsqueeze(1),
            torch.as_tensor(np.array(s2), dtype=torch.float32),
            torch.as_tensor(done, dtype=torch.float32).unsqueeze(1),
        )
