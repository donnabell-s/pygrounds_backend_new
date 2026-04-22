"""
Performance Test: Bulk Question Generation (Minigame)
=====================================================
Tests generation time across different scenario configurations:
  - 5 questions/subtopic × all 4 difficulties
  - 10 questions/subtopic × all 4 difficulties
  - 5 questions/subtopic × 1 difficulty (beginner only)
  - 5 questions/subtopic × 2 difficulties (beginner + intermediate)
  - 5 questions/subtopic × 3 difficulties (beginner + intermediate + advanced)

Uses a single topic (topic_id=1) to keep runs manageable.
Polls the generation status endpoint until complete.

Outputs:
  - Terminal table with avg/min/max per scenario
  - perf_bulk_question_gen.png chart (300 DPI)
"""
import os
import sys
import time

import requests
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from auth_helper import BASE_URL, auth_headers

RUNS = 3
POLL_INTERVAL = 3
SUBTOPIC_IDS = [1, 2, 3]  # Use specific subtopics

SCENARIOS = [
    # ---- NON-CODING SCENARIOS ----
    {
        "label": "NC: 5 Q/sub\nBeginner (1 sub)",
        "body": {
            "game_type": "non_coding",
            "num_questions_per_subtopic": 5,
            "difficulty_levels": ["beginner"],
            "subtopic_ids": SUBTOPIC_IDS[:1],
        },
    },
    {
        "label": "NC: 5 Q/sub\nInter. (2 sub)",
        "body": {
            "game_type": "non_coding",
            "num_questions_per_subtopic": 5,
            "difficulty_levels": ["intermediate"],
            "subtopic_ids": SUBTOPIC_IDS[:2],
        },
    },
    {
        "label": "NC: 5 Q/sub\nAdv. (3 sub)",
        "body": {
            "game_type": "non_coding",
            "num_questions_per_subtopic": 5,
            "difficulty_levels": ["advanced"],
            "subtopic_ids": SUBTOPIC_IDS[:3],
        },
    },
    # ---- CODING SCENARIOS (Heavier) ----
    {
        "label": "C: 2 Q/sub\nBeginner (1 sub)",
        "body": {
            "game_type": "coding",
            "num_questions_per_subtopic": 2,
            "difficulty_levels": ["beginner"],
            "subtopic_ids": SUBTOPIC_IDS[:1],
        },
    },
    {
        "label": "C: 2 Q/sub\nInter. (2 sub)",
        "body": {
            "game_type": "coding",
            "num_questions_per_subtopic": 2,
            "difficulty_levels": ["intermediate"],
            "subtopic_ids": SUBTOPIC_IDS[:2],
        },
    },
    {
        "label": "C: 2 Q/sub\nAdv. (3 sub)",
        "body": {
            "game_type": "coding",
            "num_questions_per_subtopic": 2,
            "difficulty_levels": ["advanced"],
            "subtopic_ids": SUBTOPIC_IDS[:3],
        },
    },
]


