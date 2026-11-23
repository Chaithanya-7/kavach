import sys

import pytest

from endpoint_framework.scenarios import get_scenario
from endpoint_framework.rl.rewards import feedback_reward, simulated_coverage_reward
from endpoint_framework.telemetry.feedback import ScenarioFeedback, _outcome, process_feedback


def test_outcome_matrix():
    assert _outcome(True, True, True) == "expected_detection"
    assert _outcome(True, False, True) == "missed_detection"
    assert _outcome(False, True, True) == "unexpected_alert"
    assert _outcome(False, False, True) == "no_alert_as_expected"
    assert _outcome(False, False, False) == "inconclusive"  # telemetry unknown -> never guess


@pytest.mark.skipif(sys.platform == "win32", reason="checks the off-Windows inconclusive path")
def test_process_feedback_off_windows_is_honest():
    fb = process_feedback("EXP-001", get_scenario("SC-001"), "completed")
    assert isinstance(fb, ScenarioFeedback)
    assert fb.execution_status == "completed"
    assert fb.telemetry_status == "source_unavailable"
    assert fb.alert_status == "source_unavailable"
    assert fb.detection_outcome == "inconclusive"   # Defender unreadable off Windows
    assert fb.confidence == "inconclusive"
    assert fb.expected_alert is False               # benign scenario


def test_simulated_reward():
    assert simulated_coverage_reward(True, True) == 1.5
    assert simulated_coverage_reward(True, False) == 1.0
    assert simulated_coverage_reward(False, False) == -1.0


def test_feedback_reward_ranks_information():
    def fb(exec_status, tel):
        return ScenarioFeedback("E", "SC", exec_status, tel, tel, 0, False, "x")
    assert feedback_reward(fb("completed", "observed")) == 1.0
    assert feedback_reward(fb("completed", "not_observed")) == 0.0
    assert feedback_reward(fb("completed", "source_unavailable")) == -0.25
    assert feedback_reward(fb("failed", "observed")) == -1.0
