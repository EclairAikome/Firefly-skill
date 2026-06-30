#!/usr/bin/env bash
# S2 - pre-build liveness re-check. LinkedIn listings die fast: a job that was live at scrape
# time is often closed or removed by the time the shortlist is read. Right before building the
# workbook, re-ping every KEPT job and record its current status so apply_live_status.py can drop
# the ones that died since the scrape. Read-only; safe to re-run (overwrites live_status.tsv).
#
# Usage: bash recheck_live.sh <SKILL_DIR> <RUN_DIR> <session> [BROWSER_ID]
#   BROWSER_ID : if given, (re)open the browser on <session> first (fresh-session/unattended runs).
set -u
SKILL_DIR="$1"; RUN_DIR="$2"; SESSION="${3:-ljh}"; BROWSER_ID="${4:-}"
EXE="$(command -v browser-act || echo "$HOME/.local/bin/browser-act.exe")"
ST_JS="$SKILL_DIR/scripts/job_status.js"
OUT="$RUN_DIR/live_status.tsv"
: > "$OUT"

if [ -n "$BROWSER_ID" ]; then
  "$EXE" --session "$SESSION" browser open "$BROWSER_ID" "https://www.linkedin.com/feed/" >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
fi

ids=$(grep -oE '"jid": ?"[0-9]+"' "$RUN_DIR/kept_candidates.json" | grep -oE '[0-9]+')
n=0
for id in $ids; do
  "$EXE" --session "$SESSION" navigate "https://www.linkedin.com/jobs/view/$id/" >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
  sleep 1
  st=$(cat "$ST_JS" | "$EXE" --session "$SESSION" eval --stdin 2>/dev/null | tr -d '"' | tr -dc 'a-z')
  [ -z "$st" ] && st="unknown"
  printf '%s\t%s\n' "$id" "$st" >> "$OUT"
  echo "live $id $st"; n=$((n+1))
  sleep $((RANDOM % 2 + 1))   # gentle jitter
done
echo "DONE recheck: $n statuses -> $OUT"
