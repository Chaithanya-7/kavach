"""Windows event-log telemetry collector.

Reads events from Sysmon / Security / Defender channels via wevtutil and
normalizes them. Off Windows (or when a channel is absent) it returns an
honest status — never a fabricated "no detection" result.

Status meanings (kept distinct on purpose):
  observed           - events were read
  not_observed       - channel available, query returned nothing in the window
  source_unavailable - not Windows, or the channel does not exist / access denied
  collection_failure - the query itself errored
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

_IS_WIN = sys.platform == "win32"

CHANNELS: dict[str, str] = {
    "Sysmon": "Microsoft-Windows-Sysmon/Operational",
    "Security": "Security",
    "Defender": "Microsoft-Windows-Windows Defender/Operational",
}
_NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}


@dataclass
class TelemetryEvent:
    source: str
    event_id: int | None
    time_created: str
    provider: str
    pid: int | None
    image: str | None
    raw: str


@dataclass
class CollectionResult:
    source: str
    status: str
    events: list[TelemetryEvent] = field(default_factory=list)
    detail: str = ""

    @property
    def count(self) -> int:
        return len(self.events)


def _parse_event(xml_text: str, source: str) -> TelemetryEvent:
    root = ET.fromstring(xml_text)
    sys_el = root.find("e:System", _NS)
    def _txt(tag: str) -> str | None:
        el = sys_el.find(f"e:{tag}", _NS) if sys_el is not None else None
        return el.text if el is not None else None
    eid = _txt("EventID")
    provider_el = sys_el.find("e:Provider", _NS) if sys_el is not None else None
    provider = provider_el.get("Name", "") if provider_el is not None else ""
    tc_el = sys_el.find("e:TimeCreated", _NS) if sys_el is not None else None
    time_created = tc_el.get("SystemTime", "") if tc_el is not None else ""
    data = {d.get("Name"): d.text for d in root.iter() if d.tag.endswith("}Data")}
    pid = data.get("ProcessId") or _txt("Execution")
    image = data.get("Image")
    return TelemetryEvent(
        source=source,
        event_id=int(eid) if eid and eid.isdigit() else None,
        time_created=time_created,
        provider=provider,
        pid=int(pid) if pid and str(pid).isdigit() else None,
        image=image,
        raw=xml_text,
    )


def collect(source: str, max_events: int = 50, timeout: int = 20) -> CollectionResult:
    """Collect recent events from one named channel."""
    channel = CHANNELS.get(source)
    if channel is None:
        return CollectionResult(source, "collection_failure", detail=f"unknown source {source!r}")
    if not _IS_WIN:
        return CollectionResult(source, "source_unavailable", detail="telemetry collection requires Windows")
    try:
        proc = subprocess.run(
            ["wevtutil", "qe", channel, f"/c:{max_events}", "/rd:true", "/f:xml"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return CollectionResult(source, "collection_failure", detail=str(e))
    if proc.returncode != 0:
        return CollectionResult(source, "source_unavailable",
                                detail=(proc.stderr or proc.stdout).strip()[:200])
    chunks = [c for c in proc.stdout.split("</Event>") if "<Event" in c]
    events: list[TelemetryEvent] = []
    for c in chunks:
        try:
            events.append(_parse_event(c + "</Event>", source))
        except ET.ParseError:
            continue
    status = "observed" if events else "not_observed"
    return CollectionResult(source, status, events=events, detail=f"{len(events)} event(s)")
