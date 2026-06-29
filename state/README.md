Runtime state (auto-created):
- master_jobs.jsonl : persistent dedupe library; build_xlsx appends each run's shortlist.
- run_<YYYY-MM-DD>/ : per-run workspace (cards, details, candidates, kept/dropped, scores).
Delete master_jobs.jsonl to reset what counts as "already seen".
