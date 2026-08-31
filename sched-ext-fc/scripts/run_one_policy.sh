#!/usr/bin/env bash
# Run a single named policy end-to-end.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POLICY="${1:?flat|nice|sched_batch|layers|protect}"
DURATION="${DURATION:-20}"
CG_ROOT="${CG_ROOT:-/sys/fs/cgroup/sched_ext_fc}"
LABEL="${LABEL:-$POLICY}"
OUT_JSON="${OUT_JSON:-$ROOT/results/${LABEL}.json}"
OUT_TXT="${OUT_TXT:-$ROOT/results/${LABEL}.txt}"

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo --preserve-env=DURATION,LABEL,OUT_JSON,OUT_TXT,CG_ROOT,PATH,BATCH_WORKERS,BATCH_BURST_US,IX_PERIOD_US,IX_BURST_US,PIN_CPUS,IX_MODE \
    env DURATION="$DURATION" LABEL="$LABEL" OUT_JSON="$OUT_JSON" OUT_TXT="$OUT_TXT" CG_ROOT="$CG_ROOT" \
    PIN_CPUS="${PIN_CPUS:-}" IX_MODE="${IX_MODE:-burn}" \
    bash "$0" "$POLICY"
fi

# After sudo, results files may be root-owned — ensure dir exists.
mkdir -p "$ROOT/results"
"$ROOT/scripts/setup_cgroups.sh" destroy >/dev/null 2>&1 || true

export DURATION LABEL OUT_JSON OUT_TXT

case "$POLICY" in
  flat)
    "$ROOT/scripts/setup_cgroups.sh" create-flat
    export IX_CG="$CG_ROOT/all" BATCH_CG="$CG_ROOT/all"
    export NICE_IX=0 NICE_BATCH=0 BATCH_SCHED_BATCH=0
    ;;
  nice)
    "$ROOT/scripts/setup_cgroups.sh" create-flat
    export IX_CG="$CG_ROOT/all" BATCH_CG="$CG_ROOT/all"
    export NICE_IX=-5 NICE_BATCH=10 BATCH_SCHED_BATCH=0
    ;;
  sched_batch)
    "$ROOT/scripts/setup_cgroups.sh" create-flat
    export IX_CG="$CG_ROOT/all" BATCH_CG="$CG_ROOT/all"
    export NICE_IX=0 NICE_BATCH=0 BATCH_SCHED_BATCH=1
    ;;
  layers)
    "$ROOT/scripts/setup_cgroups.sh" create-layers
    export IX_CG="$CG_ROOT/interactive" BATCH_CG="$CG_ROOT/batch"
    export NICE_IX=0 NICE_BATCH=0 BATCH_SCHED_BATCH=0
    ;;
  protect)
    "$ROOT/scripts/setup_cgroups.sh" create-protect
    export IX_CG="$CG_ROOT/interactive" BATCH_CG="$CG_ROOT/batch"
    export NICE_IX=0 NICE_BATCH=0 BATCH_SCHED_BATCH=0
    ;;
  *)
    echo "unknown policy: $POLICY" >&2
    exit 1
    ;;
esac

"$ROOT/scripts/run_pair.sh"
"$ROOT/scripts/setup_cgroups.sh" destroy
# Make results readable by the invoking user
chmod -R a+rX "$ROOT/results" 2>/dev/null || true
