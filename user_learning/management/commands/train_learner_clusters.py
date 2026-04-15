import numpy as np
import joblib
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models.expressions import ExpressionWrapper
from django.db.models import Avg, Count, FloatField
from django.db.models.functions import Cast
from django.db.models import IntegerField

from minigames.models import PreAssessmentResponse

MODEL_DIR     = Path(__file__).resolve().parent.parent.parent / "ml_models"
CLUSTERS_PATH = MODEL_DIR / "learner_clusters.pkl"
SCALER_PATH   = MODEL_DIR / "learner_scaler.pkl"
MIN_STUDENTS  = 50


class Command(BaseCommand):
    help = (
        "Retrains the K-Means learner cluster model on real PreAssessmentResponse data. "
        "Overwrites user_learning/ml_models/learner_clusters.pkl and learner_scaler.pkl. "
        "Use --dry-run to inspect results without overwriting."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run aggregation and training but do not overwrite .pkl files.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # ── 1. Aggregate per-student stats from real pre-assessment responses
        students = (
            PreAssessmentResponse.objects
            .values("user_id")
            .annotate(
                avg_time=Avg("time_taken"),
                accuracy=Avg(
                    ExpressionWrapper(
                        Cast("is_correct", output_field=IntegerField()),
                        output_field=FloatField()
                    )
                ),
                question_count=Count("id")
            )
            .filter(question_count__gte=3)
        )

        student_list = list(students)
        n = len(student_list)

        self.stdout.write(f"Students with ≥3 responses: {n}")

        # ── 2. Minimum sample size gate
        if n < MIN_STUDENTS:
            self.stdout.write(
                self.style.WARNING(
                    f"Insufficient data: {n} students found, {MIN_STUDENTS} required. "
                    f"Existing .pkl files were NOT modified."
                )
            )
            return

        # ── 3. Build feature matrix [avg_time, accuracy]
        X = np.array([[s["avg_time"], s["accuracy"]] for s in student_list])

        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        kmeans.fit(X_scaled)

        # ── 4. Centroid report (in original scale)
        centroids_scaled = kmeans.cluster_centers_
        centroids_orig   = scaler.inverse_transform(centroids_scaled)

        self.stdout.write("\nCluster centroids (original scale):")
        self.stdout.write(f"  {'Cluster':<10} {'avg_time':>12} {'accuracy':>12}")
        self.stdout.write(f"  {'-'*36}")
        for i, c in enumerate(centroids_orig):
            self.stdout.write(f"  {i:<10} {c[0]:>12.2f} {c[1]:>12.4f}")

        self.stdout.write(
            self.style.WARNING(
                "\nACTION REQUIRED: Inspect the centroids above and verify that the cluster "
                "number → label mapping in clustering.py (CLUSTER_NAMES, CLUSTER_MASTERY_DEFAULTS) "
                "still matches. Update manually if the ordering has changed."
            )
        )

        # ── 5. Save or dry-run
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n--dry-run: training complete. "
                    f"Would have written:\n  {CLUSTERS_PATH}\n  {SCALER_PATH}\n"
                    f"No files were modified."
                )
            )
        else:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            joblib.dump(kmeans, CLUSTERS_PATH)
            joblib.dump(scaler, SCALER_PATH)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSaved:\n  {CLUSTERS_PATH}\n  {SCALER_PATH}"
                )
            )
