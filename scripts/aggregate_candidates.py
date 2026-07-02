"""Merge all per-query card files, dedupe, strip noise, remove already-applied/seen.

Two dedupe passes:
  1. by LinkedIn job id (same job surfaced by several queries)
  2. by normalized company+title (LinkedIn reposts the same role under a fresh id
     within days; keep the newest posting, drop the rest as duplicate_repost)
"""
import argparse, os, re, glob, json, sys
sys.path.insert(0, os.path.dirname(__file__))
from lib_common import norm, clean_title, read_json, write_json, merge_dropped

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--exclusion", default=None)
ap.add_argument("--out", default=None)
a = ap.parse_args()
run = a.run
excl_path = a.exclusion or os.path.join(run, "exclusion.json")
out = a.out or os.path.join(run, "candidates.json")

excl = read_json(excl_path)
excl_ids = set(excl["job_ids"])
excl_pairs = set(tuple(p) for p in excl["pairs"])

cand, raw_cards = {}, 0
for f in sorted(glob.glob(os.path.join(run, "cards", "*.json"))):
    label = os.path.basename(f)[:-5]
    raw = open(f, encoding="utf-8", errors="replace").read().strip()
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        continue
    try:
        arr = json.loads(m.group(0))
    except Exception:
        continue
    for j in arr:
        jid = j.get("id")
        if not jid:
            continue
        raw_cards += 1
        title = clean_title(j.get("title"))
        comp = (j.get("company") or "").strip()
        if jid not in cand:
            cand[jid] = {"id": jid, "title": title, "company": comp,
                         "loc": (j.get("loc") or "").strip(),
                         "posted_date": (j.get("posted_date") or "").strip(),
                         "src": [label]}
        else:
            cand[jid]["src"].append(label)

raw_unique = len(cand)

# pass 2: collapse same-company+title reposts, newest posting wins
# (posted_date from the guest card's <time datetime>; falls back to the numeric id,
# which LinkedIn assigns roughly monotonically)
by_pair = {}
for c in cand.values():
    by_pair.setdefault((norm(c["company"]), norm(c["title"])), []).append(c)

deduped, repost_dropped = {}, []
for (nc, nt), group in by_pair.items():
    if len(group) == 1 or not nc or not nt:   # blank keys never collapse
        for c in group:
            deduped[c["id"]] = c
        continue
    group.sort(key=lambda c: (c.get("posted_date") or "", int(c["id"])), reverse=True)
    deduped[group[0]["id"]] = group[0]
    for c in group[1:]:
        repost_dropped.append({"jid": c["id"], "company": c["company"], "title": c["title"],
                               "reason": "duplicate_repost", "kept_as": group[0]["id"]})

kept, excluded = {}, 0
for jid, c in deduped.items():
    if jid in excl_ids or (norm(c["company"]), norm(c["title"])) in excl_pairs:
        excluded += 1
        continue
    kept[jid] = c

write_json(list(kept.values()), out)
merge_dropped(run, "aggregate", repost_dropped)
write_json({"raw_cards": raw_cards, "raw_unique": raw_unique,
            "duplicate_reposts": len(repost_dropped),
            "excluded_applied": excluded, "candidates": len(kept)},
           os.path.join(run, "agg_stats.json"))
print(f"cards {raw_cards} -> unique {raw_unique} -> reposts {len(repost_dropped)} "
      f"-> excluded {excluded} -> candidates {len(kept)}")
