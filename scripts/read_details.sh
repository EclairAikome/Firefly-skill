#!/usr/bin/env bash
# Read every candidate's LinkedIn detail page, resumably.
# Usage: bash read_details.sh <SKILL_DIR> <RUN_DIR> <session>
# Re-run after a tool timeout: it only fetches ids that have no saved detail yet.
set -u
SKILL_DIR="$1"; RUN_DIR="$2"; SESSION="${3:-ljh}"
EXE="$(command -v browser-act || echo "$HOME/.local/bin/browser-act.exe")"
DET_JS="$SKILL_DIR/scripts/detail_extract.js"
CLICK_JS="$SKILL_DIR/scripts/click_seemore.js"
mkdir -p "$RUN_DIR/details"

# candidate ids come from candidates.json ("id":"<digits>")
ids=$(grep -oE '"id": ?"[0-9]+"' "$RUN_DIR/candidates.json" | grep -oE '[0-9]+')
i=0; done=0
for id in $ids; do
  i=$((i+1))
  f="$RUN_DIR/details/$id.json"
  if [ -s "$f" ]; then done=$((done+1)); continue; fi
  "$EXE" --session "$SESSION" navigate "https://www.linkedin.com/jobs/view/$id/" >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
  # Expand the collapsed JD ("see more") BEFORE reading, else the description and Key
  # Requirements come out truncated. Click, wait for re-render, then read the full text.
  cat "$CLICK_JS" | "$EXE" --session "$SESSION" eval --stdin >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
  cat "$DET_JS" | "$EXE" --session "$SESSION" eval --stdin > "$f" 2>/dev/null
  sz=$(wc -c < "$f")
  echo "read $id (${sz}b)"
done
echo "DONE: $done already had details; total candidates $i; saved $(ls -1 "$RUN_DIR/details" | wc -l)"
