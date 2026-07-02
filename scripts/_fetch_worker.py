# Fetch worker executed BY browser-harness (its helpers, notably js(), are in
# globals). Reads a task list, GETs each url through the logged-in Chrome via
# js(fetch), appends JSONL results. Resumable: ids already in the output are
# skipped, so a crashed pass just re-runs.
#
# KEEP THIS FILE PURE ASCII. browser-harness reads stdin with the OS locale
# codec on Windows (GBK here); any raw non-ASCII byte becomes a lone surrogate
# and exec() dies. Escape as \uXXXX if ever needed.
#
# Env contract: FIREFLY_TASKS (json path), FIREFLY_OUT (jsonl path),
#               FIREFLY_INTERVAL ("lo,hi" seconds, optional)
import json
import os
import random
import time

tasks_path = os.environ["FIREFLY_TASKS"]
out_path = os.environ["FIREFLY_OUT"]
lo, hi = [float(x) for x in os.environ.get("FIREFLY_INTERVAL", "1.0,1.6").split(",")]

with open(tasks_path, encoding="utf-8") as f:
    tasks = json.load(f)

done = set()
if os.path.exists(out_path):
    for line in open(out_path, encoding="utf-8", errors="replace"):
        try:
            done.add(str(json.loads(line)["id"]))
        except Exception:
            pass

out = open(out_path, "a", encoding="utf-8")
n_ok = n_404 = n_err = 0
todo = [t for t in tasks if str(t["id"]) not in done]
print("worker: " + str(len(todo)) + " to fetch (" + str(len(done)) + " already done)", flush=True)

for i, t in enumerate(todo, 1):
    url = str(t["url"]).replace("'", "%27")
    status, body = "error:exhausted", ""
    for attempt in range(3):
        res = js("fetch('" + url + "').then(r => r.ok ? r.text() : 'HTTPERR::' + r.status).catch(e => 'HTTPERR::' + e.message)")
        res = str(res or "")
        if res.startswith("HTTPERR::"):
            code = res.split("::", 1)[1]
            if code == "404":
                status, body = "http_404", ""
                break
            status, body = "error:" + code, ""
            time.sleep(15 * (attempt + 1))   # 429/5xx backoff
            continue
        status, body = "ok", res
        break
    out.write(json.dumps({"id": str(t["id"]), "status": status, "body": body}, ensure_ascii=False) + "\n")
    out.flush()
    if status == "ok":
        n_ok += 1
    elif status == "http_404":
        n_404 += 1
    else:
        n_err += 1
    if i % 25 == 0:
        print("worker progress " + str(i) + "/" + str(len(todo)) + " ok=" + str(n_ok)
              + " 404=" + str(n_404) + " err=" + str(n_err), flush=True)
    time.sleep(random.uniform(lo, hi))

out.close()
print("WORKER DONE ok=" + str(n_ok) + " 404=" + str(n_404) + " err=" + str(n_err))
