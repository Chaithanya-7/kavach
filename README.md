# Adaptive Cross-Layer Endpoint Defense Evaluation Framework

CLI research framework for evaluating endpoint security on **Windows 11** using controlled,
non-destructive scenarios, Windows telemetry, and a DQN agent for adaptive scenario selection.
Architecture inspired by VYUHA; this is an independent reconstruction, not the original authors' code.

**Authorized, isolated lab use only.** Scenario execution is gated on `lab.authorized: true` in
`configs/framework.yaml`, which you should set only inside a dedicated test VM.

## Setup (Windows PowerShell)

```powershell
git clone https://github.com/chaithanya-7/kavach.git
cd kavach
py -3.11 -m venv .venv            # any Python >= 3.11
.\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install -e ".[dev]"
framework --help
framework init
framework status
framework doctor
python -m pytest -q
```

Run `framework doctor` from an elevated PowerShell to see the Security event log; it is reported
`WARN (unavailable)` when unprivileged. That is a collection limit, not a detection result.

## Commands (Stage 1)

| Command | Purpose |
|---|---|
| `framework init [--force]` | Write `configs/framework.yaml`, create `experiments/` and `outputs/{logs,models,graphs,reports}` |
| `framework status` | Active config, seed, lab gate, workspace directories |
| `framework doctor` | Read-only readiness checks (Python, Windows 11 build, admin, pywin32, Sysmon/Security/Defender logs, config, lab gate). Exit 1 on any FAIL |
| `--config PATH`, `-v` | Alternate config (or `$env:FRAMEWORK_CONFIG`), verbose console logs |

Logs: JSON lines in `outputs/logs/framework.jsonl`.

## Progress

- [x] Stage 1 — Foundation: package, config validation, structured logging, `init`/`status`/`doctor`, tests
- [ ] Stage 2 — Core orchestration: experiment model + lifecycle, scheduler, scenario registry, SQLite storage
- [ ] Stage 3 — Controlled Windows scenarios
- [ ] Stage 4 — Telemetry (Sysmon, Security, Defender)
- [ ] Stage 5 — DQN (simulated feedback first, clearly labelled)
- [ ] Stage 6 — Adaptive orchestration
- [ ] Stage 7 — SHAP + K-means
- [ ] Stage 8 — Benchmarks (DQN vs random vs fixed-order), reporting

Stage 1 verification so far: tests and CLI run on Linux (Windows-only checks report SKIP).
**Pending:** verification on a real Windows 11 host.
