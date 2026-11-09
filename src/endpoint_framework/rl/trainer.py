"""Training loop and baselines for the DQN scenario selector (simulated feedback)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from endpoint_framework.rl.agent import DQNAgent
from endpoint_framework.rl.environment import ScenarioSelectionEnv
from endpoint_framework.rl.replay_buffer import ReplayBuffer


@dataclass
class TrainResult:
    episode_returns: list[float] = field(default_factory=list)
    losses: list[float] = field(default_factory=list)
    dqn_eval_mean: float = 0.0
    random_eval_mean: float = 0.0
    episodes: int = 0
    seed: int = 0
    simulated: bool = True  # feedback is synthetic; recorded so reports never overstate it


def _epsilon(ep: int, episodes: int, start: float = 1.0, end: float = 0.05) -> float:
    frac = min(1.0, ep / max(1, int(episodes * 0.8)))
    return start + frac * (end - start)


def train(
    env: ScenarioSelectionEnv,
    agent: DQNAgent,
    episodes: int,
    seed: int = 0,
    batch_size: int = 32,
    buffer_capacity: int = 5000,
    target_sync: int = 10,
) -> TrainResult:
    buffer = ReplayBuffer(buffer_capacity, seed=seed)
    result = TrainResult(episodes=episodes, seed=seed)
    for ep in range(episodes):
        state = env.reset()
        done = False
        total = 0.0
        eps = _epsilon(ep, episodes)
        while not done:
            action = agent.act(state, epsilon=eps)
            nxt, reward, done, _ = env.step(action)
            buffer.push(state, action, reward, nxt, done)
            loss = agent.learn(buffer, batch_size)
            state = nxt
            total += reward
            if loss:
                result.losses.append(loss)
        result.episode_returns.append(total)
        if ep % target_sync == 0:
            agent.sync_target()
    result.dqn_eval_mean = evaluate(env, agent, episodes=20)
    result.random_eval_mean = random_baseline(env, episodes=20, seed=seed)
    return result


def evaluate(env: ScenarioSelectionEnv, agent: DQNAgent, episodes: int = 20) -> float:
    returns = []
    for _ in range(episodes):
        state = env.reset()
        done = False
        total = 0.0
        while not done:
            state, reward, done, _ = env.step(agent.act(state, epsilon=0.0))
            total += reward
        returns.append(total)
    return float(np.mean(returns))


def random_baseline(env: ScenarioSelectionEnv, episodes: int = 20, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    returns = []
    for _ in range(episodes):
        env.reset()
        done = False
        total = 0.0
        while not done:
            _, reward, done, _ = env.step(int(rng.integers(env.action_dim)))
            total += reward
        returns.append(total)
    return float(np.mean(returns))
