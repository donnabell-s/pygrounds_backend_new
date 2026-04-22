"""
Performance Test: PDF Parser Pipeline
======================================
Tests full processing time (upload → pipeline → completion) for 3 PDFs of different sizes.
Polls the status endpoint until processing finishes.

Outputs:
  - Terminal table with avg/min/max per PDF
  - perf_pdf_pipeline.png chart (300 DPI)
"""
import os
import sys
import time

import requests
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from auth_helper import BASE_URL, auth_headers

RUNS = 3
POLL_INTERVAL = 5  # seconds between status checks

PDFS = {
    "Small (~1.3 MB)\npython_intermediate": os.path.join(
        os.path.dirname(__file__), "..", "pdfs", "python_intermediate.pdf"
    ),
    "Medium (~6.5 MB)\nPython Basics": os.path.join(
        os.path.dirname(__file__), "..", "pdfs",
        "Python_Basics_A_Practical_Introduction_To_Python_3.pdf",
    ),
    "Large (~16 MB)\nFluent Python": os.path.join(
        os.path.dirname(__file__), "..", "pdfs", "fluent_python.pdf"
    ),
}


def upload_pdf(filepath: str) -> int:
    """Upload a PDF and return its document_id."""
    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/docs/upload/",
            files={"file": (os.path.basename(filepath), f, "application/pdf")},
            headers=auth_headers(),
            timeout=120,
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed: {resp.status_code} {resp.text[:300]}")
    return resp.json()["id"]


def start_pipeline(doc_id: int):
    """Trigger the async pipeline."""
    resp = requests.post(
        f"{BASE_URL}/api/pipeline/{doc_id}/",
        json={"reprocess": True},
        headers=auth_headers(),
        timeout=30,
    )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Pipeline start failed: {resp.status_code} {resp.text[:300]}")


def poll_until_done(doc_id: int, timeout: int = 1800) -> str:
    """Poll status endpoint until COMPLETED or FAILED. Returns final status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/docs/{doc_id}/status/",
            headers=auth_headers(),
            timeout=15,
        )
        data = resp.json()
        status = data.get("processing_status", "UNKNOWN")
        progress = data.get("processing_progress", 0)
        msg = data.get("processing_message", "")

        if status in ("COMPLETED", "FAILED"):
            return status

        print(f"    [{status}] {progress}% — {msg[:80]}", end="\r", flush=True)
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Document {doc_id} did not finish within {timeout}s")


def delete_document(doc_id: int):
    """Clean up uploaded document after test."""
    try:
        requests.delete(
            f"{BASE_URL}/api/docs/{doc_id}/delete/",
            headers=auth_headers(),
            timeout=15,
        )
    except Exception:
        pass


def run_single(label: str, filepath: str) -> float:
    """Run one pipeline end-to-end, return elapsed seconds."""
    print(f"  Uploading {os.path.basename(filepath)}...")
    doc_id = upload_pdf(filepath)

    print(f"  Starting pipeline (doc_id={doc_id})...")
    t0 = time.time()
    start_pipeline(doc_id)
    final_status = poll_until_done(doc_id)
    elapsed = time.time() - t0
    print()  # clear \r line

    if final_status == "FAILED":
        print(f"  WARNING: pipeline FAILED for {label}")

    delete_document(doc_id)
    return elapsed


def main():
    results = {}  # label -> list of elapsed times

    for label, filepath in PDFS.items():
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            print(f"SKIP {label}: file not found at {filepath}")
            continue

        times = []
        for run in range(1, RUNS + 1):
            print(f"\n[{label.split(chr(10))[0]}] Run {run}/{RUNS}")
            try:
                elapsed = run_single(label, filepath)
                times.append(elapsed)
                print(f"  Done: {elapsed:.1f}s")
            except Exception as e:
                print(f"  ERROR: {e}")
                times.append(float("nan"))

        results[label] = times

    # ── Terminal table ──
    print("\n" + "=" * 70)
    print(f"{'Scenario':<35} {'Avg (s)':>8} {'Min (s)':>8} {'Max (s)':>8}")
    print("-" * 70)
    for label, times in results.items():
        clean = [t for t in times if t == t]  # filter NaN
        if not clean:
            print(f"{label.split(chr(10))[0]:<35} {'N/A':>8} {'N/A':>8} {'N/A':>8}")
            continue
        avg = sum(clean) / len(clean)
        mn, mx = min(clean), max(clean)
        print(f"{label.split(chr(10))[0]:<35} {avg:>8.1f} {mn:>8.1f} {mx:>8.1f}")
    print("=" * 70)

    # ── Chart ──
    labels = list(results.keys())
    avgs = []
    mins = []
    maxs = []
    for label in labels:
        clean = [t for t in results[label] if t == t]
        if clean:
            avgs.append(sum(clean) / len(clean))
            mins.append(min(clean))
            maxs.append(max(clean))
        else:
            avgs.append(0)
            mins.append(0)
            maxs.append(0)

    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(labels))
    bar_width = 0.5

    bars = ax.bar(x, avgs, bar_width, color="#4C72B0", edgecolor="white", zorder=3)

    # Error bars showing min/max range
    err_lower = [a - m for a, m in zip(avgs, mins)]
    err_upper = [m - a for a, m in zip(avgs, maxs)]
    ax.errorbar(x, avgs, yerr=[err_lower, err_upper],
                fmt="none", ecolor="black", capsize=5, zorder=4)

    # Value labels on bars
    for bar, avg_val in zip(bars, avgs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{avg_val:.1f}s", ha="center", va="bottom", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Processing Time (seconds)")
    ax.set_title("PDF Parser Pipeline — Processing Time by Document Size")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    fig.tight_layout()

    out_path = os.path.join(os.path.dirname(__file__), "perf_pdf_pipeline.png")
    fig.savefig(out_path, dpi=300)
    print(f"\nChart saved to {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
