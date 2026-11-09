# Setup

## Windows 11 (primary target, PowerShell)

```powershell
git clone -b claude/laughing-brown-kcs7l6 https://github.com/chaithanya-7/kavach.git
cd kavach
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install -e ".[dev]"
framework init
framework doctor                   # also run from an elevated prompt for the Security log
python -m pytest -q
```

Install Sysmon (with a config that logs process, network, image-load and DNS events)
for telemetry collection. `framework doctor` reports whether each event channel is
present and enabled.

## Lab authorization

Scenario execution is refused until `lab.authorized: true` in `configs/framework.yaml`.
Set it only inside an isolated, authorized Windows test VM.

## Linux (development only)

The framework installs and the full test suite runs on Linux. Windows-only paths
(event logs, registry and scheduled-task scenarios) report `SKIP` / `source_unavailable`
honestly; they are not exercised. `pip install` pulls torch/shap (~1 GB).

## Dependencies

torch and shap are heavy. For a lighter dev install, the baseline CLI (init/status/
doctor/scenarios/run) works without them; train/analyze require torch, analyze's SHAP
step requires shap.
