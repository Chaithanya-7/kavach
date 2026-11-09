"""Scenario definition schema.

A scenario is *authorized, non-destructive* Windows activity run to observe how
telemetry and security products react. Definitions carry only metadata here;
Stage 3 adds the execute/cleanup implementations behind this same interface.

Explicitly out of scope (by project policy): stealth payloads, EDR-disabling,
driver exploitation, syscall-level evasion, or any technique whose goal is to
avoid detection. Scenarios describe ordinary system behavior, honestly labeled.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Layer(str, Enum):
    USER_MODE = "user_mode"
    OS_SERVICE = "os_service"
    KERNEL_OBSERVABLE = "kernel_observable"  # observed via Sysmon/ETW, not kernel instrumentation we ship
    NETWORK = "network"


class ExpectedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str  # e.g. "Sysmon", "Security", "Defender"
    event_id: int | None = None
    description: str


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^SC-\d{3}$")
    name: str
    description: str
    layer: Layer
    # ATT&CK technique a benign activity *illustrates*; not a claim of malicious intent.
    mitre_attack: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    expected_events: list[ExpectedEvent] = Field(default_factory=list)
    timeout_seconds: int = 30
    cleanup: str = "none required"
    success_criteria: str = "scenario actions complete without error"
    destructive: bool = False  # the registry rejects any scenario that sets this true
