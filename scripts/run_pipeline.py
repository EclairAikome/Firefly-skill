"""Firefly pipeline orchestrator - checkpointed, resumable, fail-loud.

Runs every phase in order, marking each completed phase with a .done file so any
interruption (token limit, crash, Ctrl-C, guest outage) resumes exactly where it
stopped. Each phase is the existing standalone script, so everything can still be
run (and debugged) by hand.

  uv run --with pyyaml --with openpyxl python scripts/run_pipeline.py \
      --config config.yaml [--run <dir>] [--until 10_digest] [--force-from 07_parse]

Agent-scoring handshake: with scoring.mode "agent", the pipeline stops after
10_digest (exit code 3) until scores exist - the agent reads scoring_digest.json,
writes scores_p*.jsonl batches, then re-runs the pipeline; 11_scores merges and
gates them. With mode "heuristic" the pipeline runs straight through.

Exit codes: 0 done/until reached, 3 awaiting agent scores, 1 phase failure.
"""
import argparse, datetime, glob, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import lib_common as L
import driver as drv

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(SCRIPTS)


class PipelineError(RuntimeError):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(SKILL, "config.yaml"))
    ap.add_argument("--run", default=None, help="run dir (default state/run_<today>)")
    ap.add_argument("--until", default=None, help="stop after this phase (inclusive)")
    ap.add_argument("--force-from", default=None, help="clear .done for this phase onward")
    ap.add_argument("--list", action="store_true", help="list phases and exit")
    a = ap.parse_args()

    cfg_path = os.path.abspath(a.config)
    cfg = L.load_config(cfg_path)
    run = os.path.abspath(a.run or os.path.join(
        SKILL, "state", f"run_{datetime.date.today().isoformat()}"))
    os.makedirs(run, exist_ok=True)
    done_dir = os.path.join(run, ".done")
    os.makedirs(done_dir, exist_ok=True)
    log_path = os.path.join(run, "pipeline.log")

    def sh(script, *args):
        return [sys.executable, "-X", "utf8", os.path.join(SCRIPTS, script), *args]

    def stream(argv, check=True):
        """Run a phase subprocess, tee-ing output to console + pipeline.log."""
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"\n$ {' '.join(argv)}\n")
            p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace",
                                 env=dict(os.environ, PYTHONUTF8="1"))
            for line in p.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
            p.wait()
        if check and p.returncode != 0:
            raise PipelineError(f"exited {p.returncode}: {' '.join(argv)}")
        return p.returncode

    # --- phase bodies -------------------------------------------------------
    def probe_guest():
        """Fail loud before scraping if the guest API is unreachable/blocked."""
        probe = os.path.join(run, ".probe.jsonl")
        if os.path.exists(probe):
            os.remove(probe)
        url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
               "?keywords=engineer&location=Singapore&geoId=102454443&start=0")
        drv.fetch_batch([{"id": "probe", "url": url}], probe, (0.1, 0.2), drv.pick_driver(cfg))
        body = ""
        for line in open(probe, encoding="utf-8", errors="replace"):
            body = json.loads(line).get("body", "")
        os.remove(probe)
        if "data-entity-urn" not in body:
            raise PipelineError(
                "guest API probe failed - endpoint changed or blocked. "
                "Check connectivity, or fall back to fetch_details.py --mode browser.")
        print("guest API probe: OK")

    def details_loop():
        """Fetch details, then run the integrity gate; corrupt/empty files are
        deleted and re-fetched. Green gate + full coverage required (a small gap
        is tolerated with a loud warning: those jobs drop as no_detail)."""
        for rnd in range(1, 4):
            stream(sh("fetch_details.py", "--config", cfg_path, "--run", run))
            gate = stream(sh("verify_details.py", "--run", run, "--delete"), check=False)
            cands = L.read_json(os.path.join(run, "candidates.json"))
            det = os.path.join(run, "details")
            have = {f[:-5] for f in os.listdir(det)} if os.path.isdir(det) else set()
            missing = [c["id"] for c in cands if c["id"] not in have]
            if gate == 0 and not missing:
                return
            print(f"details round {rnd}: gate={'green' if gate == 0 else 'RED'}, "
                  f"missing={len(missing)}")
        if gate != 0:
            raise PipelineError("details failed the integrity gate after 3 rounds")
        if len(missing) > max(2, len(cands) // 50):   # >2% gaps is a fetch problem
            raise PipelineError(f"{len(missing)} details unfetched after 3 rounds")
        print(f"WARNING: proceeding with {len(missing)} unfetched details "
              f"(they will drop as no_detail): {missing[:10]}")

    def scores_gate():
        """Merge agent score batches; in agent mode, halt until scores exist."""
        parts = glob.glob(os.path.join(run, "scores_p*.jsonl"))
        if parts:
            stream(sh("merge_scores.py", "--run", run))
            return
        if os.path.exists(os.path.join(run, "scores.json")):
            print("scores.json present")
            return
        if (cfg.get("scoring", {}) or {}).get("mode", "agent") == "agent":
            print("\n=== AWAITING AGENT SCORES ===")
            print(f"Read {os.path.join(run, 'scoring_digest.json')}, judge fit per the")
            print("SKILL.md Phase 7 protocol, write scores_p*.jsonl batches into the run")
            print("dir, then re-run this pipeline to continue.")
            sys.exit(3)
        print("heuristic mode: building without agent scores")

    phases = [
        ("01_exclusion",   lambda: stream(sh("build_exclusion.py", "--config", cfg_path, "--run", run))),
        ("02_probe",       probe_guest),
        ("03_cards",       lambda: stream(sh("fetch_cards.py", "--config", cfg_path, "--run", run))),
        ("04_aggregate",   lambda: stream(sh("aggregate_candidates.py", "--run", run))),
        ("05_prefilter",   lambda: stream(sh("prefilter_cards.py", "--config", cfg_path, "--run", run))),
        ("06_details",     details_loop),
        ("07_parse",       lambda: stream(sh("parse_details.py", "--config", cfg_path, "--run", run,
                                             "--out", os.path.join(run, "kept_candidates.json")))),
        ("08_recheck",     lambda: stream(sh("recheck_live.py", "--config", cfg_path, "--run", run))),
        ("09_apply_live",  lambda: stream(sh("apply_live_status.py", "--run", run))),
        ("10_digest",      lambda: stream(sh("make_digest.py", "--run", run))),
        ("11_scores",      scores_gate),
        ("12_build",       lambda: stream(sh("build_xlsx.py", "--config", cfg_path, "--run", run))),
        ("13_verify_wb",   lambda: stream(sh("verify_workbook.py", "--config", cfg_path, "--run", run))),
        ("14_report",      lambda: stream(sh("run_report.py", "--run", run, "--config", cfg_path))),
    ]

    if a.list:
        for name, _ in phases:
            mark = "done" if os.path.exists(os.path.join(done_dir, name)) else "    "
            print(f"  [{mark}] {name}")
        return

    if a.force_from:
        names = [n for n, _ in phases]
        if a.force_from not in names:
            raise SystemExit(f"unknown phase {a.force_from}; use --list")
        for n in names[names.index(a.force_from):]:
            p = os.path.join(done_dir, n)
            if os.path.exists(p):
                os.remove(p)

    print(f"pipeline run dir: {run}")
    for name, body in phases:
        mark = os.path.join(done_dir, name)
        if os.path.exists(mark):
            print(f"[skip] {name}")
        else:
            print(f"\n=== {name} ===")
            try:
                body()
            except PipelineError as e:
                print(f"\nPIPELINE FAILED at {name}: {e}")
                sys.exit(1)
            with open(mark, "w") as f:
                f.write(datetime.datetime.now().isoformat())
        if a.until and name == a.until:
            print(f"\nstopped after {name} (--until)")
            return
    print("\nPIPELINE COMPLETE")


if __name__ == "__main__":
    main()
