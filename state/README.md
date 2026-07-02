Runtime state (auto-created):
- master_jobs.jsonl : persistent dedupe library; build_xlsx merges each run's
  shortlist into it idempotently (first-seen wins).
- run_<YYYY-MM-DD>/ : per-run workspace (cards, cards_raw.jsonl, candidates,
  raw_details.jsonl, details/, kept/dropped, scoring_digest, scores, live_status,
  report.md, pipeline.log, .done/ phase markers).
Delete master_jobs.jsonl to reset what counts as "already seen".
Delete a run dir's .done/<phase> files (or use run_pipeline.py --force-from) to
redo phases; raw_*.jsonl caches let you reparse without refetching.
