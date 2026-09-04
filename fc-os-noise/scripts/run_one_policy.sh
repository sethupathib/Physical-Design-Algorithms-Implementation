#!/usr/bin/env bash
# Soft-isolation demo policies (no reboot required).
#
# On a 4-CPU host default layout:
#   JOB_CPUS=2-3   NOISE_CPUS=0-1
# Under contention, pinning the FC-proxy away from noise should cut round p99.
#
# Env: LABEL OUT_JSON OUT_TXT JOB_CPUS NOISE_CPUS THREADS ROUNDS BURST_US
#      NOISE_PROCS NOISE_BURST_US NOISE_SLEEP_US
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/fc_noise_bench"
POLICY="${1:?flat_quiet|flat_contend|pin_split|pin_only}"

LABEL="${LABEL:-$POLICY}"
OUT_JSON="${OUT_JSON:-$ROOT/results/${LABEL}.json}"
OUT_TXT="${OUT_TXT:-$ROOT/results/${LABEL}.txt}"
NPROC="$(nproc)"
# Defaults for 4 CPUs; override freely.
if [[ "$NPROC" -ge 4 ]]; then
  JOB_CPUS="${JOB_CPUS:-2-3}"
  NOISE_CPUS="${NOISE_CPUS:-0-1}"
  THREADS="${THREADS:-2}"
else
  JOB_CPUS="${JOB_CPUS:-0}"
  NOISE_CPUS="${NOISE_CPUS:-0}"
  THREADS="${THREADS:-1}"
fi
ROUNDS="${ROUNDS:-300}"
BURST_US="${BURST_US:-1500}"
NOISE_PROCS="${NOISE_PROCS:-4}"
NOISE_BURST_US="${NOISE_BURST_US:-2000}"
NOISE_SLEEP_US="${NOISE_SLEEP_US:-0}"

if [[ ! -x "$BIN" ]]; then
  echo "missing $BIN — run make" >&2
  exit 1
fi
mkdir -p "$(dirname "$OUT_JSON")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; [[ -n "${NOISE_PIDS:-}" ]] && kill ${NOISE_PIDS:-} 2>/dev/null || true' EXIT

start_noise() {
  local cpus="$1"
  NOISE_PIDS=""
  local i
  for i in $(seq 1 "$NOISE_PROCS"); do
    # duration long enough to cover the worker run
    local dur=$((ROUNDS * BURST_US / 1000000 + 30))
    if [[ "$dur" -lt 20 ]]; then dur=20; fi
    if [[ -n "$cpus" ]]; then
      taskset -c "$cpus" "$BIN" --mode noise --duration-s "$dur" \
        --burst-us "$NOISE_BURST_US" --sleep-us "$NOISE_SLEEP_US" \
        --label "noise_$i" >"$TMP/noise_$i.log" 2>&1 &
    else
      "$BIN" --mode noise --duration-s "$dur" \
        --burst-us "$NOISE_BURST_US" --sleep-us "$NOISE_SLEEP_US" \
        --label "noise_$i" >"$TMP/noise_$i.log" 2>&1 &
    fi
    NOISE_PIDS="$NOISE_PIDS $!"
  done
  sleep 0.3
}

stop_noise() {
  if [[ -n "${NOISE_PIDS:-}" ]]; then
    kill $NOISE_PIDS 2>/dev/null || true
    wait $NOISE_PIDS 2>/dev/null || true
    NOISE_PIDS=""
  fi
}

run_workers() {
  local cpus="$1"
  if [[ -n "$cpus" ]]; then
    taskset -c "$cpus" "$BIN" --mode workers --threads "$THREADS" --rounds "$ROUNDS" \
      --burst-us "$BURST_US" --label "$LABEL" --json "$OUT_JSON"
  else
    "$BIN" --mode workers --threads "$THREADS" --rounds "$ROUNDS" \
      --burst-us "$BURST_US" --label "$LABEL" --json "$OUT_JSON"
  fi
}

{
  echo "# policy=$POLICY label=$LABEL nproc=$NPROC"
  echo "# JOB_CPUS=$JOB_CPUS NOISE_CPUS=$NOISE_CPUS THREADS=$THREADS ROUNDS=$ROUNDS BURST_US=$BURST_US"
} | tee "$OUT_TXT"

case "$POLICY" in
  flat_quiet)
    # Workers on all CPUs, no noise — quiet baseline.
    run_workers "" | tee -a "$OUT_TXT"
    ;;
  flat_contend)
    # Workers + noise share all CPUs — farm default under load.
    start_noise ""
    run_workers "" | tee -a "$OUT_TXT"
    stop_noise
    ;;
  pin_split)
    # Soft isolation: job on JOB_CPUS, noise on NOISE_CPUS.
    start_noise "$NOISE_CPUS"
    run_workers "$JOB_CPUS" | tee -a "$OUT_TXT"
    stop_noise
    ;;
  pin_only)
    # Pinned job, no noise — shows pin overhead alone.
    run_workers "$JOB_CPUS" | tee -a "$OUT_TXT"
    ;;
  *)
    echo "unknown policy $POLICY" >&2
    exit 1
    ;;
esac

python3 - "$OUT_JSON" "$POLICY" <<'PY' | tee -a "$OUT_TXT"
import json, sys
path, policy = sys.argv[1], sys.argv[2]
d = json.loads(open(path).read())
d["policy"] = policy
open(path, "w").write(json.dumps(d, indent=2) + "\n")
print(
    f"SUMMARY policy={policy} wall_s={d['wall_s']:.3f} "
    f"p50_us={d['round_p50_us']:.1f} p99_us={d['round_p99_us']:.1f} "
    f"max_us={d['round_max_us']:.1f}"
)
PY
