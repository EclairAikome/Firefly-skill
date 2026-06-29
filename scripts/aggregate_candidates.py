"""Merge all per-query card files, dedupe, strip noise, remove already-applied/seen."""
import argparse, os, re, glob, json, sys
sys.path.insert(0, os.path.dirname(__file__))
from lib_common import norm, clean_title, read_json, write_json

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
                         "loc": (j.get("loc") or "").strip(), "src": [label]}
        else:
            cand[jid]["src"].append(label)

raw_unique = len(cand)
kept, excluded = {}, 0
for jid, c in cand.items():
    if jid in excl_ids or (norm(c["company"]), norm(c["title"])) in excl_pairs:
        excluded += 1
        continue
    kept[jid] = c

write_json(list(kept.values()), out)
write_json({"raw_cards": raw_cards, "raw_unique": raw_unique,
            "excluded_applied": excluded, "candidates": len(kept)},
           os.path.join(run, "agg_stats.json"))
print(f"cards {raw_cards} -> unique {raw_unique} -> excluded {excluded} -> candidates {len(kept)}")
