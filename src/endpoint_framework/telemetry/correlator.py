"""Associate a scenario's expected telemetry sources with a collection result.

Honest and coarse: it reports whether each source the scenario expects was
available and produced events in the recent window. It does NOT claim that those
events were caused by this scenario — precise per-scenario correlation (by pid /
time window) is the documented upgrade once validated on a real Windows host.
"""

from __future__ import annotations

from endpoint_framework.scenarios.base import Scenario
from endpoint_framework.storage.models import TelemetryStatus
from endpoint_framework.telemetry.collector import collect

# source-availability precedence, best to worst
_ORDER = [
    TelemetryStatus.OBSERVED,
    TelemetryStatus.NOT_OBSERVED,
    TelemetryStatus.SOURCE_UNAVAILABLE,
    TelemetryStatus.COLLECTION_FAILURE,
]


def telemetry_for(scenario: Scenario, max_events: int = 50) -> tuple[str, int, str]:
    """Return (telemetry_status, channel_event_count, note) for a scenario's sources."""
    sources = sorted({e.source for e in scenario.expected_events})
    if not sources:
        return TelemetryStatus.NOT_OBSERVED.value, 0, "scenario defines no expected telemetry sources"

    results = [collect(src, max_events=max_events) for src in sources]
    by_status = {r.status for r in results}
    # best available status across the scenario's sources
    status = next((s.value for s in _ORDER if s.value in by_status), TelemetryStatus.COLLECTION_FAILURE.value)
    # shortcut: channel-level count, not per-scenario filtered; upgrade with pid/time correlation on Windows
    total = sum(r.count for r in results)
    note = "; ".join(f"{r.source}:{r.status}({r.count})" for r in results)
    return status, total, note
