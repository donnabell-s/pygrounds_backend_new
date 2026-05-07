"""
Performance Test: PDF Parser Pipeline
======================================
Times the 3 core steps (TOC extraction → chunking → embedding) per PDF.
Calls each step's individual API endpoint and measures wall-clock time.

Outputs:
  - Terminal table with per-step + total times in minutes
  - perf_pdf_pipeline.png chart (300 DPI)
"""
import os
import sys
import time

import requests
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from auth_helper import BASE_URL, auth_headers

RUNS = 1

PDFS = {
    "Small (~1.3 MB)\npython_intermediate": os.path.join(
        os.path.dirname(__file__), "..", "pdfs", "python_intermediate.pdf"
    ),
    "Medium (~6.5 MB)\nPython Basics": os.path.join(
        os.path.dirname(__file__), "..", "pdfs",
        "Python_Basics_A_Practical_Introduction_To_Python_3.pdf",
    ),
    "Medium-Large (~7.0 MB)\nExpert Python": os.path.join(
        os.path.dirname(__file__), "..", "pdfs", "expert_python.pdf"
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


def run_toc(doc_id: int) -> float:
    """Run TOC extraction, return elapsed minutes."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/toc/{doc_id}/generate/",
        headers=auth_headers(),
        timeout=600,
    )
    elapsed = time.time() - t0
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"TOC failed: {resp.status_code} {resp.text[:300]}")
    return elapsed / 60.0


def run_chunking(doc_id: int) -> float:
    """Run chunking, return elapsed minutes."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/pipeline/{doc_id}/chunks/",
        headers=auth_headers(),
        timeout=600,
    )
    elapsed = time.time() - t0
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Chunking failed: {resp.status_code} {resp.text[:300]}")
    return elapsed / 60.0


def run_embedding(doc_id: int) -> float:
    """Run embedding generation, return elapsed minutes."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/pipeline/{doc_id}/embeddings/",
        headers=auth_headers(),
        timeout=600,
    )
    elapsed = time.time() - t0
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Embedding failed: {resp.status_code} {resp.text[:300]}")
    return elapsed / 60.0


def delete_document(doc_id: int):
    """Hard-delete document and ALL related data (TOC, chunks, embeddings)."""
    try:
        requests.delete(
            f"{BASE_URL}/api/docs/{doc_id}/delete/?hard_delete=true",
            headers=auth_headers(),
            timeout=30,
        )
    except Exception:
        pass


def run_single(label: str, filepath: str) -> dict:
    """Run one pipeline end-to-end, return per-step timing dict (all in minutes)."""
    print(f"  Uploading {os.path.basename(filepath)}...")
    doc_id = upload_pdf(filepath)

    print(f"  Step 1/3 — TOC extraction...   ", end="", flush=True)
    toc_m = run_toc(doc_id)
    print(f"{toc_m*60:.0f}s")

    print(f"  Step 2/3 — Chunking...          ", end="", flush=True)
    chunk_m = run_chunking(doc_id)
    print(f"{chunk_m*60:.0f}s")

    print(f"  Step 3/3 — Embedding...         ", end="", flush=True)
    embed_m = run_embedding(doc_id)
    print(f"{embed_m*60:.0f}s")

    total = toc_m + chunk_m + embed_m
    print(f"  Total: {total:.2f} min ({total*60:.0f}s)")

    delete_document(doc_id)
    return {"toc": toc_m, "chunking": chunk_m, "embedding": embed_m, "total": total}


def main():
    results = {}  # label -> list of dicts with toc/chunking/embedding/total

    for label, filepath in PDFS.items():
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            print(f"SKIP {label}: file not found at {filepath}")
            continue

        runs = []
        for run in range(1, RUNS + 1):
            print(f"\n[{label.split(chr(10))[0]}] Run {run}/{RUNS}")
            try:
                timings = run_single(label, filepath)
                runs.append(timings)
            except Exception as e:
                print(f"  ERROR: {e}")

        results[label] = runs

    # ── Terminal table (per-step + total in minutes) ──
    print("\n" + "=" * 95)
    header = f"{'PDF':<30} {'TOC':>7} {'Chunk':>7} {'Embed':>7} {'Total':>7} {'Total':>8}"
    print(header)
    header2 = f"{'':<30} {'(min)':>7} {'(min)':>7} {'(min)':>7} {'(min)':>7} {'(s)':>8}"
    print(header2)
    print("-" * 95)
    for label, runs in results.items():
        pdf_short = label.split(chr(10))[0]
        if runs:
            r = runs[0]  # single run
            total_s = r["total"] * 60
            print(f"{pdf_short:<30} {r['toc']:>7.2f} {r['chunking']:>7.2f} {r['embedding']:>7.2f} {r['total']:>7.2f} {total_s:>8.0f}")
        else:
            print(f"{pdf_short:<30} {'N/A':>7} {'N/A':>7} {'N/A':>7} {'N/A':>7} {'N/A':>8}")
    print("=" * 95)

    # ── Chart: total time per PDF in minutes ──
    labels = [l.split(chr(10))[0] for l in results.keys()]
    totals_m = []
    for runs in results.values():
        totals_m.append(runs[0]["total"] if runs else 0)

    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(labels))
    bars = ax.bar(x, totals_m, 0.5, color="#4C72B0", edgecolor="white", zorder=3)

    for bar, val in zip(bars, totals_m):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{val:.1f} min", ha="center", va="bottom", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Total Processing Time (minutes)")
    ax.set_title("PDF Parser Pipeline — TOC + Chunking + Embedding Time")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    fig.tight_layout()

    out_path = os.path.join(os.path.dirname(__file__), "perf_pdf_pipeline.png")
    fig.savefig(out_path, dpi=300)
    print(f"\nChart saved to {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
