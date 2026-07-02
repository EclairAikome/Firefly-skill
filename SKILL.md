---
name: Firefly-skill
description: >-
  Fully automated, read-only LinkedIn job scraping, filtering, and Excel export for a
  job seeker. Use this WHENEVER the user wants to find, scrape, search, collect, or
  refresh job postings from LinkedIn, build or update a job-application shortlist or
  tracker, or export matched jobs to a spreadsheet — especially Singapore entry-level
  roles filtered by years-of-experience, base location, and already-applied status.
  Trigger on phrases like "scrape LinkedIn jobs", "find me entry-level jobs", "refresh
  my job list", "update the job tracker", "new job matches", "do a job-hunt run",
  "pull SG product/marketing jobs", even when the user does NOT say "scrape" outright.
  It searches LinkedIn, reads every job's full description, drops roles needing >= N
  years, non-Singapore roles, direct-sales/MLM roles, and anything already applied to,
  scores fit, and writes a dated v3-style .xlsx (Job Applications + This-Week by Fit +
  Summary) sorted by match score, deduping against past runs. Do NOT use it for:
  applying to jobs or filling application forms (a separate apply skill does that);
  scraping non-LinkedIn sites or product/price data; exporting LinkedIn connections
  or collecting people's profiles for networking/lead-gen; resume writing; or generic
  spreadsheet formatting. This skill is READ-ONLY and is specifically about turning
  LinkedIn job OPENINGS into a fit-ranked shortlist; it never auto-applies.
---

# Firefly-skill

Automates the LinkedIn job-hunt scrape this user runs repeatedly: search both of their
career tracks, read each job's full description, filter hard on the rules they care
about, score fit, and hand back a clean spreadsheet in their established format.

