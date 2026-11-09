"""K-means over defensive-response profiles across experiments.

Honest by design: with too few experiments to cluster meaningfully, it reports
that rather than manufacturing comparisons (per project methodology).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from endpoint_framework.analysis.metrics import compute_metrics
from endpoint_framework.storage import Database

MIN_SAMPLES = 3  # fewer response profiles than this cannot be clustered meaningfully


@dataclass
class ClusterResult:
    meaningful: bool
    reason: str = ""
    labels: list[int] | None = None
    silhouette: float | None = None
    k: int | None = None
    experiment_ids: list[str] | None = None


def _feature_row(m) -> list[float]:
    return [m.completion_rate, m.failed / m.total if m.total else 0.0,
            m.skipped / m.total if m.total else 0.0, m.telemetry_observed / m.total if m.total else 0.0,
            float(len(m.layer_coverage)), m.mean_duration_s]


def cluster_experiments(db: Database, k: int = 2) -> ClusterResult:
    exps = db.list_experiments()
    if len(exps) < MIN_SAMPLES:
        return ClusterResult(False, f"only {len(exps)} experiment(s); need >= {MIN_SAMPLES} to cluster")
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    ids = [e.id for e in exps]
    X = np.array([_feature_row(compute_metrics(db, e.id)) for e in exps])
    Xs = StandardScaler().fit_transform(X)
    k = max(2, min(k, len(exps) - 1))
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Xs)
    sil = float(silhouette_score(Xs, labels)) if len(set(labels)) > 1 else None
    return ClusterResult(True, labels=labels.tolist(), silhouette=sil, k=k, experiment_ids=ids)
