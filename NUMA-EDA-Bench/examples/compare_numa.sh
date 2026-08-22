#!/usr/bin/env bash
# Before/after NUMA policy compare — same spirit as PD Job Acceleration's
# compare_accel.sh / compare_pd_farm_io.sh.
#
# HARDWARE (≥2 NUMA nodes + numactl):
#   BEFORE = remote (cpunodebind=0 membind=1)
#   AFTER  = local  (cpunodebind=0 membind=0)
#
# EMULATED (1-node hosts / this cloud VM) — like NFS_US farm model:
#   BEFORE = --emulate-remote  (remote DRAM tax)
#   AFTER  = native local (optionally under numactl membind=0)
#
# Usage:
#   ./examples/compare_numa.sh
#   BYTES=1G THREADS=4 ./examples/compare_numa.sh
#   FORCE_EMULATE=1 ./examples/compare_numa.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/examples/compare_results"
BIN="${ROOT}/build/numa_mem_bench"
NUMACTL="${ROOT}/tools/numactl-root/usr/bin/numactl"
if [[ ! -x "$NUMACTL" ]]; then
  NUMACTL="$(command -v numactl || true)"
fi

BYTES="${BYTES:-512M}"
THREADS="${THREADS:-$(nproc)}"
STREAM_ITERS="${STREAM_ITERS:-5}"
CHASE_ITERS="${CHASE_ITERS:-8000000}"
GRAPH_ITERS="${GRAPH_ITERS:-4000000}"
FORCE_EMULATE="${FORCE_EMULATE:-0}"
REMOTE_BW_MULT="${REMOTE_BW_MULT:-0.55}"
REMOTE_LAT_MULT="${REMOTE_LAT_MULT:-1.75}"

mkdir -p "$OUT_DIR"

if [[ ! -x "$BIN" ]]; then
  echo "Building numa_mem_bench..."
  make -C "$ROOT" -j"$(nproc)"
fi

NODES=1
if [[ -d /sys/devices/system/node ]]; then
  NODES=$(find /sys/devices/system/node -maxdepth 1 -type d -name 'node[0-9]*' | wc -l | tr -d ' ')
fi

MODE="emulated"
if [[ "$FORCE_EMULATE" != "1" && "$NODES" -ge 2 && -n "${NUMACTL}" && -x "$NUMACTL" ]]; then
  MODE="hardware"
fi

echo "================================================================"
echo " NUMA × FC-class memory — BEFORE vs AFTER"
echo "================================================================"
echo "host=$(hostname)  nodes=${NODES}  mode=${MODE}"
echo "bytes=${BYTES}  threads=${THREADS}"
echo "numactl=${NUMACTL:-none}"
echo