def start_generation(body: dict) -> str:
    """Start bulk generation, return session_id."""
    resp = requests.post(
        f"{BASE_URL}/api/generate/bulk/",
        json=body,
        headers=auth_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Bulk gen start failed: {resp.status_code} {resp.text[:300]}")
    return resp.json()["session_id"]


def poll_until_done(session_id: str, timeout: int = 900) -> dict:
    """Poll status until completed/failed. Returns final status payload."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/generate/status/{session_id}/",
            headers=auth_headers(),
            timeout=15,
        )
        data = resp.json()
        status = data.get("status", "unknown")

        if status in ("completed", "failed", "error"):
            return data

        progress = data.get("overall_progress", {})
        generated = progress.get("total_questions_generated", 0)
        workers_done = progress.get("workers_completed", 0)
        total_workers = data.get("worker_summary", {}).get("total_workers", "?")
        print(
            f"    [{status}] workers {workers_done}/{total_workers}, "
            f"questions: {generated}",
            end="\r", flush=True,
        )
            
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Session {session_id} did not finish within {timeout}s")


def run_single(scenario: dict) -> dict:
    """Run one scenario, return timing + question count info."""
    session_id = start_generation(scenario["body"])
    print(f"  session_id={session_id[:12]}...")

    t0 = time.time()
    final = poll_until_done(session_id)
    elapsed = time.time() - t0
    print()  # clear \r line

    total_q = final.get("questions_generated", final.get("overall_progress", {}).get("total_questions_generated", 0))
    # if total_q is still 0, try fetching the specific total calculated before making requests
    if total_q == 0:
        total_q = len(scenario["body"].get("subtopic_ids", [])) * len(scenario["body"].get("difficulty_levels", [])) * scenario["body"].get("num_questions_per_subtopic", 1)

    # calculate by taking total elapsed time divided by the full batch count
    per_q = elapsed / total_q if total_q > 0 else 0

    return {
        "elapsed": elapsed,
        "total_questions": total_q,
        "time_per_question": per_q,
        "status": final.get("status"),
    }


def main():
    results = {}  # label -> list of run dicts

    for scenario in SCENARIOS:
        label = scenario["label"]
        runs = []
        for run in range(1, RUNS + 1):
            print(f"\n[{label.split(chr(10))[0]}] Run {run}/{RUNS}")
            try:
                info = run_single(scenario)
                runs.append(info)
                print(
                    f"  Done: {info['elapsed']:.1f}s, "
                    f"{info['total_questions']} questions, "
                    f"{info['time_per_question']:.2f}s/question"
                )
            except Exception as e:
                print(f"  ERROR: {e}")
                runs.append({"elapsed": float("nan"), "total_questions": 0, "time_per_question": 0, "status": "error"})
        results[label] = runs

    # ── Terminal table ──
    print("\n" + "=" * 90)
    print(f"{'Scenario':<25} {'Avg (s)':>8} {'Min (s)':>8} {'Max (s)':>8} {'Avg Q':>7} {'Avg s/Q':>8}")
    print("-" * 90)
    for label, runs in results.items():
        times = [r["elapsed"] for r in runs if r["elapsed"] == r["elapsed"]]
        if not times:
            print(f"{label.split(chr(10))[0]:<25} {'N/A':>8}")
            continue
        avg_t = sum(times) / len(times)
        avg_q = sum(r["total_questions"] for r in runs) / len(runs)
        avg_per = sum(r["time_per_question"] for r in runs if r["time_per_question"] == r["time_per_question"]) / len(times)
        print(
            f"{label.split(chr(10))[0]:<25} "
            f"{avg_t:>8.1f} {min(times):>8.1f} {max(times):>8.1f} "
            f"{avg_q:>7.0f} {avg_per:>8.2f}"
        )
    print("=" * 90)

    # ── Chart: dual-axis (total time + time per question) ──
    labels = list(results.keys())
    avgs = []
    per_q_avgs = []
    for label in labels:
        times = [r["elapsed"] for r in results[label] if r["elapsed"] == r["elapsed"]]
        per_qs = [r["time_per_question"] for r in results[label] if r["time_per_question"] == r["time_per_question"]]
        avgs.append(sum(times) / len(times) if times else 0)
        per_q_avgs.append(sum(per_qs) / len(per_qs) if per_qs else 0)

    fig, ax1 = plt.subplots(figsize=(12, 6))
    x = range(len(labels))
    bar_width = 0.4

    bars = ax1.bar(x, avgs, bar_width, color="#4C72B0", edgecolor="white", label="Total Time", zorder=3)
    ax1.set_ylabel("Total Generation Time (seconds)", color="#4C72B0")
    ax1.tick_params(axis="y", labelcolor="#4C72B0")

    for bar, val in zip(bars, avgs):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{val:.1f}s", ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax2 = ax1.twinx()
    ax2.plot([i + bar_width / 2 for i in x], per_q_avgs, "o-", color="#DD8452",
             linewidth=2, markersize=8, label="Time/Question", zorder=4)
    ax2.set_ylabel("Time per Question (seconds)", color="#DD8452")
    ax2.tick_params(axis="y", labelcolor="#DD8452")
    ax2.set_ylim(bottom=0) # ensure it doesn't look flat!

    for i, val in enumerate(per_q_avgs):
        ax2.text(x[i] + bar_width / 2, val + 0.1, f"{val:.1f}s", ha="center", va="bottom", fontsize=8, color="#DD8452", fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_title("Bulk Question Generation — Total Time & Per-Question Cost")
    ax1.grid(axis="y", alpha=0.3, zorder=0)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    fig.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), "perf_bulk_question_gen.png")
    fig.savefig(out_path, dpi=300)
    print(f"\nChart saved to {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
