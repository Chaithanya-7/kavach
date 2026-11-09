"""The built-in non-destructive scenario catalog, grouped by Windows layer.

Each scenario describes ordinary administrative/system behavior and the telemetry
it is expected to produce, so detection coverage can be measured honestly.
"""

from __future__ import annotations

from endpoint_framework.scenarios.base import ExpectedEvent, Layer, Scenario

CATALOG: list[Scenario] = [
    # --- User-mode ---
    Scenario(
        id="SC-001",
        name="Process creation",
        description="Launch a benign child process (cmd.exe /c whoami) and let it exit.",
        layer=Layer.USER_MODE,
        mitre_attack="T1059.003",  # illustrative: Windows Command Shell
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=1, description="ProcessCreate for the child"),
            ExpectedEvent(source="Security", event_id=4688, description="A new process has been created"),
        ],
        cleanup="child process exits on its own",
    ),
    Scenario(
        id="SC-002",
        name="Parent-child process chain",
        description="A short, labeled process tree (powershell -> cmd -> whoami) to study lineage telemetry.",
        layer=Layer.USER_MODE,
        mitre_attack="T1059.001",
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=1, description="ProcessCreate with ParentImage populated"),
        ],
        cleanup="processes exit on their own",
    ),
    Scenario(
        id="SC-003",
        name="File create and modify",
        description="Create, write, and delete a temp file under the workspace to study file telemetry.",
        layer=Layer.USER_MODE,
        mitre_attack="T1074.001",
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=11, description="FileCreate for the temp file"),
        ],
        cleanup="temp file is deleted at end of scenario",
    ),
    # --- OS-service ---
    Scenario(
        id="SC-010",
        name="Temporary registry key",
        description="Create a value under HKCU\\Software and remove it, to study registry telemetry.",
        layer=Layer.OS_SERVICE,
        mitre_attack="T1112",
        prerequisites=["write access to HKCU (no elevation needed)"],
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=13, description="RegistryValueSet under the test key"),
        ],
        cleanup="registry value and key are deleted",
    ),
    Scenario(
        id="SC-011",
        name="Scheduled task create and delete",
        description="Register a disabled scheduled task that runs nothing, then delete it.",
        layer=Layer.OS_SERVICE,
        mitre_attack="T1053.005",
        prerequisites=["schtasks.exe available"],
        expected_events=[
            ExpectedEvent(source="Security", event_id=4698, description="A scheduled task was created"),
        ],
        cleanup="scheduled task is deleted",
    ),
    Scenario(
        id="SC-012",
        name="Service status inspection",
        description="Query (read-only) the state of a standard Windows service. No service is modified.",
        layer=Layer.OS_SERVICE,
        expected_events=[],
        cleanup="none required (read-only)",
        success_criteria="service query returns a status",
    ),
    # --- Kernel-observable (via Sysmon/ETW; we ship no kernel driver) ---
    Scenario(
        id="SC-020",
        name="Process lifecycle observation",
        description="Observe start and stop events of a benign process through Sysmon, not kernel code we ship.",
        layer=Layer.KERNEL_OBSERVABLE,
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=1, description="ProcessCreate"),
            ExpectedEvent(source="Sysmon", event_id=5, description="ProcessTerminate"),
        ],
        cleanup="process exits on its own",
    ),
    Scenario(
        id="SC-021",
        name="Image load observation",
        description="Observe module/image load events for a benign process via Sysmon event 7.",
        layer=Layer.KERNEL_OBSERVABLE,
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=7, description="ImageLoad (requires Sysmon ImageLoad config)"),
        ],
        cleanup="process exits on its own",
    ),
    # --- Network ---
    Scenario(
        id="SC-030",
        name="Localhost TCP connection",
        description="Open a short-lived TCP connection to a loopback listener started by the framework.",
        layer=Layer.NETWORK,
        mitre_attack="T1071",
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=3, description="NetworkConnect (requires Sysmon network config)"),
        ],
        cleanup="connection and local listener are closed",
    ),
    Scenario(
        id="SC-031",
        name="DNS resolution",
        description="Resolve a designated lab test domain to study DNS telemetry.",
        layer=Layer.NETWORK,
        mitre_attack="T1071.004",
        prerequisites=["lab DNS reachable"],
        expected_events=[
            ExpectedEvent(source="Sysmon", event_id=22, description="DnsQuery (requires Sysmon DNS config)"),
        ],
        cleanup="none required",
    ),
]