**Scope is deliberately read-only.** Every blocker in past runs (captchas, "I'm not a
robot" walls, garbled Easy Apply modals, ATS login walls) came from the *apply* step,
not the *scrape* step. Applying is handled by the user's separate apply skill.

**Data path is guest-API-first.** Cards and full JDs come from LinkedIn's guest
endpoints (`jobs-guest/jobs/api/...`, see `references/linkedin_params.md`), fetched
through the logged-in Chrome's network stack so the user's proxy and cookies apply.
This is deliberate: current LinkedIn virtualizes the search list and ignores scripted
scrolling, and the logged-in detail pane has an SPA race that can serve a *neighbouring*
job's JD. The guest endpoints have neither problem — an HTTP response is keyed to its
id by the request itself — and each detail costs ~1.5s instead of 15-20s. The browser
DOM survives only as a detail-read fallback (`fetch_details.py --mode browser`).

## Prerequisites (check once per run)

1. Chrome running and logged in to LinkedIn (the fetch driver rides its network stack).
2. One data driver on PATH — set `pipeline.driver` in `config.yaml` (or `FIREFLY_DRIVER`):
   - `harness` (default): the `browser-harness` CLI. Field-tested.
   - `act`: the `browser-act` CLI. Written to spec but UNTESTED (browser-act was
     unreachable when this path was built) — verify on first use.
   - `direct`: plain HTTP from Python. Only works if the shell itself can reach
     linkedin.com (VPN/proxy env vars set).
3. Python 3.12+ with `uv`. All commands below run from the skill directory.

The pipeline probes the guest API before scraping (phase `02_probe`) and fails loud if
it is unreachable, so a broken setup costs seconds, not a silent empty workbook.

## How to run

One command drives the whole pipeline, checkpointed and resumable:

```bash
PYTHONUTF8=1 uv run --with pyyaml --with openpyxl python scripts/run_pipeline.py \
    --config config.yaml
```

Every phase writes a `.done` marker under the run dir (default
`state/run_<YYYY-MM-DD>`); re-running skips completed phases, so interruptions
(token limits, crashes, guest outages) resume exactly where they stopped. Useful
flags: `--run <dir>` (explicit run dir), `--until <phase>` (stop after a phase),
`--force-from <phase>` (redo a phase and everything after it), `--list` (show
phase status). Long runs: launch it in the background and check `pipeline.log`.

| Phase | What it does | Script |
|---|---|---|
| 01_exclusion | already-applied/seen set from master library + history CSVs | build_exclusion.py |
| 02_probe | guest-API reachability check (fail loud early) | (built-in) |
| 03_cards | guest search, paged, all queries -> cards/*.json | fetch_cards.py |
| 04_aggregate | id-dedupe + collapse same-role reposts + drop already-seen | aggregate_candidates.py |
| 05_prefilter | card-level rules: senior titles, foreign-tagged locations | prefilter_cards.py |
| 06_details | guest jobPosting fetch for every candidate + integrity gate loop | fetch_details.py + verify_details.py |
| 07_parse | hard rules on full JDs -> kept/dropped | parse_details.py |
| 08_recheck | liveness re-ping, ONLY if details are older than `recheck_max_age_hours` | recheck_live.py |
| 09_apply_live | drop kept jobs that died since the fetch (fail open) | apply_live_status.py |
| 10_digest | compact per-job digest for agent scoring | make_digest.py |
| 11_scores | merge agent score batches; in agent mode HALT (exit 3) until they exist | merge_scores.py |
| 12_build | dated v3 workbook + idempotent master-library update | build_xlsx.py |
| 13_verify_wb | deterministic ship-gate: leaks/order/structure (red = do not ship) | verify_workbook.py |
| 14_report | report.md into the run dir + a copy next to the workbook | run_report.py |

Each script still runs standalone with the same arguments — use that for debugging a
single phase.

## Phase 7 — agent scoring protocol

With `scoring.mode: agent` the pipeline stops after `10_digest` (exit code 3) and
prints AWAITING AGENT SCORES. Then:

1. Read `<RUN_DIR>/scoring_digest.json` — one compact row per kept job, sorted by
   heuristic score. **Read `yrs_all` before scoring anything high**: it lists every
   year-requirement clause, because stacked requirements ("3+ yrs PM and 2+ yrs AI")
   hide behind the floor that the deterministic gate uses. `sen`/`emp`/`ind` carry
   LinkedIn's structured Seniority/Employment/Industries fields.
2. Judge fit against `config.yaml`'s profile. Scoring guidance — be concrete and
   honest, this is the whole value of the skill:
   - Anchor `why` in the user's actual background, not generic praise.
   - `watch` should name the real risk (years gap, domain, visa/language gate,
     internship-not-FT, suspected roadshow bait) so the user can triage fast.
   - 85-95 = strong/apply-now, 78-84 = solid, 65-77 = stretch. Before granting >=85,
     re-read that job's full `req` in `kept_candidates.json`.
3. Write scores in batches of ~70 as `<RUN_DIR>/scores_p1.jsonl`, `scores_p2.jsonl`, …
   one JSON object per line:
   `{"jid": "...", "fit": "High", "score": 92, "why": "...", "watch": "...",
     "category": "...", "industry": "..."}`
4. Re-run the pipeline. `11_scores` merges the batches, refuses to build on partial
   coverage (missing/extra jids exit non-zero), and the rest runs through.

With `scoring.mode: heuristic` (unattended runs) the pipeline builds straight through
on the keyword-overlap fallback score.

## Verification (never skip)

- `06_details` loops fetch -> `verify_details.py --delete` until the identity gate is
  green: every detail file's body must actually describe its id's company+title.
  Corrupt or empty files are deleted and re-fetched. Never build while this gate is red.
- `13_verify_wb` re-checks the built workbook: no already-seen id leaks (exclusion CSVs
  + master library), No. sequence, score ordering, status column, header layout, and
  sheet-ids == kept-ids. Non-zero exit means do not ship the file.
- Rule-function unit tests (fixtures are real sentences from past runs, including every
  bug that ever slipped through):
  `uv run --with pytest --with pyyaml python -m pytest tests/ -q -s`

## Filters (deterministic gate, phase 05 + 07)

Detailed in `references/filter_rules.md`. Summary: >= N years (floor of ALL hard
year clauses; every clause is preserved for Phase 7), senior titles (incl.
AVP/SVP/EVP/Vice President), non-Singapore base/business, direct-sales/MLM patterns
(incl. roadshow perk-bait titles and face-to-face-marketing copy), dead/closed/ghost
listings (S1+S3), config blacklists, and optional contract/part-time drops driven by
LinkedIn's structured Employment-type field first, header text second.

## Unattended / scheduled runs

Schedule a session that invokes this skill with `scoring.mode: heuristic`, or let it
halt at scoring and finish interactively later (`.done` markers keep the halt cheap).
Keep volume human-like: the defaults (10-card pages, 1-2s jitter, 200-card query cap)
matched a 673-detail run with zero 429s. On guest-probe failure the pipeline stops
with a clear message rather than writing an empty sheet.

## Troubleshooting (field-tested)

- **02_probe fails / guest pages empty** -> the guest endpoint moved or is blocked for
  this network. Try `FIREFLY_DRIVER=direct` (if the shell has a proxy), or fetch
  details via the browser fallback: `python scripts/fetch_details.py --config
  config.yaml --run <RUN_DIR> --mode browser` (needs browser-harness; slow).
- **429s / error statuses in raw_details.jsonl** -> the worker already backs off and
  the pipeline's chunk loop re-fetches on the next pass; widen
  `pipeline.detail_fetch_interval` if they persist.
- **verify_details reports CORRUPT** -> a detail body doesn't match its id (browser
  fallback race, or a guest anomaly). The gate deletes it; the details loop re-fetches
  exactly those ids. If one id never verifies, it ships as a gap (no_detail), never
  as a wrong JD.
- **UnicodeEncodeError mentioning surrogates** -> a script piped into browser-harness
  contains raw non-ASCII. Workers (`_*_worker.py`) must stay pure ASCII (`\uXXXX`
  escapes); run everything with `PYTHONUTF8=1`.
- **eval wrapper returns null from a .js file** -> the file must START with `(`;
  leading `//` comments make generic eval wrappers swallow the IIFE's return value.
- **Workbook rebuilt after a fix** -> safe: `build_xlsx.py` updates the master library
  idempotently (first-seen wins) and `--date YYYY-MM-DD` keeps the original filename.
- **Reset "already seen"** -> delete or trim `state/master_jobs.jsonl`.

## Reference files

- `references/linkedin_params.md` — guest API endpoints (search paging + jobPosting
  detail), URL params (geoId, f_E, f_TPR, sortBy), rate-limit field notes.
- `references/filter_rules.md` — exact years / senior / Singapore / MLM logic and the
  noise each rule must ignore.
- `references/v3_format.md` — the three-sheet workbook layout and master-library
  semantics.
- `config.yaml` — the only file the user normally edits (queries, filters, profile,
  paths, pipeline knobs).
