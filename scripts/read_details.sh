#!/usr/bin/env bash
# Read every candidate's LinkedIn detail page, resumably AND with per-page identity verification.
# Usage: bash read_details.sh <SKILL_DIR> <RUN_DIR> <session> [MAX] [BROWSER_ID]
#   MAX        : stop after reading this many NEW pages this pass (0 = unlimited). Bounding each
#                pass + using a fresh session per pass avoids the session degradation that starts
#                returning empty pages after ~65 reads in a single session.
#   BROWSER_ID : if given, (re)open the browser on <session> first, so a freshly-named session works
#                (the watchdog starts each pass on a new session).
#
# Why the settle + verify dance below:  /jobs/view/<id>/ is an in-place SPA route change. The URL
# updates immediately but the detail pane re-renders one navigation cycle LATER. A naive
# "navigate; wait stable; read" therefore captures the PREVIOUS/neighbouring job and saves it under
# the wrong id (the JD-crosstalk bug). So we (1) wait until the header is non-empty and STABLE
# across two reads, (2) verify the captured body actually describes the requested job, and
# (3) on mismatch force a hard re-navigation (neutral page -> target) and retry. A page that can
# never be verified is left UNREAD (fail closed) rather than saved wrong.
#
# Idempotent: skips ids that already have a verified detail file, so re-running resumes.
set -u
SKILL_DIR="$1"; RUN_DIR="$2"; SESSION="${3:-ljh}"; MAX="${4:-0}"; BROWSER_ID="${5:-}"
EXE="$(command -v browser-act || echo "$HOME/.local/bin/browser-act.exe")"
DET_JS="$SKILL_DIR/scripts/detail_extract.js"
CLICK_JS="$SKILL_DIR/scripts/click_seemore.js"
HDR_JS="$SKILL_DIR/scripts/job_header.js"
VERIFY="$SKILL_DIR/scripts/verify_one.py"
NEUTRAL="https://www.linkedin.com/jobs/"
mkdir -p "$RUN_DIR/details"

nav() { "$EXE" --session "$SESSION" navigate "$1" >/dev/null 2>&1; "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1; }
hdr() { cat "$HDR_JS" | "$EXE" --session "$SESSION" eval --stdin 2>/dev/null; }

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
  ok=0
  for attempt in 1 2 3; do
    # attempt 1: direct nav. retries: bounce through a neutral page first so the SPA is FORCED to
    # unmount the stale detail pane and re-render the target (this is what breaks the off-by-one).
    [ "$attempt" -gt 1 ] && nav "$NEUTRAL"
    nav "https://www.linkedin.com/jobs/view/$id/"
    # settle: wait until the header is non-empty and identical across two consecutive reads.
    prev=""; settled=0
    for w in 1 2 3 4 5 6 7 8; do
      "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
      cur="$(hdr | tr -dc 'A-Za-z0-9')"
      if [ -n "$cur" ] && [ "$cur" = "$prev" ]; then settled=1; break; fi
      prev="$cur"; sleep 1
    done
    # Expand the collapsed JD ("see more") BEFORE reading, else the description and Key
    # Requirements come out truncated. Click, wait for re-render, then read the full text.
    cat "$CLICK_JS" | "$EXE" --session "$SESSION" eval --stdin >/dev/null 2>&1
    "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
    cat "$DET_JS" | "$EXE" --session "$SESSION" eval --stdin > "$f.tmp" 2>/dev/null
    sz=$(wc -c < "$f.tmp" 2>/dev/null || echo 0)
    if [ "$sz" -lt 50 ]; then rm -f "$f.tmp"; continue; fi
    # IDENTITY GATE: the body must actually describe THIS job, or we discard and re-navigate.
    if PYTHONUTF8=1 python "$VERIFY" "$RUN_DIR" "$id" "$f.tmp" >/dev/null 2>&1; then
      mv -f "$f.tmp" "$f"; ok=1; break
    else
      echo "mismatch $id (attempt $attempt) - re-navigating"; rm -f "$f.tmp"; sleep 2
    fi
  done
  if [ "$ok" = 1 ]; then
    echo "read $id (${sz}b)"; got=$((got+1)); streak=0
    if [ "$MAX" -gt 0 ] && [ "$got" -ge "$MAX" ]; then echo "CHUNK done ($got)"; break; fi
  else
    echo "UNVERIFIED $id (left unread - fail closed)"; streak=$((streak+1))
    # A burst of failures means the session degraded; bail so a fresh session can take over.
    if [ "$streak" -ge 5 ]; then echo "BAIL: $streak failures in a row (session degraded)"; break; fi
  fi
  sleep $((RANDOM % 3 + 1))   # 1-3s jitter: gentler on LinkedIn, more human-like over long runs
done
echo "DONE pass: read $got new; saved $(ls -1 "$RUN_DIR/details" | wc -l) total"
