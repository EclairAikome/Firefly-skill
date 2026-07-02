# LinkedIn endpoints & parameters

## Guest search API (cards) — the primary card source

```
https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?
    keywords=<q>&location=Singapore&geoId=102454443&f_E=2%2C3&f_TPR=r604800&sortBy=DD&start=N
```

- Returns an HTML fragment of `<li>` cards. **Pages are 10 cards**, not 25: advance
  `start` by the number of cards actually returned; a short (<10) or empty page is the
  last one. (A +25 stride silently skips 60% of results — field-tested mistake.)
- Per-card fields: job id (`data-entity-urn="urn:li:jobPosting:<id>"`), title
  (`base-search-card__title`), company (`base-search-card__subtitle`), location
  (`job-search-card__location`), posted date (`<time datetime="YYYY-MM-DD">`).
- The `f_E` filter is loose on this endpoint — senior roles come through and must be
  dropped by the pipeline's own rules (they are: prefilter + parse).
- No login required, but fetching through the logged-in Chrome's network stack (the
  drivers do this) inherits the user's proxy and avoids guest rate-limits. A bare
  urllib from a shell without a proxy 404s in networks where LinkedIn is blocked.

## Guest jobPosting API (details) — the primary JD source

```
https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<jobId>
```

- Returns the full detail HTML: title (`top-card-layout__title`), company
  (`topcard__org-name-link`), location (`topcard__flavor--bullet`), posted
  (`posted-time-ago__text`), applicants (`num-applicants__caption`), the COMPLETE
  description (`show-more-less-html__markup` — no "see more" click needed), and the
  structured criteria list (`description__job-criteria-*`: Seniority level,
  Employment type, Job function, Industries).
- HTTP 404 = posting removed (a definitive answer, not a fetch failure).
- "No longer accepting applications" appears in the body for closed listings.
- Because the response is keyed to the id by the request, the logged-in SPA's
  off-by-one crosstalk cannot happen on this path.
- Rate limits, field-tested 2026-07-02: 673 sequential fetches at 1.0–1.6s jitter
  through a logged-in Chrome produced zero 429s.

## Shared query parameters

| Param | Meaning | Values used here |
|---|---|---|
| `keywords` | search terms (URL-encoded) | from `config.search.queries` |
| `location` | display label | `Singapore` |
| `geoId` | location id (authoritative) | `102454443` = Singapore |
| `f_E` | experience level (comma list) | `2,3` = Entry + Associate. (`1`=Intern, `4`=Mid-Senior, `5`=Director, `6`=Exec) |
| `f_TPR` | date posted | `r604800` = past week, `r2592000` = past month |
| `sortBy` | sort order | `DD` = most recent, `R` = relevance |

## Logged-in pages (browser fallback only)

- Job detail: `https://www.linkedin.com/jobs/view/<jobId>/`. The trailing number in
  any job URL is the stable id used for de-duplication.
- The logged-in detail pane is an in-place SPA route change: the URL updates before
  the pane re-renders, so a too-early read captures the PREVIOUS job. The browser
  fallback (`fetch_details.py --mode browser`) settles the header, clicks "see more",
  extracts, and verifies identity — fail closed.
- The logged-in SEARCH list is virtualized and does not render on scripted scrolling
  (scrollTop, scrollIntoView, and CDP mouseWheel all fail on the 2026-07 layout).
  There is deliberately NO browser fallback for cards — if the guest search endpoint
  dies, fail loud instead of pretending.
