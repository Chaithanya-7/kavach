import numpy as np

from endpoint_framework.rl.agent import DQNAgent
from endpoint_framework.rl.environment import ScenarioSelectionEnv
from endpoint_framework.rl.trainer import random_baseline, train

LAYERS = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3]  # mirrors the 10-scenario catalog's layers


def _env(seed=0):
    return ScenarioSelectionEnv(LAYERS, seed=seed)


def test_env_penalises_repeats_and_ends():
    env = _env()
    env.reset()
    _, r1, _, _ = env.step(0)
    _, r2, _, _ = env.step(0)  # repeat
    assert r1 > 0 and r2 < 0


def test_env_terminates():
    env = _env()
    env.reset()
    steps = 0
    done = False
    while not done and steps < 100:
        _, _, done, _ = env.step(steps % env.action_dim)
        steps += 1
    assert done


def test_dqn_learns_to_beat_random():
    env = _env(seed=1)
    agent = DQNAgent(env.state_dim, env.action_dim, seed=1)
    res = train(env, agent, episodes=120, seed=1)
    # a trained greedy policy should collect more reward than uniform-random selection
    assert res.dqn_eval_mean > res.random_eval_mean
    assert res.simulated is True


def test_checkpoint_roundtrip(tmp_path):
    env = _env()
    a1 = DQNAgent(env.state_dim, env.action_dim, seed=3)
    train(env, a1, episodes=20, seed=3)
    p = tmp_path / "dqn.pt"
    a1.save(p)
    a2 = DQNAgent(env.state_dim, env.action_dim, seed=99)
    a2.load(p)
    s = env.reset()
    assert a1.act(s) == a2.act(s)  # loaded policy reproduces actions


def test_reproducible_seed():
    r1 = train(_env(seed=5), DQNAgent(10, 10, seed=5), episodes=30, seed=5)
    r2 = train(_env(seed=5), DQNAgent(10, 10, seed=5), episodes=30, seed=5)
    assert r1.episode_returns == r2.episode_returns