run_one() {
  local label="$1"
  shift
  local json="${OUT_DIR}/${label}.json"
  local log="${OUT_DIR}/${label}.log"
  echo "---- ${label} ----"
  echo "cmd: $*" | tee "$log"
  # Single timed pass → JSON (stable); pretty-print into the log too
  "$@" --json | tee "$json" | tee -a "$log" >/dev/null
  python3 -c "
import json
from pathlib import Path
j=json.loads(Path('${json}').read_text())
print(f\"  triad={j['triad_gib_s']:.3f} GiB/s  chase={j['chase_ns']:.2f} ns  graph={j['graph_ns']:.2f} ns  wall_proxy={j['wall_proxy']:.2f}\")
print(f\"  emulate_remote={j['emulate_remote']}  affinity={j['affinity']}  numa_nodes={j['numa_nodes']}\")
" | tee -a "$log"
  echo
}

COMMON=(--bytes "$BYTES" --threads "$THREADS"
        --stream-iters "$STREAM_ITERS"
        --chase-iters "$CHASE_ITERS"
        --graph-iters "$GRAPH_ITERS")

if [[ "$MODE" == "hardware" ]]; then
  run_one before_unbound "$BIN" "${COMMON[@]}"
  run_one before_remote "$NUMACTL" --cpunodebind=0 --membind=1 "$BIN" "${COMMON[@]}"
  run_one after_local "$NUMACTL" --cpunodebind=0 --membind=0 "$BIN" "${COMMON[@]}"
  BEFORE_KEY=before_remote
  AFTER_KEY=after_local
  BEFORE_LABEL="BEFORE remote (cpunodebind=0 membind=1)"
  AFTER_LABEL="AFTER  local  (cpunodebind=0 membind=0)"
else
  run_one before_emulated_remote "$BIN" "${COMMON[@]}" \
    --emulate-remote --remote-bw-mult "$REMOTE_BW_MULT" --remote-lat-mult "$REMOTE_LAT_MULT"
  if [[ -n "${NUMACTL}" && -x "$NUMACTL" ]]; then
    run_one after_local "$NUMACTL" --cpunodebind=0 --membind=0 "$BIN" "${COMMON[@]}"
  else
    run_one after_local "$BIN" "${COMMON[@]}"
  fi
  BEFORE_KEY=before_emulated_remote
  AFTER_KEY=after_local
  BEFORE_LABEL="BEFORE emulated remote (bw x ${REMOTE_BW_MULT}, lat x ${REMOTE_LAT_MULT})"
  AFTER_LABEL="AFTER  local / membind=0"
fi

export OUT_DIR BEFORE_KEY AFTER_KEY BEFORE_LABEL AFTER_LABEL MODE NODES BYTES THREADS
python3 - <<'PY' | tee "${OUT_DIR}/SUMMARY.txt"
import json, os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
before = json.loads((out / (os.environ["BEFORE_KEY"] + ".json")).read_text())
after = json.loads((out / (os.environ["AFTER_KEY"] + ".json")).read_text())
bl = os.environ["BEFORE_LABEL"]
al = os.environ["AFTER_LABEL"]

def ratio(a, b):
    return (b / a) if a else float("nan")

print("=" * 72)
print("NUMA policy — WITH vs WITHOUT (FC-class memory microbench)")
print(f"mode={os.environ['MODE']}  nodes={os.environ['NODES']}  bytes={os.environ['BYTES']}  threads={os.environ['THREADS']}")
print("=" * 72)
print(f"{'config':<52} {'triad':>8} {'chase':>8} {'graph':>8} {'wall':>8}")
print("-" * 72)
print(f"{bl:<52} {before['triad_gib_s']:8.3f} {before['chase_ns']:8.2f} {before['graph_ns']:8.2f} {before['wall_proxy']:8.2f}")
print(f"{al:<52} {after['triad_gib_s']:8.3f} {after['chase_ns']:8.2f} {after['graph_ns']:8.2f} {after['wall_proxy']:8.2f}")
print("-" * 72)
print(f"{'AFTER/BEFORE triad (higher better)':<52} {ratio(before['triad_gib_s'], after['triad_gib_s']):8.3f}x")
print(f"{'BEFORE/AFTER chase (higher = after faster)':<52} {ratio(after['chase_ns'], before['chase_ns']):8.3f}x")
print(f"{'BEFORE/AFTER graph (higher = after faster)':<52} {ratio(after['graph_ns'], before['graph_ns']):8.3f}x")
print(f"{'BEFORE/AFTER wall_proxy (higher = after better)':<52} {ratio(after['wall_proxy'], before['wall_proxy']):8.3f}x")
print("-" * 72)
if os.environ["MODE"] == "emulated":
    print("NOTE: This host has 1 NUMA node. BEFORE uses labeled remote-DRAM")
    print("emulation (same idea as NFS_US in PD Job Acceleration). On a real")
    print("2S/4S box, re-run to get HARDWARE local vs remote numbers.")
else:
    print("HARDWARE path: remote membind vs local membind on this machine.")
print("wall_proxy is a composite (lower = better turnaround proxy).")
print("Functional work is identical; only memory policy / tax differs.")
print("=" * 72)
ub = out / "before_unbound.json"
if ub.exists():
    u = json.loads(ub.read_text())
    print(f"unbound triad={u['triad_gib_s']:.3f}  chase={u['chase_ns']:.2f}  wall={u['wall_proxy']:.2f}")
PY

echo
echo "Summary: ${OUT_DIR}/SUMMARY.txt"
echo "JSONs:   ${OUT_DIR}/*.json"
