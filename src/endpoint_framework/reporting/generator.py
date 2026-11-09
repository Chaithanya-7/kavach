"""Assemble CSV/JSON exports and figures for an experiment from stored data."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from endpoint_framework.analysis.metrics import compute_metrics
from endpoint_framework.analysis.visualization import coverage_bar, training_curve
from endpoint_framework.storage import Database


def export_experiment(db: Database, experiment_id: str, reports_dir: Path, models_dir: Path) -> dict[str, Path]:
    """Write runs CSV, metrics JSON, coverage figure, and (if present) the training curve."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    runs = db.runs_for(experiment_id)
    csv_path = reports_dir / f"{experiment_id}_runs.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario_id", "status", "duration_s", "telemetry_status", "event_count", "detail"])
        for r in runs:
            w.writerow([r.scenario_id, r.status, r.duration_s, r.telemetry_status, r.event_count, r.detail])
    out["runs_csv"] = csv_path

    metrics = compute_metrics(db, experiment_id)
    metrics_path = reports_dir / f"{experiment_id}_metrics.json"
    metrics_path.write_text(json.dumps(asdict(metrics), indent=2), encoding="utf-8")
    out["metrics_json"] = metrics_path

    out["coverage_png"] = coverage_bar(metrics.layer_coverage, reports_dir / f"{experiment_id}_coverage.png")

    dqn_metrics = models_dir / "dqn_metrics.json"
    if dqn_metrics.is_file():
        out["training_curve_png"] = training_curve(dqn_metrics, reports_dir / "dqn_training_curve.png")

    out["report_md"] = _write_markdown(db, experiment_id, reports_dir, out)
    return out


def _write_markdown(db: Database, experiment_id: str, reports_dir: Path, artifacts: dict[str, Path]) -> Path:
    """One research-quality Markdown report assembling metrics, runs, SHAP and benchmark."""
    exp = db.get_experiment(experiment_id)
    m = compute_metrics(db, experiment_id)
    runs = db.runs_for(experiment_id)
    lines: list[str] = [
        f"# Experiment {experiment_id}",
        "",
        f"- Profile: `{exp.profile}`  |  State: **{exp.state}**  |  Seed: {exp.seed}",
        f"- Host: {exp.host or 'n/a'}  |  Created: {exp.created_at[:19]}",
        "",
        "## Metrics",
        "",
        f"- Scenarios: {m.total}  (completed {m.completed}, failed {m.failed}, skipped {m.skipped})",
        f"- Completion rate: {m.completion_rate:.0%}",
        f"- Telemetry observed: {m.telemetry_observed}  |  Mean duration: {m.mean_duration_s:.3f}s",
        f"- Layer coverage: {', '.join(f'{k}: {v}' for k, v in m.layer_coverage.items()) or 'none'}",
        "",
        "## Scenario runs",
        "",
        "| Scenario | Status | Duration (s) | Telemetry | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in runs:
        lines.append(f"| {r.scenario_id} | {r.status} | {r.duration_s} | {r.telemetry_status} | {r.detail} |")

    analysis = reports_dir / f"{experiment_id}_analysis.json"
    if analysis.is_file():
        data = json.loads(analysis.read_text(encoding="utf-8"))
        shap = data.get("shap")
        if shap:
            top = sorted(shap["importances"].items(), key=lambda kv: kv[1], reverse=True)[:5]
            lines += ["", "## DQN explainability (SHAP, simulated)", "",
                      f"Method: `{shap['method']}`. Top features:", ""]
            lines += [f"- {sid}: {v:.4f}" for sid, v in top]

    bench = reports_dir / "benchmark.json"
    if bench.is_file():
        b = json.loads(bench.read_text(encoding="utf-8"))
        lines += ["", "## Strategy benchmark", "", "| Strategy | Steps to full coverage | Completed |",
                  "| --- | --- | --- |"]
        for mode, v in b.items():
            lines.append(f"| {mode} | {v['steps_to_full_coverage']} | {v['completed']} |")
        lines.append("")
        lines.append("_Note: this metric is only decisive on a real Windows host (Windows-only "
                     "scenarios skip off Windows)._")

    lines += ["", "## Figures", ""]
    for key in ("coverage_png", "training_curve_png"):
        if key in artifacts:
            lines.append(f"![{key}]({artifacts[key].name})")
    lines += ["", "---", "_Generated from stored experiment data. DQN training uses simulated "
              "feedback; results are not validated on a real Windows host._", ""]

    path = reports_dir / f"{experiment_id}_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
