#!/usr/bin/env bash
# Launch interactive-class + batch as separate processes under cgroups / nice / SCHED_BATCH.
#
# Default interactive-class mode is `burn` (always-runnable): that is where cgroup
# cpu.weight differences show up as CPU share. Paced `interactive` latency mode is
# available via IX_MODE=interactive but CFS already protects short wakeups well.
#
# Env: DURATION LABEL OUT_JSON OUT_TXT IX_CG BATCH_CG NICE_IX NICE_BATCH
#      BATCH_SCHED_BATCH BATCH_WORKERS BATCH_BURST_US IX_MODE IX_BURST_US IX_PERIOD_US PIN_CPUS
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/fc_sched_bench"

DURATION="${DURATION:?}"
LABEL="${LABEL:?}"
OUT_JSON="${OUT_JSON:?}"
OUT_TXT="${OUT_TXT:?}"
IX_CG="${IX_CG:-}"
BATCH_CG="${BATCH_CG:-}"
NICE_IX="${NICE_IX:-0}"
NICE_BATCH="${NICE_BATCH:-0}"
BATCH_SCHED_BATCH="${BATCH_SCHED_BATCH:-0}"
BATCH_WORKERS="${BATCH_WORKERS:-6}"
BATCH_BURST_US="${BATCH_BURST_US:-2000}"
IX_MODE="${IX_MODE:-burn}"
IX_BURST_US="${IX_BURST_US:-2000}"
IX_PERIOD_US="${IX_PERIOD_US:-5000}"
PIN_CPUS="${PIN_CPUS:-}"

if [[ ! -x "$BIN" ]]; then
  echo "missing $BIN — run make" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$(dirname "$OUT_JSON")"

STARTED_PID=""
start_role() {
  local role="$1" cg="$2" nice_val="$3" json="$4"
  local log="$TMP/${role}.log"
  local -a prefix=()
  if [[ -n "$PIN_CPUS" ]]; then
    prefix+=(taskset -c "$PIN_CPUS")
  fi
  if [[ "$nice_val" != "0" ]]; then
    prefix+=(nice -n "$nice_val")
  fi
  if [[ "$role" == "batch" && "$BATCH_SCHED_BATCH" == "1" ]]; then
    prefix+=(chrt --batch 0)
  fi

  local -a cmd=("$BIN")
  if [[ "$role" == "batch" ]]; then
    cmd+=(--mode batch --duration-s "$DURATION" --label "$LABEL" --json "$json"
          --workers "$BATCH_WORKERS" --burst-us "$BATCH_BURST_US")
  else
    if [[ "$IX_MODE" == "burn" ]]; then
      cmd+=(--mode burn --duration-s "$DURATION" --label "$LABEL" --json "$json"
            --burst-us "$IX_BURST_US")
    else
      cmd+=(--mode interactive --duration-s "$DURATION" --label "$LABEL" --json "$json"
            --period-us "$IX_PERIOD_US" --burst-us "$IX_BURST_US")
    fi
  fi

  if [[ ${#prefix[@]} -gt 0 ]]; then
    "${prefix[@]}" "${cmd[@]}" >"$log" 2>&1 &
  else
    "${cmd[@]}" >"$log" 2>&1 &
  fi
  STARTED_PID=$!

  if [[ -n "$cg" && "$(id -u)" -eq 0 ]]; then
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
      if echo "$STARTED_PID" > "$cg/cgroup.procs" 2>/dev/null; then
        break
      fi
      sleep 0.05
    done
  fi
}

IX_JSON="$TMP/ix.json"
BATCH_JSON="$TMP/batch.json"

start_role ix "$IX_CG" "$NICE_IX" "$IX_JSON"
IX_PID="$STARTED_PID"
start_role batch "$BATCH_CG" "$NICE_BATCH" "$BATCH_JSON"
BATCH_PID="$STARTED_PID"

{
  echo "# started ix_pid=$IX_PID batch_pid=$BATCH_PID label=$LABEL"
  echo "# IX_CG=$IX_CG BATCH_CG=$BATCH_CG NICE_IX=$NICE_IX NICE_BATCH=$NICE_BATCH BATCH_SCHED_BATCH=$BATCH_SCHED_BATCH"
  echo "# BATCH_WORKERS=$BATCH_WORKERS IX_MODE=$IX_MODE IX_BURST_US=$IX_BURST_US PIN_CPUS=${PIN_CPUS:-all}"
} | tee "$OUT_TXT"

set +e
wait "$IX_PID"; IX_RC=$?
wait "$BATCH_PID"; BATCH_RC=$?
set -e

{
  echo "----- ix log -----"
  cat "$TMP/ix.log" || true
  echo "----- batch log -----"
  cat "$TMP/batch.log" || true
} | tee -a "$OUT_TXT"

if [[ "$IX_RC" -ne 0 || "$BATCH_RC" -ne 0 ]]; then
  echo "worker failed: ix_rc=$IX_RC batch_rc=$BATCH_RC" >&2
  exit 1
fi

python3 - "$IX_JSON" "$BATCH_JSON" "$LABEL" "$OUT_JSON" <<'PY' | tee -a "$OUT_TXT"
import json, sys
ix_path, batch_path, label, out_path = sys.argv[1:5]
with open(ix_path) as f:
    ix = json.load(f)
with open(batch_path) as f:
    batch = json.load(f)

merged = {
    "label": label,
    "ix": ix,
    "batch": batch,
    "ix_role": ix.get("role"),
    "batch_iters_per_s": batch["iters_per_s"],
}
if ix.get("role") == "burn":
    merged["ix_cpu_eq"] = ix["cpu_eq"]
    merged["ix_iters_per_s"] = ix["iters_per_s"]
else:
    merged["ix_p50_us"] = ix["p50_us"]
    merged["ix_p99_us"] = ix["p99_us"]
    merged["ix_p999_us"] = ix.get("p999_us", ix["p99_us"])
    merged["ix_max_us"] = ix["max_us"]
    merged["ix_outlier_ppm"] = ix.get("outlier_ppm", 0.0)

with open(out_path, "w") as f:
    json.dump(merged, f, indent=2)
    f.write("\n")

if ix.get("role") == "burn":
    print(
        f"label={label} ix_cpu_eq={ix['cpu_eq']:.3f} ix_iters_per_s={ix['iters_per_s']:.2f} "
        f"batch_iters_per_s={batch['iters_per_s']:.2f}"
    )
else:
    print(
        f"label={label} ix_p50_us={ix['p50_us']:.1f} ix_p99_us={ix['p99_us']:.1f} "
        f"ix_max_us={ix['max_us']:.1f} outlier_ppm={ix.get('outlier_ppm', 0):.1f} "
        f"batch_iters_per_s={batch['iters_per_s']:.2f}"
    )
PY
