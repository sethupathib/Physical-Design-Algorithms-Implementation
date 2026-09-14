#!/usr/bin/env bash
# compare_profiles.sh — A/B fanout_bench under two migration-cost settings.
#
# Primary comparison (does not require full TuneD):
#   HIGH = 5000000  (throughput-performance AMD default)
#   LOW  = 10000    (epyc-eda)
#
# Usage:
#   sudo ./scripts/compare_profiles.sh
#   ./scripts/compare_profiles.sh --dry-run   # bench only, no knob writes
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/src/fanout_bench"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUTDIR="$ROOT/results/compare_${STAMP}"
DRY=0
HIGH=5000000
LOW=10000

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --help|-h)
      echo "Usage: $0 [--dry-run]"
      exit 0
      ;;
  esac
done

mkdir -p "$OUTDIR"
make -C "$ROOT" bin >/dev/null

resolve_mig_path() {
  if [[ -e /proc/sys/kernel/sched_migration_cost_ns ]]; then
    echo /proc/sys/kernel/sched_migration_cost_ns
  elif [[ -e /sys/kernel/debug/sched/migration_cost_ns ]]; then
    echo /sys/kernel/debug/sched/migration_cost_ns
  else
    echo ""
  fi
}

PATH_MIG="$(resolve_mig_path)"
"$ROOT/scripts/detect_env.sh" "$OUTDIR/host_inventory.txt" >/dev/null
"$ROOT/scripts/dump_sched_knobs.sh" "$OUTDIR/knobs_before.txt" >/dev/null

run_bench() {
  local label="$1"
  local out="$OUTDIR/bench_${label}.txt"
  "$BIN" --mode spread --outer 7 --work-units 2500 --burn-iters 10000 | tee "$out"
}

set_mig() {
  local val="$1"
  if [[ -z "$PATH_MIG" ]]; then
    echo "ERROR: no migration_cost path" >&2
    return 2
  fi
  if [[ ! -w "$PATH_MIG" ]]; then
    echo "ERROR: $PATH_MIG not writable; re-run as root" >&2
    return 2
  fi
  echo "$val" > "$PATH_MIG"
  echo "set $PATH_MIG=$val (readback=$(cat "$PATH_MIG"))"
}

parse_median() {
  awk -F= '/makespan_median_s/{print $2}' "$1"
}

{
  echo "# compare_profiles"
  echo "stamp=$STAMP"
  echo "dry_run=$DRY"
  echo "high_ns=$HIGH"
  echo "low_ns=$LOW"
  echo "mig_path=${PATH_MIG:-none}"
} | tee "$OUTDIR/meta.txt"

if [[ "$DRY" -eq 1 ]]; then
  echo "NOTE: dry-run — running bench once at current knobs only" | tee -a "$OUTDIR/meta.txt"
  run_bench current | tee "$OUTDIR/bench_current.txt"
  echo "result=DRY_RUN" | tee "$OUTDIR/summary.txt"
  echo "outdir=$OUTDIR"
  exit 0
fi

if [[ -z "$PATH_MIG" || ! -w "$PATH_MIG" ]]; then
  echo "result=SKIP" | tee "$OUTDIR/summary.txt"
  echo "skip_reason=migration_cost_not_writable" | tee -a "$OUTDIR/summary.txt"
  echo "HINT: sudo $0   OR   --dry-run for bench-only" | tee -a "$OUTDIR/summary.txt"
  # Still run one bench for baseline artifact
  run_bench current || true
  echo "outdir=$OUTDIR"
  exit 0
fi

ORIG=$(cat "$PATH_MIG")
echo "original_migration_cost_ns=$ORIG" | tee -a "$OUTDIR/meta.txt"
cleanup() {
  echo "$ORIG" > "$PATH_MIG" 2>/dev/null || true
}
trap cleanup EXIT

set_mig "$HIGH"
"$ROOT/scripts/dump_sched_knobs.sh" "$OUTDIR/knobs_high.txt" >/dev/null
run_bench high

set_mig "$LOW"
"$ROOT/scripts/dump_sched_knobs.sh" "$OUTDIR/knobs_low.txt" >/dev/null
run_bench low

MED_HIGH=$(parse_median "$OUTDIR/bench_high.txt")
MED_LOW=$(parse_median "$OUTDIR/bench_low.txt")

python3 - "$MED_HIGH" "$MED_LOW" "$OUTDIR/summary.txt" <<'PY'
import sys
hi, lo, path = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
ratio = lo / hi if hi > 0 else float("nan")
# Claim: low migration cost should not be slower; prefer ratio < 1.0
# Gate thresholds documented in CLAIM_GATE.md
lines = [
    f"makespan_high_s={hi:.6f}",
    f"makespan_low_s={lo:.6f}",
    f"ratio_low_over_high={ratio:.4f}",
    f"speedup_high_over_low={(hi/lo) if lo>0 else float('nan'):.4f}",
]
# PASS if low is at least 3% faster (ratio <= 0.97)
if ratio <= 0.97:
    lines.append("compare_result=PASS")
    lines.append("compare_note=low_migration_cost_faster_by_ge_3pct")
elif ratio <= 1.02:
    lines.append("compare_result=INCONCLUSIVE")
    lines.append("compare_note=within_noise_band_pm_2pct")
else:
    lines.append("compare_result=FAIL")
    lines.append("compare_note=low_migration_cost_not_faster")
open(path, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
PY

echo "outdir=$OUTDIR"
