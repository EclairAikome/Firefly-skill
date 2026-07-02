# Cards worker executed BY browser-harness (js() in globals). Sequentially pages
# through the LinkedIn guest search API for each query, fetching raw HTML pages
# into a JSONL file. Paging must be sequential (stop on a short page), which is
# why cards get their own worker instead of the generic batch fetcher.
#
# KEEP PURE ASCII (see _fetch_worker.py for why).
#
# Env contract: FIREFLY_CARDS_TASKS (json: [{label, qs, max_pages}]),
#               FIREFLY_OUT (jsonl), FIREFLY_INTERVAL ("lo,hi")
import json
import os
import random
import re
import time

API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
RE_CARD = re.compile(r'data-entity-urn="urn:li:jobPosting:')

tasks_path = os.environ["FIREFLY_CARDS_TASKS"]
out_path = os.environ["FIREFLY_OUT"]
lo, hi = [float(x) for x in os.environ.get("FIREFLY_INTERVAL", "1.4,2.2").split(",")]

with open(tasks_path, encoding="utf-8") as f:
    tasks = json.load(f)

out = open(out_path, "a", encoding="utf-8")
for t in tasks:
    label, qs, max_pages = t["label"], t["qs"], int(t.get("max_pages", 20))
    start, pages = 0, 0
    while pages < max_pages:
        url = (API + qs + "&start=" + str(start)).replace("'", "%27")
        body = ""
        for attempt in range(3):
            res = js("fetch('" + url + "').then(r => r.ok ? r.text() : 'HTTPERR::' + r.status).catch(e => 'HTTPERR::' + e.message)")
            res = str(res or "")
            if res.startswith("HTTPERR::"):
                time.sleep(12 * (attempt + 1))
                continue
            body = res
            break
        n = len(RE_CARD.findall(body))
        out.write(json.dumps({"label": label, "start": start, "n": n, "body": body},
                             ensure_ascii=False) + "\n")
        out.flush()
        print("cards " + label + " start=" + str(start) + " n=" + str(n), flush=True)
        if n < 10:          # short/empty page = last page (guest pages are 10 cards)
            break
        start += n
        pages += 1
        time.sleep(random.uniform(lo, hi))
out.close()
print("CARDS WORKER DONE")
