"""Phase 3 - fetch job cards via the LinkedIn guest search API.

Replaces the retired browser-scroll path (search.sh + scroll.js + card_extract.js):
current LinkedIn virtualizes the results list and ignores scripted scrolling, while
the guest endpoint pages cleanly and already carries id/title/company/loc/posted.
Requests go through the logged-in Chrome's network stack via the driver (proxy +
cookies); see scripts/driver.py for driver selection.

Output: <RUN_DIR>/cards/<label>.json  [{id,title,company,loc,posted_date}]
        (same shape aggregate_candidates.py always consumed, plus posted_date)
Raw pages are kept in <RUN_DIR>/cards_raw.jsonl for reparsing without refetching.
"""
import argparse, html, json, os, re, shutil, subprocess, sys, time, random
import urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from lib_common import load_config
import driver as drv

API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"

RE_LI = re.compile(r"<li\b")
RE_ID = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
RE_TITLE = re.compile(r'class="base-search-card__title[^"]*"[^>]*>\s*(.*?)\s*</', re.S)
RE_COMP = re.compile(r'class="base-search-card__subtitle[^"]*"[^>]*>(.*?)</(?:h4|div)>', re.S)
RE_LOC = re.compile(r'class="job-search-card__location[^"]*"[^>]*>\s*(.*?)\s*</', re.S)
RE_DATE = re.compile(r'<time[^>]*datetime="([^"]+)"')
RE_CARDMARK = re.compile(r'data-entity-urn="urn:li:jobPosting:')
TAGS = re.compile(r"<[^>]+>")


def clean(fragment):
    return html.unescape(TAGS.sub(" ", fragment or "")).replace(" ", " ").strip().strip(",").strip()


def grab(match):
    return match.group(1) if match else ""


def parse_cards(page_html):
    out = []
    for block in RE_LI.split(page_html or "")[1:]:
        m = RE_ID.search(block)
        if not m:
            continue
        out.append({"id": m.group(1),
                    "title": clean(grab(RE_TITLE.search(block))),
                    "company": clean(grab(RE_COMP.search(block))),
                    "loc": clean(grab(RE_LOC.search(block))),
                    "posted_date": grab(RE_DATE.search(block))})
    return out


def query_string(cfg, q):
    s = cfg["search"]
    return urllib.parse.urlencode({
        "keywords": q, "location": s.get("location_label", "Singapore"),
        "geoId": s["geo_id"], "f_TPR": s["recency"], "f_E": str(s["experience"]),
        "sortBy": s.get("sort", "DD")})


def fetch_raw_harness(tasks, raw_path, interval):
    exe = shutil.which("browser-harness")
    if not exe:
        raise SystemExit("browser-harness not on PATH")
    tmp = raw_path + ".tasks.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False)
    env = dict(os.environ, FIREFLY_CARDS_TASKS=tmp, FIREFLY_OUT=raw_path,
               FIREFLY_INTERVAL=f"{interval[0]},{interval[1]}", PYTHONUTF8="1")
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cards_worker.py")
    with open(worker, "rb") as stdin:
        r = subprocess.run([exe], stdin=stdin, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    if r.stdout:
        sys.stdout.write(r.stdout[-3000:])
    if r.returncode != 0:
        raise RuntimeError(f"cards worker exited {r.returncode}: {(r.stderr or '')[-800:]}")
    try:
        os.remove(tmp)
    except OSError:
        pass


def fetch_raw_direct(tasks, raw_path, interval):
    import urllib.request
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
    with open(raw_path, "a", encoding="utf-8") as out:
        for t in tasks:
            start, pages = 0, 0
            while pages < int(t.get("max_pages", 20)):
                url = API + t["qs"] + "&start=" + str(start)
                body = ""
                for attempt in range(3):
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": ua})
                        with urllib.request.urlopen(req, timeout=25) as r:
                            body = r.read().decode("utf-8", errors="replace")
                        break
                    except Exception:
                        time.sleep(12 * (attempt + 1))
                n = len(RE_CARDMARK.findall(body))
                out.write(json.dumps({"label": t["label"], "start": start, "n": n,
                                      "body": body}, ensure_ascii=False) + "\n")
                out.flush()
                print(f"cards {t['label']} start={start} n={n}", flush=True)
                if n < 10:
                    break
                start += n
                pages += 1
                time.sleep(random.uniform(*interval))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    cfg = load_config(a.config)
    which = drv.pick_driver(cfg)
    pipe = cfg.get("pipeline", {}) or {}
    max_cards = int(pipe.get("max_cards_per_query", 200))
    interval = tuple(pipe.get("cards_interval", [1.4, 2.2]))

    cards_dir = os.path.join(a.run, "cards")
    os.makedirs(cards_dir, exist_ok=True)
    raw_path = os.path.join(a.run, "cards_raw.jsonl")

    tasks = []
    for q in cfg["search"]["queries"]:
        label = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
        dest = os.path.join(cards_dir, label + ".json")
        if os.path.exists(dest) and os.path.getsize(dest) > 10:
            print(f"{label}: exists, skip")
            continue
        tasks.append({"label": label, "qs": query_string(cfg, q),
                      "max_pages": max(1, max_cards // 10)})
    if tasks:
        if which == "harness":
            fetch_raw_harness(tasks, raw_path, interval)
        elif which == "direct":
            fetch_raw_direct(tasks, raw_path, interval)
        else:
            raise SystemExit("driver 'act' has no cards implementation yet - "
                             "use harness or direct, or fetch cards manually")

    # parse everything in cards_raw.jsonl into per-label card files
    by_label = {}
    if os.path.exists(raw_path):
        for line in open(raw_path, encoding="utf-8", errors="replace"):
            try:
                o = json.loads(line)
            except Exception:
                continue
            for c in parse_cards(o.get("body", "")):
                by_label.setdefault(o["label"], {})[c["id"]] = c
    for label, cards in by_label.items():
        dest = os.path.join(cards_dir, label + ".json")
        if os.path.exists(dest) and os.path.getsize(dest) > 10:
            continue
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(list(cards.values()), f, ensure_ascii=False, indent=1)
        print(f"{label}: {len(cards)} cards")
    total = sum(len(v) for v in by_label.values())
    print(f"DONE cards: {total} raw cards across {len(by_label)} queries (driver={which})")


if __name__ == "__main__":
    main()
