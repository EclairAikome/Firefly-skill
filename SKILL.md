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
  It searches LinkedIn with a logged-in browser, reads every job detail page, drops
  roles needing >= N years, non-Singapore roles, direct-sales/MLM roles, and anything
  already applied to, scores fit, and writes a dated v3-style .xlsx (Job Applications +
  This-Week by Fit + Summary) sorted by match score, deduping against past runs. Do NOT
  use it for: applying to jobs or filling application forms (a separate apply skill does
  that); scraping non-LinkedIn sites or product/price data; exporting LinkedIn connections
  or collecting people's profiles for networking/lead-gen; resume writing; or generic
  spreadsheet formatting. This skill is READ-ONLY and is specifically about turning
  LinkedIn job OPENINGS into a fit-ranked shortlist; it never auto-applies.
---

# Firefly-skill

Automates the LinkedIn job-hunt scrape this user runs repeatedly: search both of their
career tracks, read each job's full description, filter hard on the rules they care
about, score fit, and hand back a clean spreadsheet in their established format.

**Scope is deliberately read-only.** Every blocker in the user's past runs (captchas,
"I'm not a robot" walls, garbled Easy Apply modals, ATS login walls) came from the
*apply* step, not the *scrape* step. Logged-in scraping almost never trips anti-bot.
Keeping this skill to scrape -> filter -> export is what makes it safe to run unattended.
Applying is handled by the user's separate apply skill — do not apply here.

## Prerequisites (check once per run, set up once ever)

1. `browser-act` CLI installed and authed. Verify:
   ```bash
   browser-act get-skills core --skill-version 2.0.2   # expect skill_compat: ok, api_key: configured
   ```
   If missing, see the browser-act skill. Anti-bot stealth features need the free API key,
   but for plain logged-in Chrome scraping the key is not strictly required.

