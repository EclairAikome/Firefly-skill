# Browser-DOM details fallback worker, executed BY browser-harness (js(),
# goto_url(), wait_for_load() in globals). Only needed when the guest jobPosting
# endpoint is unavailable. Implements the anti-crosstalk protocol the SPA
# requires: settle (header stable across two reads) -> expand "see more" ->
# extract -> verify identity -> retry via a neutral page; fail closed.
#
# KEEP PURE ASCII (see _fetch_worker.py for why).
#
# Env contract: FIREFLY_RUN (run dir), FIREFLY_MAX (cap new reads, 0 = all)
import json
import os
import random
import re
import sys
import time

RUN = os.environ["FIREFLY_RUN"]
MAX = int(os.environ.get("FIREFLY_MAX", "0"))
# browser-harness exec()s stdin so __file__ is unreliable; the caller passes the
# scripts dir explicitly (fetch_details.py browser_mode sets FIREFLY_SCRIPTS)
SCRIPTS = os.environ["FIREFLY_SCRIPTS"]
sys.path.insert(0, SCRIPTS)
import lib_common as L

NEUTRAL = "https://www.linkedin.com/jobs/"


def load_js(name):
    path = os.path.join(SCRIPTS, name)
    lines = open(path, encoding="utf-8").read().splitlines()
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("//")):
        i += 1
    return "\n".join(lines[i:])


HDR_JS = load_js("job_header.js")
CLICK_JS = load_js("click_seemore.js")
DET_JS = load_js("detail_extract.js")

cands = json.load(open(os.path.join(RUN, "candidates.json"), encoding="utf-8"))
det_dir = os.path.join(RUN, "details")
os.makedirs(det_dir, exist_ok=True)


def read_one(c):
    jid = c["id"]
    for attempt in (1, 2, 3):
        if attempt > 1:
            goto_url(NEUTRAL)
            wait_for_load(15)
            time.sleep(1.5)
        goto_url("https://www.linkedin.com/jobs/view/" + jid + "/")
        wait_for_load(20)
        prev = None
        for _ in range(8):
            cur = re.sub(r"[^A-Za-z0-9]", "", str(js(HDR_JS) or ""))
            if cur and cur == prev:
                break
            prev = cur
            time.sleep(1.0)
        js(CLICK_JS)
        time.sleep(1.2)
        raw = js(DET_JS)
        if not raw or len(raw) < 50:
            continue
        try:
            body = json.loads(raw)
        except Exception:
            continue
        if L.identity_in_text(c["company"], c["title"], body.get("txt", "")):
            body["criteria"] = {}
            with open(os.path.join(det_dir, jid + ".json"), "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False)
            return True, len(raw)
        print("mismatch " + jid + " (attempt " + str(attempt) + ") - re-navigating", flush=True)
        time.sleep(2)
    return False, 0


got, streak = 0, 0
for c in cands:
    f = os.path.join(det_dir, c["id"] + ".json")
    if os.path.exists(f) and os.path.getsize(f) > 0:
        continue
    ok, size = read_one(c)
    if ok:
        got += 1
        streak = 0
        print("read " + c["id"] + " (" + str(size) + "b)", flush=True)
        if MAX and got >= MAX:
            print("CHUNK done (" + str(got) + ")")
            break
    else:
        streak += 1
        print("UNVERIFIED " + c["id"] + " (left unread - fail closed)", flush=True)
        if streak >= 5:
            print("BAIL: " + str(streak) + " failures in a row (session degraded)")
            break
    time.sleep(random.uniform(1.0, 3.0))

saved = len([x for x in os.listdir(det_dir) if x.endswith(".json")])
print("DONE pass: read " + str(got) + " new; saved " + str(saved) + " of " + str(len(cands)))
