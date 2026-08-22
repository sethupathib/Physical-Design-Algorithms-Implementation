#!/usr/bin/env bash
# Hardware-only NUMA local vs remote compare.
#
# Requires ≥2 NUMA nodes. On a 1-node host this script exits without
# inventing fake remote numbers.
#
#   BEFORE = numactl --cpunodebind=0 --membind=1  (remote DRAM)
#   AFTER  = numactl --cpunodebind=0 --membind=0  (local DRAM)
#
# Metrics (median of TRIALS):
#   triad_gib_s  STREAM bandwidth   higher better
#   chase_ns     pointer-chase      lower better
#
# Usage:
#   TRIALS=5 BYTES=1G THREADS=16 ./examples/compare_numa.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/examples/compare_results"
BIN="${ROOT}/build/numa_mem_bench"
NUMACTL="${ROOT}/tools/numactl-root/usr/bin/numactl"
[[ -x "$NUMACTL" ]] || NUMACTL="$(command -v numactl || true)"

BYTES="${BYTES:-512M}"
THREADS="${THREADS:-$(nproc)}"
STREAM_ITERS="${STREAM_ITERS:-5}"
CHASE_ITERS="${CHASE_ITERS:-8000000}"
TRIALS="${TRIALS:-5}"

mkdir -p "$OUT_DIR"

if [[ ! -x "$BIN" ]]; then
  make -C "$ROOT" -j"$(nproc)"
fi

if [[ -z "${NUMACTL}" || ! -x "$NUMACTL" ]]; then
  echo "ERROR: numactl not found (vendored tools/ or PATH)." >&2
  exit 1
fi

NODES=$(find /sys/devices/system/node -maxdepth 1 -type d -name 'node[0-9]*' 2>/dev/null | wc -l | tr -d ' ')
if [[ "${NODES}" -lt 2 ]]; then
  cat >&2 <<EOF
ERROR: need ≥2 NUMA nodes for a real remote-vs-local measurement.
  This host reports nodes=${NODES}.

What is still useful here:
  ./scripts/numa_report.sh
  ./scripts/run_eda_numactl.sh   # on a multi-socket farm box
  make && ./build/numa_mem_bench --bytes 256M   # microbench smoke only

Refusing to emit a SUMMARY that looks like a NUMA speedup.
EOF
  printf 'CITEABLE=no\nREASON=single_numa_node\n' >"${OUT_DIR}/CLAIM_GATE.txt"
  exit 2
fi

echo "================================================================"
echo " NUMA hardware compare: remote membind vs local membind"
echo "================================================================"
echo "host=$(hostname)  nodes=${NODES}  trials=${TRIALS} (median)"
echo "bytes=${BYTES}  threads=${THREADS}"
"$NUMACTL" -H | sed 's/^/[numa] /'
echo

COMMON=(--bytes "$BYTES" --threads "$THREADS"
        --stream-iters "$STREAM_ITERS" --chase-iters "$CHASE_ITERS")

run_median() {
  local label="$1"
  shift
  local jsonl="${OUT_DIR}/${label}.trials.jsonl"
  local json="${OUT_DIR}/${label}.json"
  local log="${OUT_DIR}/${label}.log"
  : >"$jsonl"
  echo "---- ${label} ----" | tee "$log"
  echo "cmd: $*" | tee -a "$log"
  local t
  for t in $(seq 1 "$TRIALS"); do
    echo "  trial ${t}/${TRIALS}" | tee -a "$log"
    "$@" --json | tee -a "$jsonl" >/dev/null
  done
  python3 - "$jsonl" "$json" <<'PY' | tee -a "$log"
import json, sys
from pathlib import Path
rows = [json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
keys = ["triad_gib_s", "chase_ns"]
med = {k: sorted(r[k] for r in rows)[len(rows)//2] for k in keys}
base = dict(rows[-1])
base.update(med)
base["trials"] = len(rows)
base["aggregate"] = "median"
Path(sys.argv[2]).write_text(json.dumps(base) + "\n")
ts = sorted(r["triad_gib_s"] for r in rows)
cs = sorted(r["chase_ns"] for r in rows)
print(f"  median triad={med['triad_gib_s']:.3f} GiB/s  chase={med['chase_ns']:.2f} ns")
print(f"  triad spread [{ts[0]:.3f}, {ts[-1]:.3f}]  chase spread [{cs[0]:.2f}, {cs[-1]:.2f}]")
PY
  echo
}

run_median unbound "$BIN" "${COMMON[@]}"
run_median remote "$NUMACTL" --cpunodebind=0 --membind=1 "$BIN" "${COMMON[@]}"
run_median local "$NUMACTL" --cpunodebind=0 --membind=0 "$BIN" "${COMMON[@]}"

export OUT_DIR BYTES THREADS TRIALS NODES
python3 - <<'PY' | tee "${OUT_DIR}/SUMMARY.txt"
import json, os
from pathlib import Path
out = Path(os.environ["OUT_DIR"])
ub = json.loads((out/"unbound.json").read_text())
remote = json.loads((out/"remote.json").read_text())
local = json.loads((out/"local.json").read_text())

def r(a, b):
    return b/a if a else float("nan")

print("=" * 72)
print("HARDWARE NUMA compare — citeable as microbench (not FC wall time)")
print(f"nodes={os.environ['NODES']}  bytes={os.environ['BYTES']}  "
      f"threads={os.environ['THREADS']}  trials={os.environ['TRIALS']} median")
print("=" * 72)
print("triad = STREAM bandwidth (GiB/s), higher better")
print("chase = pointer-chase latency (ns/hop), lower better")
print("-" * 72)
print(f"{'config':<40} {'triad':>10} {'chase_ns':>10}")
print("-" * 72)
for name, j in [("unbound", ub), ("REMOTE membind=1", remote), ("LOCAL  membind=0", local)]:
    print(f"{name:<40} {j['triad_gib_s']:10.3f} {j['chase_ns']:10.2f}")
print("-" * 72)
print(f"{'LOCAL/REMOTE triad':<40} {r(remote['triad_gib_s'], local['triad_gib_s']):10.3f}x")
print(f"{'REMOTE/LOCAL chase (local faster if >1)':<40} {r(local['chase_ns'], remote['chase_ns']):10.3f}x")
print("-" * 72)
print("This is a memory microbench under numactl policy — not Fusion Compiler.")
print("For a farm claim, also record stage wall time and: numastat -p <pid>")
print("=" * 72)
(out/"CLAIM_GATE.txt").write_text("CITEABLE=yes\nKIND=hardware_microbench\n")
PY

echo
echo "SUMMARY: ${OUT_DIR}/SUMMARY.txt"
echo "CLAIM_GATE: CITEABLE=yes (hardware microbench only)"
