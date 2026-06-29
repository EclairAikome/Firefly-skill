"""Build the already-applied / already-seen exclusion set.

Sources: the persistent master library (state/master_jobs.jsonl) plus any history files
in config.exclusion_sources (RESULTS.csv-style, with Company/Title/URL columns).
Dedupe key is the LinkedIn job id from the URL; normalized company+title is the backup.
"""
import argparse, os, re, csv, json, sys
sys.path.insert(0, os.path.dirname(__file__))
from lib_common import load_config, norm, write_json

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(SKILL_DIR, "state", "master_jobs.jsonl")

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--run", required=True)
a = ap.parse_args()
cfg = load_config(a.config)

ids, pairs = set(), set()

def add(company, title, url):
    m = re.search(r"(\d{6,})", url or "")
    if m:
        ids.add(m.group(1))
    pairs.add((norm(company), norm(title)))

# master library
if os.path.exists(MASTER):
    for line in open(MASTER, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("jid"):
            ids.add(str(o["jid"]))
        pairs.add((norm(o.get("company")), norm(o.get("title"))))

# history CSVs
for src in cfg.get("exclusion_sources", []) or []:
    if not os.path.exists(src):
        print(f"  (skip missing source: {src})")
        continue
    for row in csv.DictReader(open(src, encoding="utf-8", errors="replace")):
        g = {k.lstrip("﻿").strip().lower(): v for k, v in row.items()}
        add(g.get("company"), g.get("title"), g.get("url"))

write_json({"job_ids": sorted(ids), "pairs": sorted([list(p) for p in pairs])},
           os.path.join(a.run, "exclusion.json"))
print(f"exclusion set: {len(ids)} job ids, {len(pairs)} company+title pairs")
