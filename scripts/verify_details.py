"""Integrity gate for the detail-read stage (prevents the JD-crosstalk bug from ever shipping).

LinkedIn serves /jobs/view/<id>/ as an in-place SPA route change: the URL updates immediately
but the detail pane re-renders one navigation cycle later. If the page is read before it settles,
the file saved as <id>.json holds a NEIGHBOURING job's description. parse/build then emit that
wrong JD under the right company — silent, hard-to-spot data corruption.

This gate re-derives each file's TRUE owner from its own body text and compares it to the
filename id. Run it after every read pass:
  --delete : remove every corrupted (and empty) file so the next read pass re-fetches exactly
             those ids (read_details.sh is idempotent and skips files that already verify).
Exit code is non-zero while any corruption remains, so it doubles as a red/green regression gate
and a CI-style block before build_xlsx.
"""
import argparse, os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L


def load_body(path):
    raw = open(path, encoding="utf-8", errors="replace").read().strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0)).get("txt", "")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--delete", action="store_true",
                    help="delete corrupt/empty detail files so the next read pass re-fetches them")
    a = ap.parse_args()
    run = a.run
    det = os.path.join(run, "details")
    cands = {c["id"]: c for c in L.read_json(os.path.join(run, "candidates.json"))}

    ok, corrupt, empty = 0, [], []
    for fn in sorted(os.listdir(det)):
        if not fn.endswith(".json"):
            continue
        jid = fn[:-5]
        c = cands.get(jid)
        path = os.path.join(det, fn)
        txt = load_body(path)
        if not txt:
            empty.append(jid)
            if a.delete:
                os.remove(path)
            continue
        if c is None:
            # not a current candidate (stale file); leave it alone
            ok += 1
            continue
        if L.identity_in_text(c["company"], c["title"], txt):
            ok += 1
        else:
            owner = _attribute(txt, cands)
            corrupt.append((jid, c["company"], c["title"], owner))
            if a.delete:
                os.remove(path)

    print(f"verify_details: OK={ok}  CORRUPT={len(corrupt)}  EMPTY={len(empty)}"
          + ("  (corrupt+empty deleted; re-run read pass)" if a.delete else ""))
    for jid, comp, title, owner in corrupt:
        print(f"  CORRUPT {jid}  [{comp} :: {title}]  body actually = {owner}")
    if empty:
        print(f"  EMPTY: {', '.join(empty)}")
    # green only when nothing is corrupt AND nothing is empty (every candidate has a clean read)
    sys.exit(1 if (corrupt or empty) else 0)


def _attribute(txt, cands):
    """Best-effort: which candidate does this body actually describe? (for the report only)"""
    h = L.norm(txt[:400])
    best, blen = "?", 0
    for jid, c in cands.items():
        k = L.norm(c["company"] + c["title"])
        if len(k) >= 12 and k in h and len(k) > blen:
            best, blen = f'{jid} [{c["company"]} :: {c["title"]}]', len(k)
    return best


if __name__ == "__main__":
    main()
