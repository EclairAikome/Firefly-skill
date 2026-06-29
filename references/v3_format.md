# Output workbook format (mirror of SG_LinkedIn_Jobs_June2026_v3.xlsx)

Built by `scripts/build_xlsx.py`. Three sheets. Shared header style: Arial 11 bold, white text
(`FFFFFFFF`) on solid fill `FF1F4E78`, row-1 frozen (`freeze_panes="A2"`). Data font Arial 10.
Links shown as text `LinkedIn job link` hyperlinked to the job URL (Arial 10, `FF0563C1`, underline).
Dates stored as real dates with number format `yyyy-mm-dd`.

## Sheet 1: "Job Applications" (21 columns)
Sorted by match score, highest first. `No.` is 1..N in that same order.

| Col | Header | Source |
|---|---|---|
| A | No. | row index after score-sort |
| B | Company Name | scraped |
| C | Industry / Business Area | agent (or blank in heuristic mode) |
| D | Job Title | scraped (suffix " with verification" stripped) |
| E | Job Description (JD) | parsed from detail page |
| F | Key Requirements | parsed (Requirements/Qualifications block) |
| G | Application Link | hyperlink "LinkedIn job link" -> /jobs/view/<id>/ |
| H | Application Deadline | "TBD" |
| I | Date Applied | blank |
| J | Application Status | "Not Applied" |
| K | Interview Stage | blank |
| L | Contact Person | blank |
| M | Referral (Y/N) | blank |
| N | Priority | High/Medium/Low from score |
| O | Notes / Follow-up | "Posted ...; <work>; <loc>; Fit ...; matched: <category>" |
| P | Company Size | blank (not reliably scrapable) |
| Q | Size Tier | blank |
| R | This-Week Target | "YES" |
| S | Location | scraped base |
| T | Date Posted | absolute date from relative ("X days ago") |
| U | Category | agent (or guessed) |

Column widths: A5 B24 C22 D30 E60 F46 G32 H13 I11 J16 K15 L13 M11 N9 O34 P15 Q17 R14 S22 T12 U16.
Wrap text on C, E, F, O, S.

## Sheet 2: "This-Week by Fit" (13 columns)
Same order as sheet 1 (Rank = score rank).

| Col | Header |
|---|---|
| A | Rank |
| B | Fit (High / Medium-High / Medium) |
| C | Score (0-100) |
| D | Why it fits you |
| E | Watch-outs |
| F | Company Name |
| G | Company Size (blank) |
| H | Job Title |
| I | Category |
| J | Industry / Business Area |
| K | Location |
| L | Date Posted |
| M | Application Link |

Widths: A6 B13 C7 D55 E42 F24 G13 H30 I18 J22 K20 L12 M18. Wrap text on D, E.

## Sheet 3: "Summary" (3 columns)
Mirrors v3's Summary layout, adapted to a scrape run. Title row (Arial 13 bold `1F4E78`), then
small tables each with a dark-blue sub-header row:
1. **Scrape funnel**: Stage | Count (raw cards, unique, excluded, candidates, read, final).
2. **By fit tier**: Fit Tier | # Roles.
3. **By category**: Category | # Roles.
4. **Excluded after reading JD**: Reason | # Roles (years / not_singapore / direct_sales_mlm / no_detail).
5. **Methodology footer**: search params (geoId, f_E, f_TPR), queries, dedupe method, filter
   thresholds, compiled date, read-only note.

v3 also had "By Company Size (Apply Order)" and "All by Fit" sheets; those are intentionally
omitted (company size is not reliably scrapable, and the shortlist is small).

## Master dedupe library
`state/master_jobs.jsonl` — one JSON object per surfaced job (`jid`, `company`, `title`, `date`).
`build_xlsx.py` appends the final shortlist each run; `build_exclusion.py` reads it next run so a
job is never surfaced twice. Delete or trim this file to reset what counts as "already seen".
