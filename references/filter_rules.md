# Filter rules (the deterministic gate before agent scoring)

Implemented in `scripts/lib_common.py`; applied card-level in
`scripts/prefilter_cards.py` (rules that need only title/loc) and JD-level in
`scripts/parse_details.py`. Every drop is recorded in `dropped.json` with a `stage`
field, so re-running any stage never duplicates records and the Summary shows one
funnel.

## 1. Minimum required experience (`min_required_years` / `required_years_clauses`)
Drop a job when its minimum required experience is `>= filters.max_years_exclusive`
(default 3).

The hard part is reading the *employer's* requirement and not the noise LinkedIn
injects:
- **IGNORE** auto skill tags: lines like `• 3+ years of work experience with <skill>`.
  These are LinkedIn's inferred skill-gap widget, present on most jobs, NOT the
  employer's bar. (The single biggest false-positive source.)
- **IGNORE** company-insight noise: `2 year growth`, `median employee tenure: 4 years`,
  `our history spans 80 years`, `founded 1990`. NOTE: only the `<N> year growth` FORM
  is noise — the bare word "growth" is a real job domain (`8+ years in growth roles`
  is a real requirement; treating "growth" as noise let an explicit 8-yr DBS
  requirement through on 2026-07-02).
- **IGNORE** soft mentions (`preferred`, `plus`, `nice to have`, `advantage`, `asset`,
  `bonus`, `ideally`) unless the same context also says `minimum` / `at least` /
  `required` / `must`.
- A match counts only with experience context (`X years of/in/as ...`, `experience`
  nearby, or an explicit `+`).
- Ranges take the low end: `2-3 years` -> 2, `3+ years` -> 3.
- The gate uses the FLOOR (smallest minimum) — deliberately lenient. **But every
  clause is preserved** in `kept_candidates.json.years_clauses` and surfaced as
  `yrs_all` in the scoring digest, because stacked conjunctive requirements
  (`3+ yrs product management AND 2+ yrs AI`) gate at the lower number; Phase 7 must
  read the full list before scoring a job High (the Hytech miss, 2026-07-02).

## 2. Senior titles (`is_senior_title`, card-level)
A clear seniority signal in the title is not entry-level whatever the JD says:
senior / sr / lead / principal / staff / director / chief / head of / **vp / avp /
svp / evp / vice president** (the AVP/SVP/spelled-out forms leaked 6 rows on
2026-07-02 before being added). Applied at the card stage — these never cost a
detail fetch.

## 3. Singapore base/business (`is_foreign_card` card-level, `is_singapore` JD-level)
With `filters.require_singapore: true`:
- Card level (conservative): drop only on a positive foreign tag (`(Hong Kong)`,
  `- MY`, `Malaysia`, `Jakarta`, `Manila`, `Europe`, `Chennai`, ...) with no
  "singapore" anywhere; ambiguous cards proceed to the JD check.
- JD level: keep if location contains `singapore` (remote-from-SG counts); drop
  `APAC (Remote)` and foreign-market titles even when the office is SG.

## 4. Direct-sales / MLM (`is_direct_sales_mlm`)
With `filters.drop_direct_sales_mlm: true`, drop disguised commission-sales /
roadshow postings. Signals:
- Copy phrases: `invest in yourself`, `build the future you want`, `warrior`,
  `uncapped commission`, `commission only`, `no experience needed`,
  `training provided!!!`, `sales & marketing representative`,
  `travelling opportunities`, `be your own boss`, **`face-to-face marketing`**,
  **`18 years old and above`** (real SG employers don't print age gates).
- **Perk-bait titles**: two of gym membership / travelling / mentorship strung
  together IN THE TITLE (`"... (Gym membership/Mentorship/Travelling)"`). Real
  employers list perks in the benefits section, not the job title.
- Company-name tokens (`Organisation`, `Marketing Group`, ...) **plus** a sales/entry
  corroborator in the copy.

Intentionally narrow: a perks sentence in a real JD ("benefits include gym
membership") must NOT fire — see tests. Pure-sales roles at real companies pass the
gate and sink on fit score instead.

## 5. Dead / ghost listings (S1 + S3)
`removed` (404 / "job posting has been removed") and `closed` ("no longer accepting
applications") drop outright (toggles `drop_removed` / `drop_closed`); a listing
closed within `fast_close_hours` (default 48h) of posting drops as
`ghost_fast_close` (resume-harvesting pattern).

## 6. Employment type (contract / part-time, off by default)
LinkedIn's structured `Employment type` criteria field (carried by the guest detail)
decides first; the header-text heuristic ("On-site Contract Apply") is the fallback.
A permanent "Contracts Manager" never counts as contract.

## 7. Blacklists
`filters.blacklist_companies` (case-insensitive substring of the employer) and
`filters.blacklist_titles` (whole-word) hard-drop known offenders.

## 8. Same-role reposts (aggregate stage)
Same normalized company+title under different ids within one run collapses to the
newest posting (`posted_date`, falling back to the larger id); the rest drop as
`duplicate_repost`. Cross-run reposts are caught by the exclusion set's
company+title pairs.

## What the gate does NOT decide
Fit, quality, freelance-gig-vs-real-role, domain mismatch, internship-vs-FT — these
are judgment calls left to Phase 7 (or the keyword heuristic in unattended mode).
The gate only removes objective disqualifiers so the agent reads a smaller, cleaner
set — and the agent must still read `yrs_all` and `watch`-worthy signals itself.
