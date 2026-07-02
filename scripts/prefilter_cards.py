"""Phase 4.5 - card-level prefilter, applied BEFORE the detail fetch.

Some hard rules need only the card (title/loc), not the JD: a senior title is a
senior title whatever the description says, and a clearly foreign-tagged card
won't turn Singaporean. Applying them here skips their detail fetches entirely
(the guest f_E filter is loose, so senior roles are ~10% of candidates).

Drops are recorded in dropped.json (stage=prefilter) with the SAME reason strings
parse_details uses, so the Summary's exclusion table stays a single funnel.
candidates.json is rewritten in place; re-running is a no-op.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L
from lib_common import merge_dropped

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--run", required=True)
a = ap.parse_args()
cfg = L.load_config(a.config)
req_sg = bool(cfg.get("filters", {}).get("require_singapore", True))

path = os.path.join(a.run, "candidates.json")
cands = L.read_json(path)

kept, dropped = [], []
for c in cands:
    if L.is_senior_title(c["title"]):
        dropped.append({"jid": c["id"], "company": c["company"], "title": c["title"],
                        "reason": "senior_title"})
    elif req_sg and L.is_foreign_card(c.get("loc", ""), c["title"]):
        dropped.append({"jid": c["id"], "company": c["company"], "title": c["title"],
                        "reason": "not_singapore"})
    else:
        kept.append(c)

L.write_json(kept, path)
merge_dropped(a.run, "prefilter", dropped)
from collections import Counter
rc = Counter(d["reason"] for d in dropped)
print(f"prefilter: {len(cands)} -> {len(kept)} (dropped {len(dropped)} {dict(rc)})")
