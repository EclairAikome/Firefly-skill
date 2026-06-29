#!/usr/bin/env bash
# Drive one LinkedIn search per query, scroll, and extract job cards.
# Usage: bash search.sh <SKILL_DIR> <RUN_DIR> <session>
# Prereq: gen_search_urls.py has written <RUN_DIR>/search_urls.tsv and scroll_rounds.txt
set -u
SKILL_DIR="$1"; RUN_DIR="$2"; SESSION="${3:-ljh}"
EXE="$(command -v browser-act || echo "$HOME/.local/bin/browser-act.exe")"
SCROLL_JS="$SKILL_DIR/scripts/scroll.js"
CARD_JS="$SKILL_DIR/scripts/card_extract.js"
ROUNDS=$(cat "$RUN_DIR/scroll_rounds.txt" 2>/dev/null || echo 2)
mkdir -p "$RUN_DIR/cards"

while IFS=$'\t' read -r label url; do
  [ -z "$label" ] && continue
  "$EXE" --session "$SESSION" navigate "$url" >/dev/null 2>&1
  "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
  r=0
  while [ "$r" -lt "$ROUNDS" ]; do
    cat "$SCROLL_JS" | "$EXE" --session "$SESSION" eval --stdin >/dev/null 2>&1
    "$EXE" --session "$SESSION" wait stable >/dev/null 2>&1
    r=$((r+1))
  done
  cat "$CARD_JS" | "$EXE" --session "$SESSION" eval --stdin > "$RUN_DIR/cards/$label.json" 2>/dev/null
  n=$(grep -o '"id"' "$RUN_DIR/cards/$label.json" | wc -l)
  echo "$label: $n cards"
done < "$RUN_DIR/search_urls.tsv"
echo "DONE searches"
