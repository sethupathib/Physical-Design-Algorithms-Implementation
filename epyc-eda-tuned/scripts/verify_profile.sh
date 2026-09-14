#!/usr/bin/env bash
# verify_profile.sh — check active settings against epyc-eda expectations.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/results/verify_profile.txt}"
mkdir -p "$(dirname "$OUT")"

EXPECT_MIG=10000
PASS=1
REASONS=()

read_mig() {
  if [[ -r /proc/sys/kernel/sched_migration_cost_ns ]]; then
    cat /proc/sys/kernel/sched_migration_cost_ns
  elif [[ -r /sys/kernel/debug/sched/migration_cost_ns ]]; then
    cat /sys/kernel/debug/sched/migration_cost_ns
  else
    echo ""
  fi
}

MIG=$(read_mig)
{
  echo "# verify against epyc-eda expectations"
  echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "expect_sched_migration_cost_ns=$EXPECT_MIG"
  echo "actual_sched_migration_cost_ns=${MIG:-UNAVAILABLE}"

  if [[ -z "$MIG" ]]; then
    PASS=0
    REASONS+=("migration_cost_unreadable")
  elif [[ "$MIG" -eq "$EXPECT_MIG" ]]; then
    echo "migration_cost_match=yes"
  else
    PASS=0
    REASONS+=("migration_cost_mismatch_${MIG}_ne_${EXPECT_MIG}")
    echo "migration_cost_match=no"
  fi

  if command -v tuned-adm >/dev/null 2>&1; then
    ACTIVE=$(tuned-adm active 2>/dev/null | awk -F: '/Current active profile/{gsub(/^[ \t]+/,"",$2); print $2}')
    echo "tuned_active=${ACTIVE:-unknown}"
    if [[ "${ACTIVE:-}" == *epyc-eda* ]]; then
      echo "tuned_profile_match=yes"
    else
      # Not fatal if manual-sysctl path used
      echo "tuned_profile_match=no"
      REASONS+=("tuned_not_epyc_eda_optional")
    fi
    tuned-adm verify 2>&1 | sed 's/^/tuned_verify=/' || true
  else
    echo "tuned_active=absent"
    echo "tuned_profile_match=n/a"
  fi

  if [[ $PASS -eq 1 ]]; then
    echo "verify_result=PASS"
  else
    echo "verify_result=FAIL"
  fi
  echo "verify_reasons=$(IFS=,; echo "${REASONS[*]}")"
} | tee "$OUT"

if [[ $PASS -ne 1 ]]; then
  exit 1
fi
