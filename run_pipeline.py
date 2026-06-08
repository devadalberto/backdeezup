#!/usr/bin/env python3
"""
BackDeezUp pipeline runner with tqdm progress bars.
Usage:
    python3 run_pipeline.py              # Drive pipeline
    python3 run_pipeline.py gmail        # Gmail pipeline
    python3 run_pipeline.py all          # Drive + Gmail
    python3 run_pipeline.py --limit 250  # custom batch size
"""
import sys
import time
import argparse
import requests
from tqdm import tqdm

BASE = "http://localhost:8844"


def post(path, params=None):
    try:
        r = requests.post(f"{BASE}{path}", params=params, timeout=360)
        return r.json() if r.ok else {}
    except Exception as e:
        return {"error": str(e)}


def get(path, params=None):
    try:
        r = requests.get(f"{BASE}{path}", params=params, timeout=30)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def run_drive(limit=100):
    print("\nDrive pipeline")
    prog = get("/api/progress")
    total = prog.get("total", 0)
    if not total:
        print("  No assets found. Run: make discover first.")
        return

    with tqdm(total=total, initial=prog.get("done", 0),
              desc="  verified", unit="file", dynamic_ncols=True) as bar:
        while True:
            r = post("/api/sync/download", {"limit": limit})
            r2 = post("/api/sync/import", {"limit": limit})
            r3 = post("/api/sync/verify", {"limit": limit})
            dl = r.get("downloaded", 0)
            imp = r2.get("imported", 0)
            ver = r3.get("verified", 0)
            bar.update(ver)
            bar.set_postfix(dl=dl, imp=imp, ver=ver)
            if dl == 0 and imp == 0 and ver == 0:
                break

    prog = get("/api/progress")
    print(f"  Drive complete: {prog.get('done')}/{prog.get('total')} ({prog.get('pct')}%)")


def run_gmail(limit=100):
    print("\nGmail pipeline")
    prog = get("/api/gmail/progress")
    total = prog.get("total", 0)
    if not total:
        print("  No messages found. Run: make gmail-discover first.")
        return

    with tqdm(total=total, initial=prog.get("verified", 0),
              desc="  verified", unit="msg", dynamic_ncols=True) as bar:
        while True:
            r = post("/api/gmail/sync/download", {"limit": limit})
            r2 = post("/api/gmail/sync/verify", {"limit": limit})
            dl = r.get("downloaded", 0)
            ver = r2.get("verified", 0)
            bar.update(ver)
            bar.set_postfix(dl=dl, ver=ver)
            if dl == 0 and ver == 0:
                break

    prog = get("/api/gmail/progress")
    print(f"  Gmail complete: {prog.get('verified')}/{prog.get('total')} ({prog.get('pct')}%)")


def main():
    parser = argparse.ArgumentParser(description="BackDeezUp pipeline runner")
    parser.add_argument("target", nargs="?", default="drive",
                        choices=["drive", "gmail", "all"],
                        help="Which pipeline to run (default: drive)")
    parser.add_argument("--limit", type=int, default=100,
                        help="Batch size per API call (default: 100)")
    args = parser.parse_args()

    if args.target in ("drive", "all"):
        run_drive(args.limit)
    if args.target in ("gmail", "all"):
        run_gmail(args.limit)


if __name__ == "__main__":
    main()
