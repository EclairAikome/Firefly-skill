"""Emit LinkedIn search URLs (one per query) from config, for search.sh to drive."""
import argparse, os, re, urllib.parse, sys
sys.path.insert(0, os.path.dirname(__file__))
from lib_common import load_config

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--run", required=True)
a = ap.parse_args()
cfg = load_config(a.config)
s = cfg["search"]
os.makedirs(a.run, exist_ok=True)

base = "https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&geoId={geo}&f_E={exp}&f_TPR={tpr}&sortBy={sort}"
lines = []
for q in s["queries"]:
    label = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
    url = base.format(
        kw=urllib.parse.quote(q),
        loc=urllib.parse.quote(s.get("location_label", "Singapore")),
        geo=s["geo_id"], exp=urllib.parse.quote(str(s["experience"])),
        tpr=s["recency"], sort=s.get("sort", "DD"))
    lines.append(f"{label}\t{url}")

with open(os.path.join(a.run, "search_urls.tsv"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
with open(os.path.join(a.run, "scroll_rounds.txt"), "w", encoding="utf-8") as f:
    f.write(str(int(s.get("scroll_rounds", 2))))
print(f"wrote {len(lines)} search urls to {a.run}\\search_urls.tsv")
