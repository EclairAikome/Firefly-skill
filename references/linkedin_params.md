# LinkedIn job-search URL parameters

Base: `https://www.linkedin.com/jobs/search/?` + query string.

| Param | Meaning | Values used here |
|---|---|---|
| `keywords` | search terms (URL-encoded) | from `config.search.queries` |
| `location` | display label | `Singapore` |
| `geoId` | location id (authoritative) | `102454443` = Singapore |
| `f_E` | experience level (comma list) | `2,3` = Entry + Associate. (`1`=Intern, `4`=Mid-Senior, `5`=Director, `6`=Exec) |
| `f_TPR` | date posted | `r604800` = past week, `r2592000` = past month |
| `sortBy` | sort order | `DD` = most recent, `R` = relevance |

Example:
```
https://www.linkedin.com/jobs/search/?keywords=Associate%20Product%20Manager&location=Singapore&geoId=102454443&f_E=2%2C3&f_TPR=r2592000&sortBy=DD
```

Notes:
- Job detail pages: `https://www.linkedin.com/jobs/view/<jobId>/`. The trailing number in any
  job URL is the stable job id used for de-duplication.
- The search results list is virtualized — only ~7-25 cards load until you scroll. `scroll.js`
  scrolls the list's scrollable ancestor to load more.
- Must be logged in. A logged-out session is walled hard; the imported-profile browser keeps
  the user's session so results render fully (and "applied" badges show).
