import joblib
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
kmeans = joblib.load(BASE_DIR / "ml_models" / "learner_clusters.pkl")
scaler = joblib.load(BASE_DIR / "ml_models" / "learner_scaler.pkl")

CLUSTER_MASTERY_DEFAULTS = {0: 0.40, 1: 0.25, 2: 0.10}
CLUSTER_NAMES = {0: "proficient", 1: "mid", 2: "novice"}


def assign_learner_cluster(avg_response_time: float, accuracy: float) -> int:
    """
    Returns cluster int (0, 1, or 2). Call after pre-assessment completes.
    Features must match training order: [avg_response_time, accuracy].
    """
    X = np.array([[avg_response_time, accuracy]])
    X_scaled = scaler.transform(X)
    return int(kmeans.predict(X_scaled)[0])


def get_cluster_mastery_default(cluster: int) -> float:
    """Returns starting mastery float (0–1) for unassessed subtopics."""
    return CLUSTER_MASTERY_DEFAULTS.get(cluster, 0.10)


def get_cluster_name(cluster: int) -> str:
    """Returns human-readable label: novice / mid / proficient."""
    return CLUSTER_NAMES.get(cluster, "novice")
