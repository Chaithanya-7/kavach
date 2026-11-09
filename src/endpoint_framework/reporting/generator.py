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
    return out
