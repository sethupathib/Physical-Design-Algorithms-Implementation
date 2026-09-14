#!/usr/bin/env bash
# claim_gate.sh — strict gate for publishable claims about epyc-eda.
#
# Exit codes:
#   0 PASS
#   1 FAIL
#   3 SKIP (host incapable — not a silent pass)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$ROOT/results/claim_gate_${STAMP}"
mkdir -p "$OUT"

"$ROOT/scripts/detect_env.sh" "$OUT/host_inventory.txt" >/dev/null
# shellcheck disable=SC1090
source <(grep -E '^(claim_gate_eligible|can_set_migration_cost|is_amd|has_tuned)=' "$OUT/host_inventory.txt" | sed 's/^/export /')

{
  echo "# CLAIM_GATE"
  echo "stamp=$STAMP"
  echo "claim=epyc_eda_lower_migration_cost_reduces_spread_makespan"
  echo "method=fanout_bench_spread_mode_A_B_5ms_vs_10us"
  echo "is_amd=${is_amd:-0}"
  echo "has_tuned=${has_tuned:-0}"
  echo "can_set_migration_cost=${can_set_migration_cost:-0}"
  echo "claim_gate_eligible=${claim_gate_eligible:-no}"
} | tee "$OUT/header.txt"

if [[ "${claim_gate_eligible:-no}" != "yes" ]]; then
  {
    echo "gate_result=SKIP"
    echo "gate_reason=host_cannot_write_sched_migration_cost_ns"
    echo "publishable_claim=NO"
    echo "allowed_public_statement=Host inventory only; no performance claim."
  } | tee "$OUT/gate.txt"
  echo "outdir=$OUT"
  exit 3
fi

# Run A/B
"$ROOT/scripts/compare_profiles.sh" | tee "$OUT/compare_log.txt"
# Find newest compare dir
COMPARE_DIR=$(ls -td "$ROOT/results"/compare_* | head -1)
cp -a "$COMPARE_DIR"/. "$OUT/compare/" 2>/dev/null || mkdir -p "$OUT/compare"
# Prefer summary from compare
if [[ -f "$COMPARE_DIR/summary.txt" ]]; then
  cp "$COMPARE_DIR/summary.txt" "$OUT/compare_summary.txt"
fi

RESULT=$(awk -F= '/compare_result/{print $2}' "$OUT/compare_summary.txt" 2>/dev/null || echo MISSING)

{
  echo "compare_result=$RESULT"
  if [[ "$RESULT" == "PASS" ]]; then
    echo "gate_result=PASS"
    echo "publishable_claim=YES"
    echo "allowed_public_statement=Under fanout_bench spread mode on this host, sched_migration_cost_ns=10000 reduced makespan by >=3% vs 5000000."
  elif [[ "$RESULT" == "INCONCLUSIVE" ]]; then
    echo "gate_result=FAIL"
    echo "publishable_claim=NO"
    echo "allowed_public_statement=Inconclusive A/B; do not claim speedup."
  elif [[ "$RESULT" == "SKIP" ]]; then
    echo "gate_result=SKIP"
    echo "publishable_claim=NO"
  else
    echo "gate_result=FAIL"
    echo "publishable_claim=NO"
    echo "allowed_public_statement=A/B did not support the claim on this host."
  fi
} | tee "$OUT/gate.txt"

echo "outdir=$OUT"
grep -q 'gate_result=PASS' "$OUT/gate.txt"
