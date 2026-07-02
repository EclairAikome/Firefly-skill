"""Phase 5 - fetch every candidate's job detail via the LinkedIn guest jobPosting
endpoint (default), or via the logged-in browser DOM as a fallback (--mode browser).

Guest mode is the primary path: the HTTP response is keyed to its id by the request
itself, so the SPA off-by-one crosstalk that plagued the browser path cannot happen;
the description arrives fully expanded (no "see more" click); and a page costs
~1.5s instead of 15-20s. verify_details.py still gates before parsing either way.

Writes details/<id>.json in the schema parse_details.py consumes:
  {"title", "status", "txt", "criteria"}   (criteria: LinkedIn's structured
  Seniority level / Employment type / Job function / Industries fields)
txt mimics the logged-in page's innerText layout so every existing parser regex
(loc_line, employment header, closed banner, "About the job") keeps working.

Raw fetches are cached in <RUN_DIR>/raw_details.jsonl - reparse without refetching.
Resumable at both layers: raw fetch skips fetched ids, parse skips existing files.
"""
import argparse, html as html_mod, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L
import driver as drv

API = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"

RE_TITLE = re.compile(r'class="top-card-layout__title[^"]*"[^>]*>(.*?)</h2>', re.S)
RE_COMP = re.compile(r'class="topcard__org-name-link[^"]*"[^>]*>(.*?)</a>', re.S)
RE_LOC = re.compile(r'class="topcard__flavor topcard__flavor--bullet[^"]*"[^>]*>(.*?)</span>', re.S)
RE_POSTED = re.compile(r'class="posted-time-ago__text[^"]*"[^>]*>(.*?)</span>', re.S)
RE_APPL = re.compile(r'class="num-applicants__caption[^"]*"[^>]*>(.*?)</', re.S)
RE_CRIT = re.compile(r'description__job-criteria-subheader[^"]*"[^>]*>\s*(.*?)\s*</h3>\s*'
                     r'<span[^>]*description__job-criteria-text[^"]*"[^>]*>\s*(.*?)\s*</span>', re.S)
RE_CLOSED = re.compile(r"no longer accepting applications", re.I)
TAGS = re.compile(r"<[^>]+>")


def strip_tags(fragment):
    return html_mod.unescape(TAGS.sub(" ", fragment or "")).replace(" ", " ").strip()


