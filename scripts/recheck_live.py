"""Phase 6.5 (S2) - conditional pre-build liveness re-ping of every KEPT job.

The re-ping exists to catch jobs that died between the scrape and the workbook
build. When the details were fetched minutes ago that window is empty, so this
script SKIPS itself unless the newest detail file is older than
pipeline.recheck_max_age_hours (default 4) - the 2026-07-02 run re-pinged 288
jobs less than an hour after fetching them and found all 288 still open.

Statuses go to live_status.tsv (id<TAB>open|closed|removed|unknown); fetch
errors map to unknown and apply_live_status.py fails open (only a positive
dead signal ever drops a job).
"""
import argparse, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L
import driver as drv

API = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
RE_CLOSED = re.compile(r"no longer accepting applications", re.I)

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--run", required=True)
ap.add_argument("--force", action="store_true", help="re-ping even if details are fresh")
ap.add_argument("--fresh", action="store_true", help="discard cached re-ping results first")
a = ap.parse_args()
cfg = L.load_config(a.config)
run = a.run
out_path = os.path.join(run, "live_status.tsv")

max_age_h = float((cfg.get("pipeline", {}) or {}).get("recheck_max_age_hours", 4))
det_dir = os.path.join(run, "details")
newest = 0.0
if os.path.isdir(det_dir):
    for fn in os.listdir(det_dir):
        newest = max(newest, os.path.getmtime(os.path.join(det_dir, fn)))
age_h = (time.time() - newest) / 3600 if newest else 999

if not a.force and age_h < max_age_h:
    if os.path.exists(out_path):
        os.remove(out_path)   # a stale tsv from an earlier pass must not be applied
    print(f"recheck SKIPPED: details are {age_h:.1f}h old (< {max_age_h}h); "
          "liveness = at-fetch. Use --force to re-ping anyway.")
    sys.exit(0)

kept = L.read_json(os.path.join(run, "kept_candidates.json"))
raw_path = os.path.join(run, "recheck_raw.jsonl")
if a.fresh and os.path.exists(raw_path):
    os.remove(raw_path)

tasks = [{"id": k["jid"], "url": API + k["jid"]} for k in kept]
which = drv.pick_driver(cfg)
interval = tuple((cfg.get("pipeline", {}) or {}).get("recheck_interval", [0.8, 1.4]))
print(f"recheck: pinging {len(tasks)} kept jobs (details {age_h:.1f}h old, driver={which})")
stats = drv.fetch_batch(tasks, raw_path, interval, which)
print(f"recheck fetch: {stats}")

status = {}
for line in open(raw_path, encoding="utf-8", errors="replace"):
    try:
        o = json.loads(line)
    except Exception:
        continue
    body = o.get("body", "")
    if o["status"] == "http_404":
        status[str(o["id"])] = "removed"
    elif o["status"] != "ok":
        status[str(o["id"])] = "unknown"
    elif RE_CLOSED.search(body):
        status[str(o["id"])] = "closed"
    elif "top-card-layout__title" in body:
        status[str(o["id"])] = "open"
    else:
        status[str(o["id"])] = "unknown"

with open(out_path, "w", encoding="utf-8") as f:
    for k in kept:
        f.write(f"{k['jid']}\t{status.get(k['jid'], 'unknown')}\n")
from collections import Counter
print(f"DONE recheck: {dict(Counter(status.values()))} -> {out_path}")
