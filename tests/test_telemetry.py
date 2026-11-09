import sys

import pytest

from endpoint_framework.telemetry.collector import CHANNELS, collect


def test_unknown_source():
    assert collect("Nope").status == "collection_failure"


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows path")
def test_sources_unavailable_off_windows():
    for name in CHANNELS:
        r = collect(name)
        assert r.status == "source_unavailable" and "Windows" in r.detail and r.count == 0


def test_parse_real_sysmon_xml(monkeypatch):
    sample = (
        '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
        '<System><Provider Name="Microsoft-Windows-Sysmon"/><EventID>1</EventID>'
        '<TimeCreated SystemTime="2026-01-01T00:00:00Z"/></System>'
        '<EventData><Data Name="ProcessId">4321</Data>'
        '<Data Name="Image">C:\\Windows\\System32\\cmd.exe</Data></EventData></Event>'
    )
    class P:
        returncode, stdout, stderr = 0, sample, ""
    import endpoint_framework.telemetry.collector as c
    monkeypatch.setattr(c, "_IS_WIN", True)
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **k: P())
    r = collect("Sysmon")
    assert r.status == "observed" and r.count == 1
    e = r.events[0]
    assert e.event_id == 1 and e.pid == 4321 and e.image.endswith("cmd.exe")
