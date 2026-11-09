# Methodology and limitations

## What is measured vs. assumed

- **Observed**: scenario execution status, durations, and (on Windows) event-log
  availability and counts. Stored verbatim in SQLite.
- **Calculated**: completion rates, layer coverage, steps-to-full-coverage, SHAP
  attributions, K-means clusters, DQN training returns.
- **Hypothesis / simulated**: all DQN training results use a *simulated* feedback
  environment and are labelled `simulated: true`. They are not claims about real EDR
  behaviour.

## Reproducibility

A single random seed (`config.seed`, default 42) drives scenario ordering, the RL
environment, and the agent. Raw experiment data is preserved; reports are generated
only from stored rows.

## Baselines

The DQN selection strategy is compared against random and fixed-order selection
(`framework benchmark`).

## Known limitations

1. **Telemetry correlation is coarse.** The correlator reports channel-level
   availability and counts, not per-scenario attribution by pid/time window. This is
   a documented shortcut to be upgraded during real-Windows validation.
2. **Not validated on a real Windows host.** All results to date are from Linux with
   simulated RL feedback; event-log collection and the registry/scheduled-task
   scenarios have not executed on Windows 11.
3. **Benchmark metric is host-sensitive.** Steps-to-full-coverage counts completed
   scenarios; because Windows-only scenarios skip off Windows, the metric is only
   decisive on a real Windows host.
4. **Single security product.** K-means clustering reports "not meaningful" until
   enough distinct response profiles exist.

## Scope and ethics

Non-destructive, authorized lab use only. No stealth payloads, EDR-disabling, or
automated bypass. This is a reconstruction inspired by the VYUHA poster; it does not
reproduce the original authors' implementation and makes no claim to their results.
