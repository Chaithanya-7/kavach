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
| `framework scenarios list [--layer L]` | List the non-destructive cross-layer scenario catalog |
| `framework menu` | Branded banner + module menu |
| `framework shell` | Interactive console (wraps the same commands) |
| `framework scenarios info SC-XXX` | Show one scenario's full definition |
| `framework run --scenario SC-XXX / --profile P` | Execute a controlled scenario (lab-gated) — _pending Stage 3_ |
| `framework train --episodes N` | Train the DQN agent — _pending Stage 5_ |
| `framework evaluate --mode adaptive/random/fixed` | Evaluate a strategy — _pending Stage 6_ |
| `framework analyze --run EXP-XXX` | Metrics + SHAP + K-means — _pending Stage 7_ |
| `framework report --run EXP-XXX` | Exports + figures — _pending Stage 8_ |
| `--config PATH`, `-v` | Alternate config (or `$env:FRAMEWORK_CONFIG`), verbose console logs |

Logs: JSON lines in `outputs/logs/framework.jsonl`.

## Progress

- [x] Stage 1 — Foundation: package, config validation, structured logging, `init`/`status`/`doctor`, tests
- [x] Stage 2 — Core orchestration: experiment model + lifecycle state machine, SQLite storage
- [x] Stage 3 — Controlled Windows scenarios: non-destructive executor (process/file/registry/schtask/TCP/DNS/service), Windows-only steps skip honestly off Windows
- [~] Stage 4 — Telemetry: Sysmon/Security/Defender collector + normalizer (Windows-only; **unverified on a real host**)
- [x] Stage 5 — DQN: trainable PyTorch agent on simulated feedback, beats random baseline, checkpoints
- [~] Stage 6 — Adaptive orchestration: `evaluate` validates modes; DQN-in-the-loop over real runs still to wire
- [x] Stage 7 — SHAP (GradientExplainer) + K-means (honest "not meaningful" with too few experiments)
- [x] Stage 8 — Reporting: CSV/JSON exports + matplotlib figures (training curve, coverage)

Verified on Linux (71 tests). Windows-specific paths (event logs, registry/schtask execution) are **not yet run on a real Windows 11 host**. Results from `train` are **simulated feedback**, labelled as such.