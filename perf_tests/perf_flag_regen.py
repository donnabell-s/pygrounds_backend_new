"""
Performance Test: Flagging & Regeneration
==========================================
Tests regeneration time for flagged questions at different concurrency levels:
  - 1 question regenerated sequentially
  - 5 questions regenerated sequentially
  - 10 questions regenerated sequentially

Each regeneration hits the preview endpoint (which calls the LLM), then applies.
Also compares regeneration time to initial generation time per question.

NOTE: regeneration is synchronous (no polling needed) — the endpoint blocks
until the LLM returns the regenerated question.

Outputs:
  - Terminal table with avg/min/max per scenario
  - perf_flag_regen.png chart (300 DPI)
"""
import os
import sys
import time

import requests
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from auth_helper import BASE_URL, auth_headers

RUNS = 3


def get_question_ids(count: int) -> list:
    """Get question IDs to test with. Prefers flagged questions, falls back to any."""
    resp = requests.get(
        f"{BASE_URL}/api/all/",
        headers=auth_headers(),
        timeout=15,
        params={"page_size": count},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to list questions: {resp.status_code}")

    data = resp.json()
    questions = data if isinstance(data, list) else data.get("results", data.get("questions", []))
    ids = [q["id"] for q in questions[:count]]

    if len(ids) < count:
        raise RuntimeError(f"Need {count} questions but only found {len(ids)}")
    return ids


def flag_question(qid: int):
    """Flag a question so we can regenerate it."""
    resp = requests.post(
        f"{BASE_URL}/api/question/{qid}/toggle-flag/",
        json={"reason": "perf-test", "note": "automated performance test"},
        headers=auth_headers(),
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Flag toggle failed for Q{qid}: {resp.status_code} {resp.text[:200]}")
    return resp.json().get("flagged", False)


def regenerate_question(qid: int) -> float:
    """Regenerate a question (preview step only — calls LLM). Returns elapsed seconds."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/question/{qid}/regenerate/",
        json={"llm_prompt": "Regenerate this question with a different angle while keeping the same difficulty and topic."},
        headers=auth_headers(),
        timeout=120,
    )
    elapsed = time.time() - t0

    if resp.status_code != 200:
        raise RuntimeError(f"Regeneration failed for Q{qid}: {resp.status_code} {resp.text[:200]}")

    return elapsed


def unflag_question(qid: int):
    """Unflag question to clean up after test."""
    try:
        # toggle-flag acts as a toggle — if flagged, this unflags
        resp = requests.post(
            f"{BASE_URL}/api/question/{qid}/toggle-flag/",
            json={},
            headers=auth_headers(),
            timeout=15,
        )
    except Exception:
        pass


def run_batch(count: int) -> dict:
    """Flag + regenerate `count` questions sequentially. Returns timing info."""
    qids = get_question_ids(count)

    # Ensure all are flagged
    for qid in qids:
        is_flagged = flag_question(qid)
        if not is_flagged:
            # Was already flagged, toggle unflagged it — toggle again
            flag_question(qid)

    per_question_times = []
    t0 = time.time()
    for i, qid in enumerate(qids):
        print(f"    Regenerating Q{qid} ({i + 1}/{count})...", end="\r", flush=True)
        try:
            qt = regenerate_question(qid)
            per_question_times.append(qt)
        except Exception as e:
            print(f"\n    WARNING: Q{qid} failed: {e}")
            per_question_times.append(float("nan"))

    total_elapsed = time.time() - t0
    print()

    # Clean up: unflag questions
    for qid in qids:
        unflag_question(qid)

    clean_times = [t for t in per_question_times if t == t]
    avg_per_q = sum(clean_times) / len(clean_times) if clean_times else 0

    return {
        "total_elapsed": total_elapsed,
        "per_question_times": per_question_times,
        "avg_per_question": avg_per_q,
        "count": count,
        "successful": len(clean_times),
    }


SCENARIOS = [
    {"label": "1 question", "count": 1},
    {"label": "5 questions", "count": 5},
    {"label": "10 questions", "count": 10},
]


def main():
    results = {}

    for scenario in SCENARIOS:
        label = scenario["label"]
        count = scenario["count"]
        runs = []

        for run in range(1, RUNS + 1):
            print(f"\n[{label}] Run {run}/{RUNS}")
            try:
                info = run_batch(count)
                runs.append(info)
                print(
                    f"  Done: {info['total_elapsed']:.1f}s total, "
                    f"{info['avg_per_question']:.2f}s/question, "
                    f"{info['successful']}/{info['count']} succeeded"
                )
            except Exception as e:
                print(f"  ERROR: {e}")
                runs.append({
                    "total_elapsed": float("nan"),
                    "avg_per_question": 0,
                    "count": count,
                    "successful": 0,
                    "per_question_times": [],
                })
        results[label] = runs

    # ── Terminal table ──
    print("\n" + "=" * 80)
    print(f"{'Scenario':<15} {'Avg Total (s)':>13} {'Min (s)':>8} {'Max (s)':>8} {'Avg/Q (s)':>10}")
    print("-" * 80)
    for label, runs in results.items():
        times = [r["total_elapsed"] for r in runs if r["total_elapsed"] == r["total_elapsed"]]
        per_qs = [r["avg_per_question"] for r in runs if r["avg_per_question"] > 0]
        if not times:
            print(f"{label:<15} {'N/A':>13}")
            continue
        avg_t = sum(times) / len(times)
        avg_pq = sum(per_qs) / len(per_qs) if per_qs else 0
        print(f"{label:<15} {avg_t:>13.1f} {min(times):>8.1f} {max(times):>8.1f} {avg_pq:>10.2f}")
    print("=" * 80)

    # ── Chart: total time bar + per-question overlay ──
    fig, ax1 = plt.subplots(figsize=(10, 6))

    labels_list = list(results.keys())
    x = np.arange(len(labels_list))
    bar_width = 0.35

    # Total time bars
    avgs_total = []
    avgs_per_q = []
    for label in labels_list:
        times = [r["total_elapsed"] for r in results[label] if r["total_elapsed"] == r["total_elapsed"]]
        per_qs = [r["avg_per_question"] for r in results[label] if r["avg_per_question"] > 0]
        avgs_total.append(sum(times) / len(times) if times else 0)
        avgs_per_q.append(sum(per_qs) / len(per_qs) if per_qs else 0)

    bars1 = ax1.bar(x - bar_width / 2, avgs_total, bar_width,
                    color="#4C72B0", edgecolor="white", label="Total Batch Time", zorder=3)
    bars2 = ax1.bar(x + bar_width / 2, avgs_per_q, bar_width,
                    color="#DD8452", edgecolor="white", label="Avg Time / Question", zorder=3)

    for bar, val in zip(bars1, avgs_total):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{val:.1f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar, val in zip(bars2, avgs_per_q):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{val:.1f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels_list, fontsize=10)
    ax1.set_ylabel("Time (seconds)")
    ax1.set_title("Flagged Question Regeneration — Batch Size Scaling")
    ax1.legend()
    ax1.grid(axis="y", alpha=0.3, zorder=0)

    fig.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), "perf_flag_regen.png")
    fig.savefig(out_path, dpi=300)
    print(f"\nChart saved to {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
