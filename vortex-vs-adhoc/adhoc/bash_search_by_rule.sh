#!/usr/bin/env bash
# Ad-hoc Bash/grep equivalent of policy/design_health.yaml (7 rules).
#
# Procedural: each rule is hand-wired. Editing thresholds / patterns means
# finding the right block, editing carefully, re-testing interactions.
#
# This is intentionally verbose — it mirrors how farm "helper scripts" grow.
set -euo pipefail

LOG="${1:-}"
if [[ -z "$LOG" || ! -f "$LOG" ]]; then
  echo "Usage: $0 <logfile>" >&2
  exit 2
fi

OUT_DIR="${OUT_DIR:-.}"
REPORT="${OUT_DIR}/bash_report.txt"
: >"$REPORT"

ts="$(date -Is)"
echo "# bash ad-hoc report  log=$LOG  ts=$ts" | tee -a "$REPORT"
echo "# engine=bash_grep_procedural" | tee -a "$REPORT"
echo | tee -a "$REPORT"

# ---------- helpers (boilerplate every script reimplements) ----------
count_matches() {
  local pat="$1"
  # grep -c exits 1 on zero matches — swallow that
  grep -Eci -- "$pat" "$LOG" 2>/dev/null || true
}

first_hit_line() {
  local pat="$1"
  local n
  n="$(grep -Eni -- "$pat" "$LOG" 2>/dev/null | head -1 | cut -d: -f1 || true)"
  echo "${n:-0}"
}

first_hit_text() {
  local pat="$1"
  grep -Ei -- "$pat" "$LOG" 2>/dev/null | head -1 || true
}

emit_rule() {
  local severity="$1" name="$2" count="$3" thr="$4" note="$5" pat="$6"
  local flag="ok"
  if (( count > thr )); then flag="TRIGGERED"; fi
  printf '[%-7s] %-22s count=%5d thr=%s  %s\n' \
    "$severity" "$name" "$count" "$thr" "$flag" | tee -a "$REPORT"
  if [[ "$flag" == "TRIGGERED" ]]; then
    local ln txt
    ln="$(first_hit_line "$pat")"
    txt="$(first_hit_text "$pat")"
    printf '           first @%s: %s\n' "$ln" "${txt:0:100}" | tee -a "$REPORT"
    echo "  note: $note" | tee -a "$REPORT"
  fi
}

# ---------- rule 1: setup_violation ----------
# threshold 0 — any hit triggers
PAT_SETUP='VIOLATED.*\bsetup\b|Setup[[:space:]]+slack[[:space:]]+-[[:digit:]]'
CNT_SETUP="$(count_matches "$PAT_SETUP")"
# hard-coded threshold (change here AND in docs AND in sibling scripts)
THR_SETUP=0
emit_rule error setup_violation "$CNT_SETUP" "$THR_SETUP" \
  "Timing setup fails (any count is actionable)." "$PAT_SETUP"

# ---------- rule 2: hold_violation ----------
PAT_HOLD='VIOLATED.*\bhold\b|Hold[[:space:]]+slack[[:space:]]+-[[:digit:]]'
CNT_HOLD="$(count_matches "$PAT_HOLD")"
THR_HOLD=0
emit_rule error hold_violation "$CNT_HOLD" "$THR_HOLD" \
  "Timing hold fails." "$PAT_HOLD"

# ---------- rule 3: max_transition ----------
# noise floor: only trigger if count > 10
PAT_MAXTRAN='max_transition|MaxTran|MAXTRAN'
CNT_MAXTRAN="$(count_matches "$PAT_MAXTRAN")"
THR_MAXTRAN=10
emit_rule warning max_transition "$CNT_MAXTRAN" "$THR_MAXTRAN" \
  "Flag only if more than 10 MaxTran hits (noise floor)." "$PAT_MAXTRAN"

# ---------- rule 4: drc_error ----------
PAT_DRC='\bDRC\b.*(error|violation|fail)|ERROR:[[:space:]]*DRC'
CNT_DRC="$(count_matches "$PAT_DRC")"
THR_DRC=0
emit_rule error drc_error "$CNT_DRC" "$THR_DRC" \
  "Hard DRC errors." "$PAT_DRC"

# ---------- rule 5: antenna ----------
# noise floor: ignore below 5
PAT_ANT='\bANTENNA\b|antenna[[:space:]]+violation'
CNT_ANT="$(count_matches "$PAT_ANT")"
THR_ANT=5
emit_rule warning antenna "$CNT_ANT" "$THR_ANT" \
  "Antenna noise below 5 is ignored." "$PAT_ANT"

# ---------- rule 6: congestion_hotspot ----------
PAT_CONG='Congestion[[:space:]]*>[[:space:]]*0\.(8|9)|Overflow[[:space:]]*>[[:space:]]*[5-9][[:digit:]]'
CNT_CONG="$(count_matches "$PAT_CONG")"
THR_CONG=0
emit_rule warning congestion_hotspot "$CNT_CONG" "$THR_CONG" \
  "Routing congestion / overflow hotspots." "$PAT_CONG"

# ---------- rule 7: fatal_or_abort ----------
PAT_FATAL='\bFATAL\b|\bABORT\b|stack[[:space:]]+trace|INTERNAL[[:space:]]+ERROR'
CNT_FATAL="$(count_matches "$PAT_FATAL")"
THR_FATAL=0
emit_rule fatal fatal_or_abort "$CNT_FATAL" "$THR_FATAL" \
  "Tool death / internal errors — stop and escalate." "$PAT_FATAL"

echo | tee -a "$REPORT"
echo "# done bash ad-hoc" | tee -a "$REPORT"

# Machine-readable side dump (reinvented every time)
JSON_OUT="${OUT_DIR}/bash_report.json"
python3 - <<PY >"$JSON_OUT"
import json
print(json.dumps({
  "engine": "bash_grep_procedural",
  "log": "$LOG",
  "timestamp": "$ts",
  "results": [
    {"name":"setup_violation","severity":"error","count":int("$CNT_SETUP"),"threshold":int("$THR_SETUP"),"triggered":int("$CNT_SETUP")>int("$THR_SETUP")},
    {"name":"hold_violation","severity":"error","count":int("$CNT_HOLD"),"threshold":int("$THR_HOLD"),"triggered":int("$CNT_HOLD")>int("$THR_HOLD")},
    {"name":"max_transition","severity":"warning","count":int("$CNT_MAXTRAN"),"threshold":int("$THR_MAXTRAN"),"triggered":int("$CNT_MAXTRAN")>int("$THR_MAXTRAN")},
    {"name":"drc_error","severity":"error","count":int("$CNT_DRC"),"threshold":int("$THR_DRC"),"triggered":int("$CNT_DRC")>int("$THR_DRC")},
    {"name":"antenna","severity":"warning","count":int("$CNT_ANT"),"threshold":int("$THR_ANT"),"triggered":int("$CNT_ANT")>int("$THR_ANT")},
    {"name":"congestion_hotspot","severity":"warning","count":int("$CNT_CONG"),"threshold":int("$THR_CONG"),"triggered":int("$CNT_CONG")>int("$THR_CONG")},
    {"name":"fatal_or_abort","severity":"fatal","count":int("$CNT_FATAL"),"threshold":int("$THR_FATAL"),"triggered":int("$CNT_FATAL")>int("$THR_FATAL")},
  ]
}, indent=2))
PY