def desc_to_text(markup):
    t = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    t = re.sub(r"(?i)</(p|div|ul|ol|h\d)>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "\n• ", t)
    t = TAGS.sub(" ", t)
    t = html_mod.unescape(t).replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def extract_desc(page):
    i = page.find('class="show-more-less-html__markup')
    if i < 0:
        return ""
    i = page.index(">", i) + 1
    depth, j = 1, i
    div = re.compile(r"<(/?)div\b")
    while depth and j < len(page):
        m = div.search(page, j)
        if not m:
            break
        depth += -1 if m.group(1) else 1
        j = m.end()
    return desc_to_text(page[i:page.rfind("<", i, j)] if depth == 0 else page[i:j])


def build_detail(page, card):
    """Assemble the detail record from a guest jobPosting HTML page."""
    title = strip_tags((RE_TITLE.search(page) or [None, ""])[1]) or card["title"]
    comp = strip_tags((RE_COMP.search(page) or [None, ""])[1]) or card["company"]
    loc = strip_tags((RE_LOC.search(page) or [None, ""])[1]) or card.get("loc", "")
    posted = strip_tags((RE_POSTED.search(page) or [None, ""])[1])
    appl = strip_tags((RE_APPL.search(page) or [None, ""])[1])
    crit = {strip_tags(k): strip_tags(v) for k, v in RE_CRIT.findall(page)}
    closed = bool(RE_CLOSED.search(page))
    desc = extract_desc(page)

    lines = [comp, title, f"{loc} · {posted}" + (f" · {appl}" if appl else "")]
    emp = crit.get("Employment type", "")
    if emp:
        lines.append(f"{L.work_mode(card.get('loc', ''))} {emp} Apply")
    if closed:
        lines.append("No longer accepting applications")
    lines += ["About the job", desc]
    for k in ("Seniority level", "Job function", "Industries"):
        if crit.get(k):
            lines.append(f"{k}: {crit[k]}")
    return {"title": title, "status": "closed" if closed else "open",
            "txt": "\n".join(lines), "criteria": crit}


def removed_stub(card):
    txt = (f"{card['company']}\n{card['title']}\n{card.get('loc', '')}\n"
           "This job posting has been removed.")
    return {"title": card["title"], "status": "removed", "txt": txt, "criteria": {}}


def guest_mode(cfg, run, cands, det_dir, max_new):
    which = drv.pick_driver(cfg)
    pipe = cfg.get("pipeline", {}) or {}
    interval = tuple(pipe.get("detail_fetch_interval", [1.0, 1.6]))
    chunk = int(pipe.get("detail_chunk_size", 250))
    raw_path = os.path.join(run, "raw_details.jsonl")

    todo = [c for c in cands
            if not os.path.exists(os.path.join(det_dir, c["id"] + ".json"))]
    if max_new:
        todo = todo[:max_new]
    tasks = [{"id": c["id"], "url": API + c["id"]} for c in todo]
    print(f"details: {len(tasks)} to fetch of {len(cands)} (driver={which})", flush=True)
    for i in range(0, len(tasks), chunk):
        stats = drv.fetch_batch(tasks[i:i + chunk], raw_path, interval, which)
        print(f"chunk {i // chunk + 1}: {stats}", flush=True)

    # parse raw fetches into detail files
    cards = {c["id"]: c for c in cands}
    ok = removed = failed = warned = 0
    for line in open(raw_path, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        jid = str(o.get("id"))
        card = cards.get(jid)
        out = os.path.join(det_dir, jid + ".json")
        if card is None or os.path.exists(out):
            continue
        if o["status"] == "http_404":
            rec = removed_stub(card)
            removed += 1
        elif o["status"] == "ok" and "top-card-layout__title" in o.get("body", ""):
            rec = build_detail(o["body"], card)
            if not L.identity_in_text(card["company"], card["title"], rec["txt"]):
                print(f"  WARN identity mismatch {jid}: card=[{card['company']} :: "
                      f"{card['title']}] page title={rec['title']!r}", flush=True)
                warned += 1
            ok += 1
        else:
            failed += 1
            continue   # leave unfetched -> next pass retries
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    saved = len([x for x in os.listdir(det_dir) if x.endswith(".json")])
    print(f"DONE details: ok={ok} removed={removed} failed={failed} "
          f"identity_warns={warned}; saved {saved} of {len(cands)}")


def browser_mode(run, cands, det_dir, max_new):
    """Fallback: read details from the logged-in LinkedIn SPA via browser-harness
    (settle -> see-more -> extract -> identity-verify, fail closed). Slow (~15-20s
    per page) - use only if the guest endpoint is dead."""
    exe = shutil.which("browser-harness")
    if not exe:
        raise SystemExit("browser-harness not on PATH (browser mode needs it)")
    env = dict(os.environ, FIREFLY_RUN=run, FIREFLY_MAX=str(max_new or 0),
               FIREFLY_SCRIPTS=os.path.dirname(os.path.abspath(__file__)), PYTHONUTF8="1")
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_browser_details_worker.py")
    with open(worker, "rb") as stdin:
        r = subprocess.run([exe], stdin=stdin, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    if r.stdout:
        sys.stdout.write(r.stdout[-4000:])
    if r.returncode != 0:
        raise RuntimeError(f"browser details worker exited {r.returncode}: {(r.stderr or '')[-800:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--mode", choices=["guest", "browser"], default="guest")
    ap.add_argument("--max", type=int, default=0, help="cap NEW fetches this pass (0 = all)")
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    cands = L.read_json(os.path.join(a.run, "candidates.json"))
    det_dir = os.path.join(a.run, "details")
    os.makedirs(det_dir, exist_ok=True)
    if a.mode == "guest":
        guest_mode(cfg, a.run, cands, det_dir, a.max)
    else:
        browser_mode(a.run, cands, det_dir, a.max)


if __name__ == "__main__":
    main()
