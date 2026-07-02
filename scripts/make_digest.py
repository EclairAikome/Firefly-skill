"""Phase 7 input - compact per-job digest for agent scoring.

A full JD corpus (~300 jobs x ~3k chars) cannot fit in an agent's context, so
scoring reads this digest instead: identity, ALL year-requirement clauses (the
floor alone hid a stacked '3+ yrs PM and 2+ yrs AI' requirement on 2026-07-02),
LinkedIn's structured criteria, keyword hits, and a requirements snippet.
Sorted by heuristic score so the agent reads the likeliest-High jobs first and
can re-read the full req in kept_candidates.json before granting >=85.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--snippet", type=int, default=420)
a = ap.parse_args()

kept = L.read_json(os.path.join(a.run, "kept_candidates.json"))


def snip(text, n):
    return re.sub(r"\s+", " ", text or "").strip()[:n]


rows = []
for k in sorted(kept, key=lambda x: -x.get("heuristic_score", 0)):
    clauses = k.get("years_clauses") or []
    rows.append({
        "jid": k["jid"], "co": k["company"], "t": k["title"],
        "loc": k["location"], "posted": k["posted"], "work": k["work"],
        "yrs": k.get("min_years"),
        "yrs_all": "; ".join(f"{y} ({e})" for y, e in clauses) if len(clauses) > 1 else "",
        "sen": k.get("seniority_label", ""), "emp": k.get("employment_type", ""),
        "cat": k["category_guess"], "ind": k.get("industry_guess", ""),
        "h": k.get("heuristic_score"), "kw": ",".join(k.get("kw_hits", [])[:10]),
        "req": snip(k.get("req", ""), a.snippet),
    })

out = os.path.join(a.run, "scoring_digest.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=0)
multi = sum(1 for r in rows if r["yrs_all"])
print(f"wrote {out} ({len(rows)} jobs; {multi} with stacked year clauses - "
      "read yrs_all before scoring those high)")