2. A reusable logged-in browser. Check first:
   ```bash
   browser-act browser list        # look for the browser named in config (default: linkedin-jobhunt)
   ```
   - **Exists** -> reuse it. This is the key to unattended runs: no Confirmation Gate fires.
   - **Missing** -> create it ONCE (this needs one human confirmation, per browser-act's gate):
     run `browser-act get-skills advanced`, then `browser-act browser list-profiles`, present the
     plan, and after the user confirms:
     ```bash
     browser-act browser create --name "linkedin-jobhunt" --type chrome \
       --desc "LinkedIn job scraping; imported Chrome login" --source-profile <profile_id>
     ```
   Creating it copies the user's Chrome login into an isolated browser; their real Chrome is
   untouched afterward. Importing may briefly close their Chrome.

## How to run the pipeline

Everything is driven from the skill directory. Set `SKILL_DIR` to this skill's folder
(`~/.claude/skills/Firefly-skill` -> `C:\Users\<you>\.claude\skills\Firefly-skill`)
and read `config.yaml` for queries, filters, paths, and the browser/session names.

**Run all browser-act + script commands through the Bash tool, not PowerShell.** PowerShell's
pipe corrupts `eval --stdin`; Bash piping (`cat file.js | browser-act ... eval --stdin`) works.
Always run Python with `PYTHONUTF8=1` and pass **Windows-style paths** to Python (MSYS `/c/...`
paths break native Python `open()`).

### Phase 1 — exclusion set (dedupe vs past)
```bash
PYTHONUTF8=1 uv run --with pyyaml python "<SKILL_DIR>\scripts\build_exclusion.py" \
  --config "<SKILL_DIR>\config.yaml" --run "<RUN_DIR>"
```
`<RUN_DIR>` is `state\run_<YYYY-MM-DD>` under the skill dir; create it at the start of the run.
Builds the already-applied/already-seen set from the persistent master library
(`state\master_jobs.jsonl`) plus any history sources in config (e.g. a past `RESULTS.csv`).
Dedupe key is the LinkedIn job id from the URL; normalized company+title is the backup.

### Phase 2 — open session, verify login
```bash
S=$(grep session_name "<SKILL_DIR>\config.yaml")   # or just use the configured session name, e.g. ljh
browser-act --session ljh browser open <browser_id> "https://www.linkedin.com/feed/"
browser-act --session ljh get title                # expect a title containing "Feed"
```
If the title is a login/guest page, the imported login expired. Try one re-import
(`browser-act browser import-profile <browser_id> <profile_id>`) and re-check. If still not
logged in, do NOT hang: write the run report noting "login expired", optionally emit a
`browser-act --session ljh remote-assist --objective "Log in to LinkedIn"` link, and stop.

### Phase 3 — search and extract cards
Generate the per-query URLs from config, then drive all searches with one helper:
```bash
PYTHONUTF8=1 uv run --with pyyaml python "<SKILL_DIR>\scripts\gen_search_urls.py" \
  --config "<SKILL_DIR>\config.yaml" --run "<RUN_DIR>"
bash "<SKILL_DIR>\scripts\search.sh" "<SKILL_DIR>" "<RUN_DIR>" ljh
```
`search.sh` navigates each query (URL shape in `references/linkedin_params.md`), scrolls
`scroll_rounds` times, and extracts cards to `<RUN_DIR>\cards\<query>.json`.

Do NOT use `get markdown` on LinkedIn search pages — it pulls in a huge blob of injected
localization JSON. The `eval` DOM extractor (anchor `a[href*="/jobs/view/"]`) is clean and
survives LinkedIn class-name churn.

### Phase 4 — aggregate + dedupe
```bash
PYTHONUTF8=1 python "<SKILL_DIR>\scripts\aggregate_candidates.py" --run "<RUN_DIR>" \
  --exclusion "<RUN_DIR>\exclusion.json" --out "<RUN_DIR>\candidates.json"
```
Merges all query cards, dedupes by job id, strips the " with verification" title suffix,
removes anything in the exclusion set.

### Phase 5 — read every detail page (chunked, resumable)
Reading the JD of *every* candidate is required — cards never show the experience bar.
`read_details.sh` clicks the JD's "see more" toggle before reading, so the FULL description
and Key Requirements are captured. This matters: LinkedIn hides the overflow of the JD, and
the hidden text is not in the page's innerText until "see more" is clicked — skip it and the
JD/requirements come out truncated with a trailing "… more".
Each page is ~15-20s, so a long list will blow the tool timeout. Read in chunks of ~15 and
skip any id already saved (idempotent resume):
```bash
bash "<SKILL_DIR>\scripts\read_details.sh" "<SKILL_DIR>" "<RUN_DIR>" ljh
# re-run the same command after a timeout; it only fetches the missing ids
```

### Phase 6 — rule filter + parse (deterministic)
```bash
PYTHONUTF8=1 uv run --with pyyaml python "<SKILL_DIR>\scripts\parse_details.py" \
  --config "<SKILL_DIR>\config.yaml" --run "<RUN_DIR>" --out "<RUN_DIR>\kept_candidates.json"
```
**Always run this script — do not hand-filter years/Singapore/MLM by eye.** The noise-handling
(ignoring LinkedIn's auto skill tags like `• 3+ years of work experience with <skill>`, plus
`X year growth` and `median tenure` lines) is exactly what a manual read gets wrong: it will
either keep a 5-year role or drop a "1-3 years" one. Let the script decide the hard rules.

This applies the hard rules and writes both kept and dropped (with reasons). The rules
(detailed in `references/filter_rules.md`):
- **>= N years -> drop.** Parse the real requirement sentence only. IGNORE LinkedIn's auto
  skill tags (`• 3+ years of work experience with <skill>`), the `X year growth` company
  insight, and `median tenure` lines — these are NOT employer requirements.
- **Not Singapore -> drop.** Base/business must be SG. APAC-remote, `(Hong Kong)`, `- MY`,
  foreign-only postings are out.
- **Direct-sales / MLM -> drop** (toggle `drop_direct_sales_mlm`). Pattern-matched on company
  name and copy (e.g. "Organisation", "Marketing Group", "invest in yourself", commission-only).

### Phase 7 — score fit (YOU, in context)
Read `kept_candidates.json`. For each kept job, read its `jd` and `req` and judge fit against
the user's profile (from `config.yaml` `profile.resume_keywords` / tracks). Write
`<RUN_DIR>\scores.json` keyed by job id:
```json
{ "4434061987": {
    "fit": "High", "score": 92,
    "why": "one specific sentence tying the JD to the user's real experience",
    "watch": "the single biggest caveat (years gap, domain, contract, etc.)",
    "category": "AI / Product", "industry": "Gaming / Tech" } }
```
Scoring guidance — be concrete and honest, this is the whole value of the skill:
- Anchor `why` in the user's actual background, not generic praise.
- `watch` should name the real risk (e.g. "asks ~2 yrs, you're sub-1yr" / "healthcare domain"),
  so the user can triage fast.
- Score 85-95 = strong/apply-now, 75-84 = solid, 65-74 = stretch. Sort happens on `score`.
- If this is a headless/unattended run where you cannot deliberate, skip scores.json; the
  builder falls back to a keyword-overlap heuristic so the run still completes.

### Phase 8 — build the workbook + report
```bash
PYTHONUTF8=1 uv run --with openpyxl --with pyyaml python "<SKILL_DIR>\scripts\build_xlsx.py" \
  --config "<SKILL_DIR>\config.yaml" --run "<RUN_DIR>"
PYTHONUTF8=1 python "<SKILL_DIR>\scripts\run_report.py" --run "<RUN_DIR>"
```
`build_xlsx.py` writes a dated workbook to the configured output dir with THREE sheets that
mirror `SG_LinkedIn_Jobs_June2026_v3.xlsx` (see `references/v3_format.md`):
1. **Job Applications** (21 cols) — sorted by match score, highest first; `No.` follows that order.
2. **This-Week by Fit** (13 cols) — same order; Rank = score rank; includes Why / Watch-outs.
3. **Summary** (3 cols) — funnel totals, by-fit-tier, by-category, exclusion breakdown, methodology.
It also appends this run's job ids to `state\master_jobs.jsonl` so the next run dedupes them out.

Then close the session but keep the browser for reuse:
```bash
browser-act session close ljh
```

## Unattended / scheduled runs

Manual invocation is the default. For hands-off recurrence, schedule a Claude session that
invokes this skill (use the `schedule` skill / scheduled tasks). It runs with zero human
input because (a) the browser already exists so no Confirmation Gate fires, and (b) it is
read-only so anti-bot rarely triggers. Two guardrails for unattended mode: keep volume
human-like (cap queries and scroll rounds in config), and on login-expiry fail loud in the
report rather than hanging. Fit scoring still works unattended via the heuristic fallback,
but agent scoring is better when a session is interactive.

## Troubleshooting (hard-won)
- **0 cards / 0 detail text extracted** -> LinkedIn changed markup. The extractors lean on
  stable signals (`/jobs/view/<id>` hrefs, `main` innerText) but verify `references/` and the
  JS if a run returns empty; abort with a clear message rather than writing an empty sheet.
- **`eval --stdin` returns nothing** -> you used PowerShell. Use Bash.
- **UnicodeEncodeError / cp1252** -> add `PYTHONUTF8=1` and `encoding="utf-8"` (emojis show up
  in company names and JDs).
- **FileNotFoundError on `/c/...`** -> you passed an MSYS path to Python. Use a Windows path.
- **Tool timeout mid detail-read** -> just re-run `read_details.sh`; it resumes.

## Reference files
- `references/linkedin_params.md` — search URL params (geoId, f_E, f_TPR, sortBy).
- `references/filter_rules.md` — exact years / Singapore / blacklist logic and the noise to ignore.
- `references/v3_format.md` — the three-sheet layout, headers, fonts, fills, widths, Summary spec.
- `config.yaml` — the only file the user normally edits (queries, filters, profile, paths).
