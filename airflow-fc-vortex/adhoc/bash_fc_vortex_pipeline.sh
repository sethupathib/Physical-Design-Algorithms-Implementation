#!/usr/bin/env bash
# Ad-hoc Bash pipeline — intentionally shows two styles:
#   NAIVE=1  → grep JSON rule *names* (false positives on clean logs)
#   default  → python one-liner reads overall (fairer, still procedural)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/results/adhoc}"
NAIVE="${NAIVE:-0}"
mkdir -p "$OUT"

route_naive() {
  local report="$1" design="$2" corner="$3"
  if grep -Eiq 'FATAL|ABORT|INTERNAL ERROR' "$OUT/${design}__${corner}.log"; then
    echo "$design $corner -> PAGE_ONCALL (naive)"
  elif grep -Eiq 'setup_violation|hold_violation|drc_error' "$report"; then
    # BUG: rule names always appear in JSON even when not triggered
    echo "$design $corner -> OPEN_JIRA (naive-grep-FALSE-POSITIVE-RISK)"
  else
    echo "$design $corner -> ARCHIVE (naive)"
  fi
}

route_json() {
  local report="$1" design="$2" corner="$3"
  python3 - "$report" "$design" "$corner" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
d,c=sys.argv[2],sys.argv[3]
o=r["overall"]
branch={"fatal":"PAGE_ONCALL","error":"OPEN_JIRA","warning":"SLACK_WARN","clean":"ARCHIVE"}[o]
print(f"{d} {c} -> {branch} (json-overall={o})")
PY
}

run_one() {
  local design="$1" corner="$2" scenario="$3"
  local log="$OUT/${design}__${corner}.log"
  local report="$OUT/${design}__${corner}.vortex.json"
  python3 "$ROOT/mock_tools/fc_mock.py" \
    --design "$design" --corner "$corner" --scenario "$scenario" \
    --out-log "$log" --work-secs 0.2 >/dev/null || true
  python3 "$ROOT/mock_tools/vortex_mock.py" \
    --policy "$ROOT/config/design_health.yaml" --log "$log" \
    --json-out "$report" --fail-on fatal >/dev/null || true
  if [[ "$NAIVE" == "1" ]]; then
    route_naive "$report" "$design" "$corner"
  else
    route_json "$report" "$design" "$corner"
  fi
}

run_one block_a ss_0p75 timing_fail
run_one block_a tt_0p85 clean
run_one block_a ff_0p95 clean
run_one block_b ss_0p70 drc_fail
