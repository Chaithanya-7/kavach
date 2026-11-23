"""Reward functions.

Two counterparts are provided and kept distinct:

* ``simulated_coverage_reward`` mirrors the reward used by the simulated training
  environment (coverage / information gain), used to train the agent offline.
* ``feedback_reward`` computes a reward from a real EDR feedback record, so the
  agent can later be driven by observed experimental feedback rather than
  simulated feedback. It rewards gaining telemetry information and penalizes
  failed or uninformative experiments; it does NOT reward evasion.
"""

from __future__ import annotations

from endpoint_framework.telemetry.feedback import ScenarioFeedback


def simulated_coverage_reward(new_scenario: bool, new_layer: bool) -> float:
    """Reward used by the simulated environment: +1 for a new scenario, +0.5 for a new layer."""
    if not new_scenario:
        return -1.0  # redundant experiment
    return 1.0 + (0.5 if new_layer else 0.0)


def feedback_reward(fb: ScenarioFeedback) -> float:
    """Reward from a real feedback record: information gained about defensive coverage."""
    if fb.execution_status != "completed":
        return -1.0  # the experiment did not run; no information gained
    if fb.telemetry_status == "observed":
        return 1.0   # telemetry was captured: informative
    if fb.telemetry_status == "not_observed":
        return 0.0   # ran, source available, nothing seen: weakly informative
    return -0.25     # source unavailable / collection failure: little information
