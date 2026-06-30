#!/usr/bin/env bash
# Read every candidate's LinkedIn detail page, resumably.
# Usage: bash read_details.sh <SKILL_DIR> <RUN_DIR> <session> [MAX] [BROWSER_ID]
#   MAX        : stop after reading this many NEW pages this pass (0 = unlimited). Bounding each
#                pass + using a fresh session per pass avoids the session degradation that starts
#                returning empty pages after ~65 reads in a single session.
#   BROWSER_ID : if given, (re)open the browser on <session> first, so a freshly-named session works
#                (the watchdog starts each pass on a new session).
# Idempotent: skips ids that already have a non-empty detail file, so re-running resumes.
set -u
SKILL_DIR="$1"; RUN_DIR="$2"; SESSION="${3:-ljh}"; MAX="${4:-0}"; BROWSER_ID="${5:-}"
EXE="$(command -v browser-act || echo "$HOME/.local/bin/browser-act.exe")"
DET_JS="$SKILL_DIR/scripts/detail_extract.js"
CLICK_JS="$SKILL_DIR/scripts/click_seemore.js"
mkdir -p "$RUN_DIR/details"

# When invoked with a fresh session (e.g. by the watchdog), open the browser on it first.
if [ -n "$BROWSER_ID" ]; then
  "$EXE" --session "$SESSION" browser open "$BROWSER_ID" "https://www.linkedin.com/feed/" >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
fi

ids=$(grep -oE '"id": ?"[0-9]+"' "$RUN_DIR/candidates.json" | grep -oE '[0-9]+')
got=0; streak=0
for id in $ids; do
  f="$RUN_DIR/details/$id.json"
  [ -s "$f" ] && continue
  "$EXE" --session "$SESSION" navigate "https://www.linkedin.com/jobs/view/$id/" >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
  # Expand the collapsed JD ("see more") BEFORE reading, else the description and Key
  # Requirements come out truncated. Click, wait for re-render, then read the full text.
  cat "$CLICK_JS" | "$EXE" --session "$SESSION" eval --stdin >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
  cat "$DET_JS" | "$EXE" --session "$SESSION" eval --stdin > "$f" 2>/dev/null
  sz=$(wc -c < "$f")
  if [ "$sz" -lt 50 ]; then
    rm -f "$f"; echo "empty $id (retry later)"; streak=$((streak+1))
    # A burst of empties means the session degraded; bail so a fresh session can take over.
    if [ "$streak" -ge 5 ]; then echo "BAIL: $streak empties in a row (session degraded)"; break; fi
  else
    echo "read $id (${sz}b)"; got=$((got+1)); streak=0
    if [ "$MAX" -gt 0 ] && [ "$got" -ge "$MAX" ]; then echo "CHUNK done ($got)"; break; fi
  fi
  sleep $((RANDOM % 3 + 1))   # 1-3s jitter: gentler on LinkedIn, more human-like over long runs
done
echo "DONE pass: read $got new; saved $(ls -1 "$RUN_DIR/details" | wc -l) total"
