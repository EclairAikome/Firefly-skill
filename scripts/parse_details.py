"""Parse every candidate's detail page, apply the hard rules, split kept vs dropped.

Hard rules (see references/filter_rules.md):
  - minimum required experience >= filters.max_years_exclusive  -> drop (years)
  - filters.require_singapore and not Singapore base/business    -> drop (location)
  - filters.drop_direct_sales_mlm and MLM/direct-sales pattern   -> drop (mlm)
Kept jobs carry extracted jd/req/location/posted/work + a heuristic score for fallback.
"""
import argparse, os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--run", required=True)
ap.add_argument("--out", default=None)
a = ap.parse_args()
cfg = L.load_config(a.config)
run = a.run
out = a.out or os.path.join(run, "kept_candidates.json")
filt = cfg.get("filters", {})
maxy = int(filt.get("max_years_exclusive", 3))
req_sg = bool(filt.get("require_singapore", True))
drop_mlm = bool(filt.get("drop_direct_sales_mlm", True))

all_kw = []
for t in (cfg.get("profile", {}).get("tracks", {}) or {}).values():
    all_kw += t.get("keywords", [])


def load_txt(jid):
    p = os.path.join(run, "details", jid + ".json")
    if not os.path.exists(p):
        return ""
    raw = open(p, encoding="utf-8", errors="replace").read().strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return ""
    try:
        return json.loads(m.group(0)).get("txt", "")
    except Exception:
        return ""


def jd_and_req(txt):
    i = txt.find("About the job")
    body = txt[i + 13:] if i >= 0 else txt
    body = re.sub(r"\n{2,}", "\n", body).strip()
    # Cut the trailing LinkedIn chrome (similar jobs, alerts, "see less" remnants) so the JD
    # column holds the real description and nothing else.
    for marker in ("People you can reach", "Set alert", "How you match", "See how you compare",
                   "About the company", "More jobs", "Show more", "Set alert for similar jobs",
                   "… more", "I’m interested", "I'm interested"):
        j = body.find(marker)
        if j > 200:
            body = body[:j]
    body = re.sub(r"[ \t]+", " ", body).strip()
    # Store the FULL description and FULL requirements (no artificial char cap that used to clip
    # them mid-word). Excel's per-cell limit is 32767; 20000 is a safe ceiling for a real JD.
    CAP = 20000
    jd = body[:CAP]
    mm = re.search(r"(Requirements|Qualifications|What (you|we)[^\n]{0,20}|Who you are|You have|Minimum)", body, re.I)
    req = body[mm.start():mm.start() + CAP] if mm else jd[:1500]
    return jd, re.sub(r"[ \t]+", " ", req).strip()


def guess_category(title):
    t = (title or "").lower()
    if "product manager" in t or "product associate" in t or "product management" in t:
        return "Product Manager"
    if "product marketing" in t:
        return "Product Marketing"
    if "content" in t or "creator" in t:
        return "Content / Social"
    if "social" in t:
        return "Social / Strategy"
    if "influencer" in t or "partnership" in t or "affiliate" in t:
        return "Influencer / Partnerships"
    if "community" in t:
        return "Community / Marketing"
    if "pr" in t or "communications" in t:
        return "PR / Communications"
    return "Digital Marketing"


cands = {c["id"]: c for c in L.read_json(os.path.join(run, "candidates.json"))}
kept, dropped = [], []
for jid, c in cands.items():
    txt = load_txt(jid)
    if not txt:
        dropped.append({"jid": jid, "company": c["company"], "title": c["title"], "reason": "no_detail"})
        continue
    miny, ev = L.min_required_years(txt)
    sg = L.is_singapore(c.get("loc", ""), c["title"], txt)
    mlm = L.is_direct_sales_mlm(c["company"], c["title"], txt)
    reason = None
    if miny is not None and miny >= maxy:
        reason = f"years>={maxy} ({ev})"
    elif L.is_senior_title(c["title"]):
        reason = "senior_title"
    elif req_sg and not sg:
        reason = "not_singapore"
    elif drop_mlm and mlm:
        reason = "direct_sales_mlm"
    if reason:
        dropped.append({"jid": jid, "company": c["company"], "title": c["title"], "reason": reason})
        continue
    _, pstr = L.rel_to_abs_date(L.loc_line(txt))
    jd, rq = jd_and_req(txt)
    hscore, hits = L.keyword_overlap_score(jd, rq, all_kw)
    kept.append({
        "jid": jid, "company": c["company"], "title": c["title"],
        "location": L.clean_loc(c.get("loc", "")), "work": L.work_mode(c.get("loc", "")),
        "posted": pstr, "link": f"https://www.linkedin.com/jobs/view/{jid}/",
        "jd": jd, "req": rq, "min_years": miny,
        "category_guess": guess_category(c["title"]),
        "heuristic_score": hscore, "kw_hits": hits,
    })

L.write_json(kept, out)
L.write_json(dropped, os.path.join(run, "dropped.json"))
from collections import Counter
rc = Counter(re.split(r"[ (]", d["reason"])[0] for d in dropped)
print(f"read {len(cands)} -> kept {len(kept)} -> dropped {len(dropped)} {dict(rc)}")
