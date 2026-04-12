"""
Performance test for the document processing pipeline.

Usage:
    python scripts/perf_test_pipeline.py --doc-ids 1 2 3
    python scripts/perf_test_pipeline.py --doc-ids 1 --reprocess
    python scripts/perf_test_pipeline.py --list-docs          # list available documents

Requires the Django server to be running and the .env file to be configured.
"""

import argparse
import os
import sys
import time
import statistics
import threading
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

BASE_URL = os.getenv("PERF_BASE_URL", "http://127.0.0.1:8000/api")
USERNAME = os.getenv("PERF_USERNAME", "")
PASSWORD = os.getenv("PERF_PASSWORD", "")

POLL_INTERVAL   = 3     # seconds between status polls
POLL_TIMEOUT    = 600   # max seconds to wait for a document to finish

# Status messages emitted during the pipeline – used to detect phase transitions
PHASE_KEYWORDS = {
    "toc":       "Parsing document structure",
    "chunking":  "Chunking document content",
    "embedding": "Generating embeddings",
    "semantic":  "Computing semantic similarities",
    "completed": "completed successfully",
    "failed":    "failed",
}

# ─── Auth ────────────────────────────────────────────────────────────────────

def get_token(session: requests.Session) -> str:
    """Obtain a JWT access token."""
    if not USERNAME or not PASSWORD:
        print("[WARN] PERF_USERNAME / PERF_PASSWORD not set in .env – trying without auth.")
        return ""

    resp = session.post(
        f"{BASE_URL}/token/",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("access", "")
    print(f"[AUTH] Logged in as '{USERNAME}'")
    return token


def auth_headers(token: str) -> dict:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def list_documents(session: requests.Session, token: str):
    """Print all documents and their current processing status."""
    resp = session.get(
        f"{BASE_URL}/content_ingestion/docs/",
        headers=auth_headers(token),
        timeout=10,
    )
    resp.raise_for_status()
    docs = resp.json()

    if isinstance(docs, dict):
        docs = docs.get("results", docs.get("documents", []))

    print(f"\n{'ID':>5}  {'Status':<12}  Title")
    print("-" * 60)
    for d in docs:
        print(f"{d['id']:>5}  {d.get('processing_status', '?'):<12}  {d.get('title', '?')}")
    print()


def get_doc_status(session: requests.Session, token: str, doc_id: int) -> dict:
    resp = session.get(
        f"{BASE_URL}/content_ingestion/docs/{doc_id}/status/",
        headers=auth_headers(token),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def trigger_pipeline(session: requests.Session, token: str, doc_id: int, reprocess: bool) -> float:
    """POST to start the pipeline. Returns the timestamp of the trigger."""
    t = time.perf_counter()
    resp = session.post(
        f"{BASE_URL}/content_ingestion/pipeline/{doc_id}/",
        json={"reprocess": reprocess},
        headers=auth_headers(token),
        timeout=10,
    )
    elapsed = time.perf_counter() - t

    if resp.status_code == 202:
        print(f"  [DOC {doc_id}] Pipeline triggered  (POST took {elapsed*1000:.1f} ms)")
    else:
        print(f"  [DOC {doc_id}] Unexpected status {resp.status_code}: {resp.text}")
        resp.raise_for_status()

    return elapsed


# ─── Single-document runner ───────────────────────────────────────────────────

def run_single(session: requests.Session, token: str, doc_id: int, reprocess: bool) -> dict:
    """
    Trigger the pipeline for one document and poll until done.
    Returns a dict with timing/result info.
    """
    result = {
        "doc_id":        doc_id,
        "reprocess":     reprocess,
        "post_ms":       0.0,
        "total_s":       0.0,
        "final_status":  "UNKNOWN",
        "final_message": "",
        "phase_times":   {},   # phase_name -> elapsed seconds when we first saw it
        "polls":         0,
        "error":         None,
    }

    try:
        post_elapsed = trigger_pipeline(session, token, doc_id, reprocess)
        result["post_ms"] = post_elapsed * 1000
    except Exception as exc:
        result["error"] = str(exc)
        return result

    wall_start     = time.perf_counter()
    seen_phases    = set()
    last_message   = ""

    for _ in range(POLL_TIMEOUT // POLL_INTERVAL + 1):
        time.sleep(POLL_INTERVAL)
        result["polls"] += 1

        try:
            data = get_doc_status(session, token, doc_id)
        except Exception as exc:
            print(f"  [DOC {doc_id}] Poll error: {exc}")
            continue

        status_val = data.get("processing_status", "")
        message    = data.get("processing_message", "")
        elapsed    = time.perf_counter() - wall_start

        # detect phase transitions
        if message != last_message:
            last_message = message
            for phase, keyword in PHASE_KEYWORDS.items():
                if keyword.lower() in message.lower() and phase not in seen_phases:
                    seen_phases.add(phase)
                    result["phase_times"][phase] = round(elapsed, 2)
                    print(f"  [DOC {doc_id}] Phase '{phase}' @ {elapsed:.1f}s  — {message}")

        if status_val in ("COMPLETED", "FAILED"):
            result["total_s"]       = round(elapsed, 2)
            result["final_status"]  = status_val
            result["final_message"] = message
            break
    else:
        result["final_status"]  = "TIMEOUT"
        result["final_message"] = f"Did not finish within {POLL_TIMEOUT}s"
        result["total_s"]       = round(time.perf_counter() - wall_start, 2)

    return result


# ─── Concurrent runner ────────────────────────────────────────────────────────

def run_concurrent(doc_ids: list, reprocess: bool, token: str) -> list:
    """Trigger all documents at the same time and collect results."""
    results = [None] * len(doc_ids)
    threads = []

    def worker(idx, doc_id):
        # each thread gets its own session
        s = requests.Session()
        results[idx] = run_single(s, token, doc_id, reprocess)

    for i, doc_id in enumerate(doc_ids):
        t = threading.Thread(target=worker, args=(i, doc_id), daemon=True)
        threads.append(t)

    start_wall = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_wall = round(time.perf_counter() - start_wall, 2)
    return results, total_wall


# ─── Report ───────────────────────────────────────────────────────────────────

def print_report(results: list, total_wall: float = None):
    print("\n" + "=" * 65)
    print("PERFORMANCE TEST REPORT")
    print(f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if total_wall is not None:
        print(f"Wall time : {total_wall:.2f}s  (all documents, concurrent)")
    print("=" * 65)

    for r in results:
        if r is None:
            continue
        doc_id = r["doc_id"]
        print(f"\n  Document #{doc_id}")
        print(f"    POST response time : {r['post_ms']:.1f} ms")
        print(f"    Final status       : {r['final_status']}")
        print(f"    Total pipeline     : {r['total_s']}s")
        print(f"    Status polls       : {r['polls']}")
        if r["phase_times"]:
            print(f"    Phase breakdown    :")
            prev = 0.0
            for phase, t in r["phase_times"].items():
                duration = round(t - prev, 2)
                print(f"       {phase:<12} starts @ {t:>6.1f}s   (Δ {duration:.2f}s from prev phase)")
                prev = t
        if r["final_message"]:
            print(f"    Message            : {r['final_message']}")
        if r["error"]:
            print(f"    Error              : {r['error']}")

    # aggregate stats if more than one doc
    completed = [r for r in results if r and r["final_status"] == "COMPLETED"]
    if len(completed) > 1:
        times = [r["total_s"] for r in completed]
        print(f"\n  Aggregate ({len(completed)} completed docs):")
        print(f"    Min  : {min(times):.2f}s")
        print(f"    Max  : {max(times):.2f}s")
        print(f"    Mean : {statistics.mean(times):.2f}s")
        print(f"    Stdev: {statistics.stdev(times):.2f}s")

    print("\n" + "=" * 65 + "\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pipeline performance tester")
    parser.add_argument(
        "--doc-ids", nargs="+", type=int, metavar="ID",
        help="Document IDs to run through the pipeline",
    )
    parser.add_argument(
        "--reprocess", action="store_true",
        help="Pass reprocess=true to clear and redo existing results",
    )
    parser.add_argument(
        "--list-docs", action="store_true",
        help="List all documents and exit",
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Run documents one-by-one instead of concurrently (default: concurrent)",
    )
    args = parser.parse_args()

    session = requests.Session()

    try:
        token = get_token(session)
    except Exception as exc:
        print(f"[ERROR] Auth failed: {exc}")
        sys.exit(1)

    if args.list_docs:
        list_documents(session, token)
        return

    if not args.doc_ids:
        parser.print_help()
        print("\n[INFO] Use --list-docs to see available document IDs.\n")
        sys.exit(0)

    print(f"\nTargeting {len(args.doc_ids)} document(s): {args.doc_ids}")
    print(f"Reprocess : {args.reprocess}")
    print(f"Mode      : {'sequential' if args.sequential else 'concurrent'}\n")

    if args.sequential or len(args.doc_ids) == 1:
        results = []
        for doc_id in args.doc_ids:
            results.append(run_single(session, token, doc_id, args.reprocess))
        print_report(results)
    else:
        results, total_wall = run_concurrent(args.doc_ids, args.reprocess, token)
        print_report(results, total_wall)


if __name__ == "__main__":
    main()
