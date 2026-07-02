"""Data-fetch driver abstraction. The pipeline needs exactly one primitive from a
browser tool: "HTTP GET this URL through the logged-in Chrome's network stack"
(proxy + cookies; a bare urllib from the shell bypasses the user's proxy and 404s).

Drivers (select via config pipeline.driver or env FIREFLY_DRIVER):
  harness - browser-harness executes scripts/_fetch_worker.py (default; field-tested)
  act     - browser-act evaluates a JS fetch loop per small batch (UNTESTED: written
            while browser-act was unreachable; verify before relying on it)
  direct  - plain urllib from this process (works only if the shell has a proxy or
            direct connectivity to linkedin.com)

fetch_batch() is resumable: results append to a JSONL file keyed by task id, and
already-fetched ids are skipped, so re-running after any failure just continues.
"""
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def pick_driver(cfg=None):
    name = os.environ.get("FIREFLY_DRIVER") or ((cfg or {}).get("pipeline", {}) or {}).get("driver") or "harness"
    name = name.strip().lower()
    if name not in ("harness", "act", "direct"):
        raise SystemExit(f"unknown driver {name!r} (want harness|act|direct)")
    return name


def _done_ids(out_path):
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path, encoding="utf-8", errors="replace"):
            try:
                done.add(str(json.loads(line)["id"]))
            except Exception:
                pass
    return done


def fetch_batch(tasks, out_path, interval=(1.0, 1.6), driver="harness"):
    """tasks: [{"id": str, "url": str}]. Appends JSONL lines
    {"id","status","body"} to out_path (status: ok | http_<code> | error:<msg>).
    Returns {"ok": n, "err": n, "skipped": n}."""
    todo = [t for t in tasks if str(t["id"]) not in _done_ids(out_path)]
    skipped = len(tasks) - len(todo)
    if not todo:
        return {"ok": 0, "err": 0, "skipped": skipped}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if driver == "harness":
        _fetch_harness(todo, out_path, interval)
    elif driver == "act":
        _fetch_act(todo, out_path, interval)
    else:
        _fetch_direct(todo, out_path, interval)
    todo_ids = {str(t["id"]) for t in todo}
    ok = err = 0
    for line in open(out_path, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if str(o.get("id")) in todo_ids:
            # http_404 is a definitive answer (posting removed), not a fetch failure
            if o.get("status") in ("ok", "http_404"):
                ok += 1
            else:
                err += 1
    return {"ok": ok, "err": err, "skipped": skipped}


def _fetch_harness(tasks, out_path, interval):
    exe = shutil.which("browser-harness")
    if not exe:
        raise SystemExit("browser-harness not on PATH (install it or switch driver)")
    tmp = out_path + ".tasks.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False)
    env = dict(os.environ, FIREFLY_TASKS=tmp, FIREFLY_OUT=out_path,
               FIREFLY_INTERVAL=f"{interval[0]},{interval[1]}", PYTHONUTF8="1")
    worker = os.path.join(SCRIPTS, "_fetch_worker.py")
    with open(worker, "rb") as stdin:
        r = subprocess.run([exe], stdin=stdin, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    if r.stdout:
        sys.stdout.write(r.stdout[-3000:])
    if r.returncode != 0:
        raise RuntimeError(f"harness worker exited {r.returncode}: {(r.stderr or '')[-800:]}")
    try:
        os.remove(tmp)
    except OSError:
        pass


def _fetch_act(tasks, out_path, interval, session="ljh", per_eval=20):
    """UNTESTED (browser-act unreachable when written). Evaluates a JS fetch loop in
    the browser-act session, per_eval urls per eval call to bound the return size."""
    exe = shutil.which("browser-act")
    if not exe:
        raise SystemExit("browser-act not on PATH (install it or switch driver)")
    ms = int(1000 * (interval[0] + interval[1]) / 2)
    with open(out_path, "a", encoding="utf-8") as out:
        for i in range(0, len(tasks), per_eval):
            chunk = tasks[i:i + per_eval]
            pairs = json.dumps([[str(t["id"]), t["url"]] for t in chunk])
            js = (
                "(async () => { const ps = " + pairs + "; const out = [];"
                " for (const [id, u] of ps) {"
                "  try { const r = await fetch(u);"
                "        out.push([id, r.ok ? 'ok' : 'http_' + r.status, r.ok ? await r.text() : '']); }"
                "  catch (e) { out.push([id, 'error:' + e.message, '']); }"
                "  await new Promise(res => setTimeout(res, " + str(ms) + ")); }"
                " return JSON.stringify(out); })()"
            )
            r = subprocess.run([exe, "--session", session, "eval", "--stdin"],
                               input=js, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0:
                raise RuntimeError(f"browser-act eval failed: {(r.stderr or '')[-400:]}")
            payload = json.loads(r.stdout[r.stdout.index("["):r.stdout.rindex("]") + 1])
            for jid, status, body in payload:
                out.write(json.dumps({"id": jid, "status": status, "body": body},
                                     ensure_ascii=False) + "\n")
            out.flush()
            print(f"act batch {i + len(chunk)}/{len(tasks)}", flush=True)


def _fetch_direct(tasks, out_path, interval):
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
    with open(out_path, "a", encoding="utf-8") as out:
        for i, t in enumerate(tasks, 1):
            status, body = "error:exhausted", ""
            for attempt in range(3):
                try:
                    req = urllib.request.Request(t["url"], headers={
                        "User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"})
                    with urllib.request.urlopen(req, timeout=25) as r:
                        status, body = "ok", r.read().decode("utf-8", errors="replace")
                    break
                except urllib.error.HTTPError as e:
                    status = f"http_{e.code}"
                    if e.code == 404:
                        break
                    time.sleep(15 * (attempt + 1))
                except Exception as e:
                    status = f"error:{e}"
                    time.sleep(8 * (attempt + 1))
            out.write(json.dumps({"id": str(t["id"]), "status": status, "body": body},
                                 ensure_ascii=False) + "\n")
            out.flush()
            if i % 25 == 0:
                print(f"direct progress {i}/{len(tasks)}", flush=True)
            time.sleep(random.uniform(*interval))
