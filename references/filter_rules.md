# Filter rules (the deterministic gate before agent scoring)

Implemented in `scripts/lib_common.py`, applied in `scripts/parse_details.py`.

## 1. Minimum required experience (`min_required_years`)
Drop a job when its minimum required experience is `>= filters.max_years_exclusive` (default 3).

The hard part is reading the *employer's* requirement and not the noise LinkedIn injects:
- **IGNORE** auto skill tags: lines like `• 3+ years of work experience with <skill>`. These are
  LinkedIn's inferred skill-gap widget, present on most jobs, NOT the employer's bar. (This is the
  single biggest false-positive source — it made a content-creator role look like it needed 3 yrs.)
- **IGNORE** company-insight noise: `2 year growth`, `median employee tenure: 4 years`,
  `8% increase`, `our history spans 80 years`, `founded 1990`.
- **IGNORE** soft mentions (`preferred`, `plus`, `nice to have`, `advantage`, `asset`, `bonus`,
  `ideally`) unless the same line also says `minimum` / `at least` / `required` / `must`.
- A line counts only if it has an experience-context word (`experience`, `minimum`, `at least`,
  `require`, `track record`, `years in`, `years of`).
- Ranges take the low end: `2-3 years` -> 2, `3-5 years` -> 3, `3~5` -> 3, `3+ years` -> 3.
- The job's floor = the smallest minimum across hard requirement lines (lenient). The agent's
  Phase 7 read is the safety net for the rare ambiguous job that slips through.

## 2. Singapore base/business (`is_singapore`)
With `filters.require_singapore: true`, keep only SG roles.
- Keep if the location contains `singapore` (covers `Singapore, Singapore`, `Singapore (Remote)`,
  `Woodlands ... Singapore`). Remote-from-Singapore still counts as SG base.
- Drop `APAC (Remote)`, and any non-SG-only location.
- Drop even if the location says Singapore when the **title** carries a foreign-market tag
  (`(Hong Kong)`, `- MY`, `Malaysia`, `Jakarta`, `Manila`, `Europe`, `Chennai`, ...): the business
  scenario is not Singapore.

## 3. Direct-sales / MLM blacklist (`is_direct_sales_mlm`)
With `filters.drop_direct_sales_mlm: true`, drop the disguised commission-sales / roadshow roles
the user does not want. Signals:
- Copy phrases: `invest in yourself`, `build the future you want`, `warrior`, `uncapped commission`,
  `commission only`, `no experience needed`, `training provided!!!`, `sales & marketing
  representative`, `campaign marketing & sales`, `travelling opportunities`, `be your own boss`.
- Company-name tokens (`Organisation`/`Organization`/`Org`, `Marketing Group`, `Marketing
  Solutions`, `Business Consulting`) **plus** a sales/entry corroborator in the copy.

This is intentionally narrow. Pure-sales roles at real companies (an SDR at CrowdStrike, a Key
Account Manager at Lyreco) are NOT blacklisted here — they pass the gate and the agent scores them
low on fit instead. Turn the whole rule off with `drop_direct_sales_mlm: false`.

## What the gate does NOT decide
Fit, quality, freelance-gig-vs-real-role, domain mismatch — these are judgment calls left to the
agent in Phase 7 (or the keyword heuristic in unattended mode). The gate only removes the
objective disqualifiers so the agent reads a smaller, cleaner set.
