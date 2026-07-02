"""Merge the agent's per-batch score files into scores.json and gate completeness.

Phase 7 protocol: the agent writes scores in batches as <RUN_DIR>/scores_p*.jsonl
(one JSON object per line, each with a "jid" plus fit/score/why/watch/category/
industry). Writing one giant scores.json in a single shot is error-prone at
~300 jobs; batched JSONL + this merger is the reliable path.

Exits non-zero if any kept job is unscored (or an unknown jid appears), so the
pipeline cannot build a workbook from a partial scoring pass. If no scores_p*
files exist, exits 0 quietly — the builder then falls back to the heuristic.
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
a = ap.parse_args()
run = a.run

parts = sorted(glob.glob(os.path.join(run, "scores_p*.jsonl")))
if not parts:
    print("merge_scores: no scores_p*.jsonl found; skipping (heuristic fallback will apply)")
    sys.exit(0)

scores, dupes = {}, []
for p in parts:
    for ln, line in enumerate(open(p, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception as e:
            print(f"merge_scores: BAD LINE {os.path.basename(p)}:{ln}: {e}")
            sys.exit(1)
        jid = str(o.pop("jid", ""))
        if not jid:
            print(f"merge_scores: missing jid at {os.path.basename(p)}:{ln}")
            sys.exit(1)
        if jid in scores:
            dupes.append(jid)
        scores[jid] = o

kept_ids = {k["jid"] for k in L.read_json(os.path.join(run, "kept_candidates.json"))}
missing = kept_ids - set(scores)
extra = set(scores) - kept_ids

L.write_json(scores, os.path.join(run, "scores.json"))

bands = {"High >=85": 0, "Medium-High 78-84": 0, "Medium <78": 0}
for s in scores.values():
    sc = int(s.get("score", 0))
    key = "High >=85" if sc >= 85 else ("Medium-High 78-84" if sc >= 78 else "Medium <78")
    bands[key] += 1

print(f"merged {len(scores)} from {len(parts)} part files | kept {len(kept_ids)} "
      f"| missing {len(missing)} | extra {len(extra)} | dupes {len(dupes)}")
for k, v in bands.items():
    print(f"  {k}: {v}")
if missing:
    kept = {k["jid"]: k for k in L.read_json(os.path.join(run, "kept_candidates.json"))}
    for jid in sorted(missing)[:20]:
        k = kept[jid]
        print(f"  MISSING: {jid} {k['company']} :: {k['title']}")
if dupes:
    print(f"  DUPES (last wins): {sorted(set(dupes))[:10]}")
sys.exit(1 if (missing or extra) else 0)
