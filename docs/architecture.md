# Architecture

KAVACH is a CLI research framework for evaluating Windows endpoint security through
controlled, non-destructive experiments. Subsystems communicate through typed Python
interfaces and dataclass/Pydantic models.

```
CLI (Typer + Rich)
  -> core/        config (Pydantic/YAML), logging (JSON-lines), environment checks
  -> scenarios/   Scenario schema, registry, non-destructive executor
  -> telemetry/   Sysmon / Security / Defender collector + correlator (Windows)
  -> rl/          DQN agent, simulated environment, replay buffer, trainer
  -> storage/     SQLite: experiments + scenario runs, lifecycle state machine
  -> analysis/    metrics, SHAP, K-means, matplotlib figures
  -> reporting/   CSV/JSON exports, research figures, benchmark
```

## Experiment lifecycle

`CREATED -> VALIDATED -> RUNNING -> COLLECTING -> (ANALYZING ->) COMPLETED`, with
`FAILED` / `CANCELLED` reachable from any live state. Transitions are enforced in
`storage/models.py`; illegal transitions raise `StateError`.

## Data flow for `run` / `evaluate` / `benchmark`

1. A strategy orders the eligible scenarios (fixed / random / adaptive-from-DQN).
2. Each scenario executes its benign action (`scenarios/executor.py`).
3. The correlator collects the scenario's expected telemetry sources.
4. Each run is persisted with status + telemetry status + duration.
5. `analyze` / `report` / `benchmark` compute metrics and figures from stored rows.

## Design boundaries

- No exploit, EDR-disabling, or anti-forensic modules. Scenarios are ordinary
  system activity, honestly labelled.
- DQN reward is coverage / information gain, never detection evasion.
- Simulated RL feedback is labelled `simulated: true`; it is never presented as
  observed telemetry.
