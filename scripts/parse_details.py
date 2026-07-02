"""Parse every candidate's detail file, apply the hard rules, split kept vs dropped.

Hard rules (see references/filter_rules.md):
  - minimum required experience >= filters.max_years_exclusive  -> drop (years)
  - filters.require_singapore and not Singapore base/business    -> drop (location)
  - filters.drop_direct_sales_mlm and MLM/direct-sales pattern   -> drop (mlm)
Kept jobs carry extracted jd/req/location/posted/work, LinkedIn's structured
criteria, ALL year-requirement clauses (not just the floor - Phase 7 needs the
full list to catch stacked requirements), and a heuristic score for fallback.
"""
import argparse, os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L
from lib_common import merge_dropped

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
drop_contract = bool(filt.get("drop_contract", False))
drop_part = bool(filt.get("drop_part_time", False))
drop_removed = bool(filt.get("drop_removed", True))      # S1: page gone / 404 placeholder
drop_closed = bool(filt.get("drop_closed", True))        # S1: "no longer accepting applications"
fast_close_h = int(filt.get("fast_close_hours", 48))     # S3: closed within this many hours = ghost
bl_companies = filt.get("blacklist_companies", []) or []  # hard-drop these employers outright
bl_titles = filt.get("blacklist_titles", []) or []        # hard-drop these title patterns outright

all_kw = []
for t in (cfg.get("profile", {}).get("tracks", {}) or {}).values():
    all_kw += t.get("keywords", [])


def load_detail(jid):
    """Return (txt, criteria) from the detail file, tolerating extractor noise."""
    p = os.path.join(run, "details", jid + ".json")
    if not os.path.exists(p):
        return "", {}
    raw = open(p, encoding="utf-8", errors="replace").read().strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return "", {}
    try:
        obj = json.loads(m.group(0))
        return obj.get("txt", ""), obj.get("criteria") or {}
    except Exception:
        return "", {}


# Requirements-block headings, matched at LINE START so the block begins at the
# heading instead of mid-sentence (74/288 rows started lowercase mid-clause on
# the 2026-07-02 run before this).
_REQ_HEADING = re.compile(
    r"(?im)^(requirements?|qualifications?|minimum qualifications?|"
    r"what you(?:'|’)?ll need|what you need( to succeed)?|who you are|"
    r"what we(?:'|’)re looking for|you (?:will )?bring|must[- ]haves?)\b")
_REQ_INLINE = re.compile(
    r"(Requirements|Qualifications|What (you|we)[^\n]{0,20}|Who you are|You have|Minimum)", re.I)


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
    # Store the FULL description and FULL requirements. Excel's per-cell limit is
    # 32767; 20000 is a safe ceiling for a real JD.
    CAP = 20000
    jd = body[:CAP]
    m = _REQ_HEADING.search(body)
    if m:
        return jd, re.sub(r"[ \t]+", " ", body[m.start():m.start() + CAP]).strip(), "heading"
    mm = _REQ_INLINE.search(body)
    if mm:
        start = body.rfind("\n", 0, mm.start()) + 1   # align to the start of the line
        return jd, re.sub(r"[ \t]+", " ", body[start:start + CAP]).strip(), "inline"
    return jd, jd[:1500], "jd_head"


def guess_category(title, criteria):
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
    if "analyst" in t or "analytics" in t or "data" in t:
        return "Data / BI Analyst"
    # whole-word "pr" — the old substring test classified "April ..." as PR
    if "pr" in t.split() or "public relations" in t or "communications" in t:
        return "PR / Communications"
    # LinkedIn's own Job function is a decent tiebreaker when the title says little
    fn = (criteria.get("Job function") or "").lower()
    if "product management" in fn:
        return "Product Manager"
    if "analyst" in fn or "information technology" in fn:
        return "Data / BI Analyst"
    return "Digital Marketing"


cands = {c["id"]: c for c in L.read_json(os.path.join(run, "candidates.json"))}
kept, dropped = [], []
for jid, c in cands.items():
    txt, crit = load_detail(jid)
    if not txt:
        dropped.append({"jid": jid, "company": c["company"], "title": c["title"], "reason": "no_detail"})
        continue
    # Defense in depth against a wrong-body read: if the saved body does not actually
    # describe this candidate, never emit it as this job's JD; drop it so
    # verify_details.py / a re-fetch can recover it instead of shipping wrong data.
    if not L.identity_in_text(c["company"], c["title"], txt):
        dropped.append({"jid": jid, "company": c["company"], "title": c["title"], "reason": "corrupt_read"})
        continue
    clauses = L.required_years_clauses(txt)
    miny, ev = (clauses[0][0], clauses[0][1][:160]) if clauses else (None, None)
    sg = L.is_singapore(c.get("loc", ""), c["title"], txt)
    mlm = L.is_direct_sales_mlm(c["company"], c["title"], txt)
    status = L.listing_status(txt)
    blk = L.is_blacklisted(c["company"], c["title"], bl_companies, bl_titles)
    # Employment type: LinkedIn's structured field first, header-text heuristic second
    emp = (crit.get("Employment type") or "").lower()
    contract_flag = emp in ("contract", "temporary") or L.is_contract(c["title"], txt)
    part_flag = emp == "part-time" or L.is_part_time(c["title"], txt)
    reason = None
    # S1/S3 (highest priority): a dead or ghost listing is worthless however well it fits.
    if drop_removed and status == "removed":
        reason = "removed"
    elif drop_closed and status == "closed":
        # S3 freshness anomaly: closed within ~fast_close_h of posting = resume-harvesting ghost.
        reason = "ghost_fast_close" if L.is_fast_close_ghost(txt, fast_close_h) else "closed"
    elif blk:
        reason = f"blacklist ({blk})"
    elif miny is not None and miny >= maxy:
        reason = f"years>={maxy} ({ev})"
    elif L.is_senior_title(c["title"]):
        reason = "senior_title"
    elif drop_contract and contract_flag:
        reason = "contract"
    elif drop_part and part_flag:
        reason = "part_time"
    elif req_sg and not sg:
        reason = "not_singapore"
    elif drop_mlm and mlm:
        reason = "direct_sales_mlm"
    if reason:
        dropped.append({"jid": jid, "company": c["company"], "title": c["title"], "reason": reason})
        continue
    _, pstr = L.rel_to_abs_date(L.loc_line(txt))
    jd, rq, rq_src = jd_and_req(txt)
    hscore, hits = L.keyword_overlap_score(jd, rq, all_kw)
    kept.append({
        "jid": jid, "company": c["company"], "title": c["title"],
        "location": L.clean_loc(c.get("loc", "")), "work": L.work_mode(c.get("loc", "")),
        "posted": pstr, "link": f"https://www.linkedin.com/jobs/view/{jid}/",
        "jd": jd, "req": rq, "req_source": rq_src,
        "min_years": miny,
        "years_clauses": [[y, e[:120]] for y, e in clauses],
        "employment_type": crit.get("Employment type", ""),
        "seniority_label": crit.get("Seniority level", ""),
        "industry_guess": crit.get("Industries", ""),
        "category_guess": guess_category(c["title"], crit),
        "heuristic_score": hscore, "kw_hits": hits,
    })

L.write_json(kept, out)
merge_dropped(run, "parse", dropped)
from collections import Counter
rc = Counter(re.split(r"[ (]", d["reason"])[0] for d in dropped)
print(f"read {len(cands)} -> kept {len(kept)} -> dropped {len(dropped)} {dict(rc)}")
