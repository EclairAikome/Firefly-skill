"""S2 - apply the pre-build liveness re-check: drop kept jobs that died since the scrape.

Reads live_status.tsv (written by recheck_live.sh) and removes any kept job now 'closed' or
'removed', appending them to dropped.json with reason closed_at_build / removed_at_build. Run this
between recheck_live.sh and build_xlsx.py. 'unknown' / 'open' are kept (fail open: never drop a
job just because the re-ping was flaky — only drop on a POSITIVE dead signal).
"""
import argparse, os, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L
from lib_common import merge_dropped

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--out", default=None, help="filtered kept list (default: overwrite kept_candidates.json)")
a = ap.parse_args()
run = a.run
out = a.out or os.path.join(run, "kept_candidates.json")

status = {}
sp = os.path.join(run, "live_status.tsv")
if os.path.exists(sp):
    for line in open(sp, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 2:
            status[parts[0]] = parts[1].strip().lower()

kept = L.read_json(os.path.join(run, "kept_candidates.json"))
survivors, killed = [], []
for k in kept:
    st = status.get(k["jid"], "unknown")
    if st in ("closed", "removed"):
        killed.append({"jid": k["jid"], "company": k["company"], "title": k["title"],
                       "reason": f"{st}_at_build"})
    else:
        survivors.append(k)

L.write_json(survivors, out)
merge_dropped(run, "liveness", killed)

from collections import Counter
print(f"liveness re-check: kept {len(kept)} -> survivors {len(survivors)} "
      f"(dropped {len(killed)} dead: {dict(Counter(d['reason'] for d in killed))})")
for d in killed:
    print(f"  {d['reason']}  {d['jid']}  {d['company']} :: {d['title']}")
