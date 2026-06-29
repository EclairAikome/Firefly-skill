"""Print a concise run report (funnel + exclusion reasons + final shortlist)."""
import argparse, os, re, glob, json, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
a = ap.parse_args()
run = a.run


def maybe(path):
    return L.read_json(path) if os.path.exists(path) else None


agg = maybe(os.path.join(run, "agg_stats.json")) or {}
dropped = maybe(os.path.join(run, "dropped.json")) or []
kept = maybe(os.path.join(run, "kept_candidates.json")) or []
scores = maybe(os.path.join(run, "scores.json")) or {}
read_n = len(glob.glob(os.path.join(run, "details", "*.json")))

print("# LinkedIn Job Scout - run report\n")
print("## Funnel")
print(f"- Raw cards: {agg.get('raw_cards','?')}")
print(f"- Unique jobs: {agg.get('raw_unique','?')}")
print(f"- Excluded (already applied/seen): {agg.get('excluded_applied','?')}")
print(f"- Candidates after exclusion: {agg.get('candidates','?')}")
print(f"- Detail pages read: {read_n}")
print(f"- Kept after rule filter: {len(kept)}")

rc = Counter(re.split(r"[ (]", d["reason"])[0] for d in dropped)
print("\n## Dropped after reading JD")
for reason, n in rc.most_common():
    print(f"- {reason}: {n}")

print("\n## Kept shortlist")
def sc(k):
    s = scores.get(k["jid"])
    return int(s["score"]) if s else int(k.get("heuristic_score", 0))
for k in sorted(kept, key=sc, reverse=True):
    s = scores.get(k["jid"])
    tag = f'{s["fit"]}/{s["score"]}' if s else f'heur/{k.get("heuristic_score","?")}'
    print(f'- [{tag}] {k["company"]} :: {k["title"]} ({k["location"]})')
