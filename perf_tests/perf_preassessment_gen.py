"""
Performance Test: Pre-Assessment Question Generation
=====================================================
Tests generation time across different topic counts:
  - 3 topics  (topic_ids 1-3)
  - 5 topics  (topic_ids 1-5)
  - 10 topics (topic_ids 1-10)
  - All topics (14 topics, no filter — server uses all)

Polls the generation status endpoint until complete.
Also checks difficulty distribution of generated questions.

Outputs:
  - Terminal table with avg/min/max per scenario
  - perf_preassessment_gen.png chart (300 DPI)
"""
import os
import sys
import time
from collections import Counter

import requests
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from auth_helper import BASE_URL, auth_headers

RUNS = 3
POLL_INTERVAL = 3
TOTAL_QUESTIONS = 30  # per scenario

SCENARIOS = [
    {
        "label": "3 topics",
        "body": {"topic_ids": [1, 2, 3], "total_questions": TOTAL_QUESTIONS},
    },
    {
        "label": "5 topics",
        "body": {"topic_ids": [1, 2, 3, 4, 5], "total_questions": TOTAL_QUESTIONS},
    },
    {
        "label": "10 topics",
        "body": {"topic_ids": list(range(1, 11)), "total_questions": TOTAL_QUESTIONS},
    },
    {
        "label": "All topics (14)",
        "body": {"total_questions": TOTAL_QUESTIONS},  # no topic_ids = all
    },
]


def start_generation(body: dict) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/generate/preassessment/",
        json=body,
        headers=auth_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Pre-assessment start failed: {resp.status_code} {resp.text[:300]}")
    return resp.json()["session_id"]


def poll_until_done(session_id: str, timeout: int = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/generate/status/{session_id}/",
            headers=auth_headers(),
            timeout=15,
        )
        data = resp.json()
        
        if "error" in data:
            status = "error"
            data["status"] = "error"
            return data
            
        status = data.get("status", "unknown")

        if status in ("completed", "failed", "error"):
            return data

        step = data.get("step", "")
        generated = data.get("questions_generated", 0)
        total = data.get("total_questions", "?")
        print(f"    [{status}] {step} — {generated}/{total}", end="\r", flush=True)
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Session {session_id} timed out after {timeout}s")


def get_difficulty_distribution() -> dict:
    """Fetch current pre-assessment questions and count by difficulty."""
    resp = requests.get(
        f"{BASE_URL}/api/preassessment/",
        headers=auth_headers(),
        timeout=15,
    )
    if resp.status_code != 200:
        return {}
    questions = resp.json()
    if isinstance(questions, dict):
        questions = questions.get("results", questions.get("questions", []))
    return dict(Counter(q.get("estimated_difficulty", "unknown") for q in questions))


def run_single(scenario: dict) -> dict:
    session_id = start_generation(scenario["body"])
    print(f"  session_id={session_id[:12]}...")

    t0 = time.time()
    final = poll_until_done(session_id)
    elapsed = time.time() - t0
    print()

    generated = 0
    if "assessment_info" in final:
        generated = final["assessment_info"].get("questions_generated", 0)
    elif "questions_generated" in final:
        generated = final["questions_generated"]

    distribution = get_difficulty_distribution()

    return {
        "elapsed": elapsed,
        "questions_generated": generated,
        "difficulty_distribution": distribution,
        "status": final.get("status"),
    }


def main():
    results = {}

    for scenario in SCENARIOS:
        label = scenario["label"]
        runs = []
        for run in range(1, RUNS + 1):
            print(f"\n[{label}] Run {run}/{RUNS}")
            try:
                info = run_single(scenario)
                runs.append(info)
                print(
                    f"  Done: {info['elapsed']:.1f}s, "
                    f"{info['questions_generated']} questions, "
                    f"dist={info['difficulty_distribution']}"
                )
            except Exception as e:
                print(f"  ERROR: {e}")
                runs.append({
                    "elapsed": float("nan"),
                    "questions_generated": 0,
                    "difficulty_distribution": {},
                    "status": "error",
                })
        results[label] = runs

    # ── Terminal table ──
    print("\n" + "=" * 80)
    print(f"{'Scenario':<20} {'Avg (s)':>8} {'Min (s)':>8} {'Max (s)':>8} {'Avg Q':>7} {'Last Dist':>25}")
    print("-" * 80)
    for label, runs in results.items():
        times = [r["elapsed"] for r in runs if r["elapsed"] == r["elapsed"]]
        if not times:
            print(f"{label:<20} {'N/A':>8}")
            continue
        avg_t = sum(times) / len(times)
        avg_q = sum(r["questions_generated"] for r in runs) / len(runs)
        last_dist = runs[-1]["difficulty_distribution"]
        dist_str = ", ".join(f"{k[0]}:{v}" for k, v in sorted(last_dist.items())) if last_dist else "N/A"
        print(f"{label:<20} {avg_t:>8.1f} {min(times):>8.1f} {max(times):>8.1f} {avg_q:>7.0f} {dist_str:>25}")
    print("=" * 80)

    # ── Chart: grouped bar (time) + stacked bar (difficulty) ──
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    labels_list = list(results.keys())
    avgs = []
    mins_list = []
    maxs_list = []
    for label in labels_list:
        times = [r["elapsed"] for r in results[label] if r["elapsed"] == r["elapsed"]]
        avgs.append(sum(times) / len(times) if times else 0)
        mins_list.append(min(times) if times else 0)
        maxs_list.append(max(times) if times else 0)

    # Left: generation time
    x = np.arange(len(labels_list))
    bars = ax1.bar(x, avgs, 0.5, color="#4C72B0", edgecolor="white", zorder=3)
    err_lo = [a - m for a, m in zip(avgs, mins_list)]
    err_hi = [m - a for a, m in zip(avgs, maxs_list)]
    ax1.errorbar(x, avgs, yerr=[err_lo, err_hi], fmt="none", ecolor="black", capsize=5, zorder=4)

    for bar, val in zip(bars, avgs):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{val:.1f}s", ha="center", va="bottom", fontweight="bold", fontsize=9)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels_list, fontsize=9)
    ax1.set_ylabel("Generation Time (seconds)")
    ax1.set_title("Generation Time by Topic Count")
    ax1.grid(axis="y", alpha=0.3, zorder=0)

    # Right: difficulty distribution (last run of each scenario)
    diff_levels = ["beginner", "intermediate", "advanced", "master"]
    colors = ["#55A868", "#4C72B0", "#DD8452", "#C44E52"]
    bottom = np.zeros(len(labels_list))

    for diff, color in zip(diff_levels, colors):
        vals = []
        for label in labels_list:
            last_run = results[label][-1]
            vals.append(last_run["difficulty_distribution"].get(diff, 0))
        ax2.bar(x, vals, 0.5, bottom=bottom, label=diff.capitalize(), color=color, edgecolor="white", zorder=3)
        bottom += np.array(vals)

    ax2.set_xticks(x)
    ax2.set_xticklabels(labels_list, fontsize=9)
    ax2.set_ylabel("Number of Questions")
    ax2.set_title("Difficulty Distribution (Last Run)")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.3, zorder=0)

    fig.suptitle("Pre-Assessment Question Generation Performance", fontsize=13, fontweight="bold")
    fig.tight_layout()

    out_path = os.path.join(os.path.dirname(__file__), "perf_preassessment_gen.png")
    fig.savefig(out_path, dpi=300)
    print(f"\nChart saved to {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
