"""Write the run report (funnel + drops + top matches + caution list) to
<RUN_DIR>/report.md, echo it to stdout, and copy it next to the workbook when
--config is given. The caution list surfaces what a reader must not miss:
suspected direct-sales posts, hard language/citizenship gates, and reposts."""
import argparse, os, re, glob, json, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--config", default=None)
a = ap.parse_args()
run = a.run


def maybe(path):
    return L.read_json(path) if os.path.exists(path) else None


agg = maybe(os.path.join(run, "agg_stats.json")) or {}
dropped = maybe(os.path.join(run, "dropped.json")) or []
kept = maybe(os.path.join(run, "kept_candidates.json")) or []
scores = maybe(os.path.join(run, "scores.json")) or {}
read_n = len(glob.glob(os.path.join(run, "details", "*.json")))


def sc(k):
    s = scores.get(k["jid"])
    return int(s["score"]) if s else int(k.get("heuristic_score", 0))


def fit(k):
    s = scores.get(k["jid"])
    return s.get("fit", "?") if s else "heur"


def watch(k):
    s = scores.get(k["jid"])
    return (s or {}).get("watch", "")


ranked = sorted(kept, key=sc, reverse=True)
rc = Counter(re.split(r"[ (]", d["reason"])[0] for d in dropped)
high = [k for k in ranked if sc(k) >= 85]

lines = []
w = lines.append
w("# LinkedIn Job Scout - run report\n")
w("## Funnel")
w(f"- Raw cards: {agg.get('raw_cards', '?')}")
w(f"- Unique jobs: {agg.get('raw_unique', '?')}")
if agg.get("duplicate_reposts"):
    w(f"- Same-role reposts collapsed: {agg['duplicate_reposts']}")
w(f"- Excluded (already applied/seen): {agg.get('excluded_applied', '?')}")
w(f"- Candidates after exclusion: {agg.get('candidates', '?')}")
w(f"- Detail pages read: {read_n}")
w(f"- Kept after rule filter: {len(kept)}")

w("\n## Dropped (all stages)")
for reason, n in rc.most_common():
    w(f"- {reason}: {n}")

if high:
    w(f"\n## Top matches (score >= 85: {len(high)})")
    w("| Score | Fit | Company | Title |")
    w("|---|---|---|---|")
    for k in high[:20]:
        w(f"| {sc(k)} | {fit(k)} | {k['company']} | {k['title']} |")

cautions = [k for k in ranked
            if sc(k) < 60 or re.search(r"skip|suspect|verify|only|required -", watch(k), re.I)]
if cautions:
    w(f"\n## Caution list ({len(cautions)}) - read Watch-outs before applying")
    for k in cautions[:15]:
        w(f"- [{sc(k)}] {k['company']} :: {k['title']} - {watch(k) or 'low score'}")

w("\n## Kept shortlist")
for k in ranked:
    s = scores.get(k["jid"])
    tag = f'{s["fit"]}/{s["score"]}' if s else f'heur/{k.get("heuristic_score", "?")}'
    w(f"- [{tag}] {k['company']} :: {k['title']} ({k['location']})")

report = "\n".join(lines) + "\n"
out_md = os.path.join(run, "report.md")
with open(out_md, "w", encoding="utf-8") as f:
    f.write(report)
print(report)
print(f"(saved {out_md})")

if a.config:
    cfg = L.load_config(a.config)
    outdir = (cfg.get("output", {}) or {}).get("dir")
    if outdir and os.path.isdir(outdir):
        import datetime, shutil
        dest = os.path.join(outdir, f"scrape-report-{datetime.date.today().isoformat()}.md")
        shutil.copyfile(out_md, dest)
        print(f"(copied to {dest})")
