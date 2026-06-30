"""Exit 0 iff the just-read detail body actually describes the requested job; else exit 1.

Called by read_details.sh right after a page read, so the reader can REJECT and re-fetch a page
that lost the SPA off-by-one race instead of saving a neighbouring job's description under the
wrong id. Usage: verify_one.py <RUN_DIR> <job_id> <body_file>
"""
import os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L

run, jid, body_file = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    raw = open(body_file, encoding="utf-8", errors="replace").read().strip()
    m = re.search(r"\{.*\}", raw, re.S)
    txt = json.loads(m.group(0)).get("txt", "") if m else ""
except Exception:
    sys.exit(1)

cands = {c["id"]: c for c in L.read_json(os.path.join(run, "candidates.json"))}
c = cands.get(jid)
if c is None:                       # unknown id -> cannot verify, accept (don't block)
    sys.exit(0)
sys.exit(0 if L.identity_in_text(c["company"], c["title"], txt) else 1)
