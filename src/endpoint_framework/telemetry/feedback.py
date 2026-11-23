"""EDR feedback processing (Module 5).

Turns a scenario's execution plus its collected telemetry into a normalized
feedback record, keeping *expected* detection outcomes separate from *observed*
behavior. This never fabricates alerts: a benign scenario is not expected to
alert, and an unavailable source is reported as such, not as a non-detection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from endpoint_framework.scenarios.base import Scenario
from endpoint_framework.storage.models import TelemetryStatus
from endpoint_framework.telemetry.collector import collect
from endpoint_framework.telemetry.correlator import telemetry_for


@dataclass
class ScenarioFeedback:
    experiment_id: str
    scenario_id: str
    execution_status: str          # completed | failed | skipped
    telemetry_status: str          # observed | not_observed | source_unavailable | collection_failure
    alert_status: str              # observed | not_observed | source_unavailable | collection_failure
    event_count: int
    expected_alert: bool           # defined by the scenario, independent of what was observed
    detection_outcome: str         # expected-vs-observed label (see _outcome)
    source: str = "Windows Event Logs / Microsoft Defender"
    confidence: str = "observed"   # observed | inconclusive

    def to_dict(self) -> dict:
        return asdict(self)


def _outcome(expected_alert: bool, alert_observed: bool, alert_known: bool) -> str:
    """Compare expected detection to observed, honestly handling unknown telemetry."""
    if not alert_known:
        return "inconclusive"  # we could not read the alert source; do not guess
    if expected_alert and alert_observed:
        return "expected_detection"       # alert expected and seen
    if expected_alert and not alert_observed:
        return "missed_detection"         # alert expected but not seen (coverage gap)
    if not expected_alert and alert_observed:
        return "unexpected_alert"         # benign activity raised an alert (notable)
    return "no_alert_as_expected"         # benign activity, no alert: the normal case


def process_feedback(
    experiment_id: str, scenario: Scenario, execution_status: str, collected: dict | None = None
) -> ScenarioFeedback:
    tel_status, event_count, _ = telemetry_for(scenario, collected=collected)
    defender = collected["Defender"] if collected and "Defender" in collected else collect("Defender")
    alert_known = defender.status in (TelemetryStatus.OBSERVED.value, TelemetryStatus.NOT_OBSERVED.value)
    alert_observed = defender.status == TelemetryStatus.OBSERVED.value and defender.count > 0
    confidence = "observed" if tel_status == TelemetryStatus.OBSERVED.value else "inconclusive"
    return ScenarioFeedback(
        experiment_id=experiment_id,
        scenario_id=scenario.id,
        execution_status=execution_status,
        telemetry_status=tel_status,
        alert_status=defender.status,
        event_count=event_count,
        expected_alert=scenario.expected_alert,
        detection_outcome=_outcome(scenario.expected_alert, alert_observed, alert_known),
        confidence=confidence,
    )
