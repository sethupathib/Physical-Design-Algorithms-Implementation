#!/usr/bin/env bash
# Before/after NUMA policy compare.
#
# HARDWARE (≥2 NUMA nodes + numactl) — the ONLY path whose ratios are
# citeable as remote-vs-local DRAM measurements:
#   BEFORE = remote (cpunodebind=0 membind=1)
#   AFTER  = local  (cpunodebind=0 membind=0)
#
# EMULATED (1-node hosts) — harness smoke / plumbing check ONLY.
#   Applies an artificial remote tax. Numbers are NOT silicon.
#   SUMMARY is stamped DO_NOT_CITE.
#
# Usage:
#   ./examples/compare_numa.sh
#   TRIALS=5 BYTES=1G THREADS=8 ./examples/compare_numa.sh
#   FORCE_EMULATE=1 ./examples/compare_numa.sh   # smoke only
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
TRIALS="${TRIALS:-3}"

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
echo "host=$(hostname)  nodes=${NODES}  mode=${MODE}  trials=${TRIALS}"
echo "bytes=${BYTES}  threads=${THREADS}"
echo "numactl=${NUMACTL:-none}"
if [[ "$MODE" == "emulated" ]]; then
  echo
  echo "*** MODE=emulated — harness smoke ONLY. DO NOT CITE as speedup. ***"
  echo "*** Need ≥2 NUMA nodes for hardware remote vs local.            ***"
fi
echo

COMMON=(--bytes "$BYTES" --threads "$THREADS"
        --stream-iters "$STREAM_ITERS"
        --chase-iters "$CHASE_ITERS"
        --graph-iters "$GRAPH_ITERS")

# Run TRIALS times; write trials JSONL + median JSON.
run_median() {
  local label="$1"
  shift
  local jsonl="${OUT_DIR}/${label}.trials.jsonl"
  local json="${OUT_DIR}/${label}.json"
  local log="${OUT_DIR}/${label}.log"
  : >"$jsonl"
  echo "---- ${label} (${TRIALS} trials → median) ----" | tee "$log"
  echo "cmd: $*" | tee -a "$log"
  local t
  for t in $(seq 1 "$TRIALS"); do
    echo "  trial ${t}/${TRIALS}..." | tee -a "$log"
    "$@" --json | tee -a "$jsonl" >/dev/null
  done
  python3 - "$jsonl" "$json" <<'PY' | tee -a "$log"
import json, sys
from pathlib import Path
jsonl, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
keys = ["triad_gib_s", "chase_ns", "graph_ns", "wall_proxy"]
med = {k: sorted(r[k] for r in rows)[len(rows)//2] for k in keys}
# keep metadata from last row
base = dict(rows[-1])
base.update(med)
base["trials"] = len(rows)
base["aggregate"] = "median"
out.write_text(json.dumps(base) + "\n")
print(f"  median triad={med['triad_gib_s']:.3f} GiB/s  chase={med['chase_ns']:.2f} ns  "
      f"graph={med['graph_ns']:.2f} ns  wall_proxy={med['wall_proxy']:.2f}  (n={len(rows)})")
print(f"  emulate_remote={base.get('emulate_remote')}  affinity={base.get('affinity')}  "
      f"numa_nodes={base.get('numa_nodes')}")
# per-trial spread for triad (honesty about noise)
ts = sorted(r["triad_gib_s"] for r in rows)
print(f"  triad spread: min={ts[0]:.3f}  median={med['triad_gib_s']:.3f}  max={ts[-1]:.3f}")
PY
  echo
}

if [[ "$MODE" == "hardware" ]]; then
  run_median before_unbound "$BIN" "${COMMON[@]}"
  run_median before_remote "$NUMACTL" --cpunodebind=0 --membind=1 "$BIN" "${COMMON[@]}"
  run_median after_local "$NUMACTL" --cpunodebind=0 --membind=0 "$BIN" "${COMMON[@]}"
  BEFORE_KEY=before_remote
  AFTER_KEY=after_local
  BEFORE_LABEL="BEFORE remote (cpunodebind=0 membind=1)"
  AFTER_LABEL="AFTER  local  (cpunodebind=0 membind=0)"
  CITEABLE=1
else
  run_median before_emulated_remote "$BIN" "${COMMON[@]}" \
    --emulate-remote --remote-bw-mult "$REMOTE_BW_MULT" --remote-lat-mult "$REMOTE_LAT_MULT"
  if [[ -n "${NUMACTL}" && -x "$NUMACTL" ]]; then
    run_median after_local "$NUMACTL" --cpunodebind=0 --membind=0 "$BIN" "${COMMON[@]}"
  else
    run_median after_local "$BIN" "${COMMON[@]}"
  fi
  BEFORE_KEY=before_emulated_remote
  AFTER_KEY=after_local
  BEFORE_LABEL="BEFORE emulated remote (ARTIFICIAL tax — not silicon)"
  AFTER_LABEL="AFTER  local / membind=0"
  CITEABLE=0
fi

export OUT_DIR BEFORE_KEY AFTER_KEY BEFORE_LABEL AFTER_LABEL MODE NODES BYTES THREADS TRIALS CITEABLE
python3 - <<'PY' | tee "${OUT_DIR}/SUMMARY.txt"
import json, os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
before = json.loads((out / (os.environ["BEFORE_KEY"] + ".json")).read_text())
after = json.loads((out / (os.environ["AFTER_KEY"] + ".json")).read_text())
bl = os.environ["BEFORE_LABEL"]
al = os.environ["AFTER_LABEL"]
citeable = os.environ["CITEABLE"] == "1"
mode = os.environ["MODE"]

def ratio(a, b):
    return (b / a) if a else float("nan")

print("=" * 72)
print("NUMA policy — BEFORE vs AFTER (FC-class memory microbench)")
print(f"mode={mode}  nodes={os.environ['NODES']}  bytes={os.environ['BYTES']}  "
      f"threads={os.environ['THREADS']}  trials={os.environ['TRIALS']} (median)")
print("=" * 72)
if not citeable:
    print("!!! DO_NOT_CITE — emulated / single-node run. Not a speedup claim. !!!")
    print("!!! Publish only hardware mode on a ≥2-node host.                !!!")
    print("-" * 72)
else:
    print("CITEABLE=yes — hardware remote vs local on this host.")
    print("-" * 72)

print("Metric guide:")
print("  triad GiB/s  — STREAM bandwidth          (higher better)")
print("  chase ns     — pointer-chase latency     (lower better)")
print("  graph ns     — graph-walk latency        (lower better)")
print("  wall_proxy   — synthetic composite ONLY  (lower better; NOT FC wall time)")
print("-" * 72)
print(f"{'config':<56} {'triad':>8} {'chase':>8} {'graph':>8} {'wall':>8}")
print("-" * 72)
print(f"{bl:<56} {before['triad_gib_s']:8.3f} {before['chase_ns']:8.2f} {before['graph_ns']:8.2f} {before['wall_proxy']:8.2f}")
print(f"{al:<56} {after['triad_gib_s']:8.3f} {after['chase_ns']:8.2f} {after['graph_ns']:8.2f} {after['wall_proxy']:8.2f}")
print("-" * 72)

# Always show ratios, but gate language hard on citeability
tr = ratio(before["triad_gib_s"], after["triad_gib_s"])
cr = ratio(after["chase_ns"], before["chase_ns"])  # before/after = how many x faster after
gr = ratio(after["graph_ns"], before["graph_ns"])
wr = ratio(after["wall_proxy"], before["wall_proxy"])
print(f"{'AFTER/BEFORE triad':<56} {tr:8.3f}x   (want >1 if bandwidth improved)")
print(f"{'BEFORE/AFTER chase':<56} {cr:8.3f}x   (want >1 if after is faster)")
print(f"{'BEFORE/AFTER graph':<56} {gr:8.3f}x   (want >1 if after is faster)")
print(f"{'BEFORE/AFTER wall_proxy':<56} {wr:8.3f}x   (synthetic; do not treat as FC)")
print("-" * 72)

if not citeable:
    print("Honesty notes (emulated mode):")
    print("  • BEFORE adds an artificial bw/lat tax in userspace — not UPI.")
    print("  • Triad is noisy on shared VMs; trust median + triad spread above.")
    print("  • If triad AFTER < BEFORE here, that is noise — not anti-NUMA proof.")
    print("  • Do not put these ratios in LinkedIn / slides / customer email.")
else:
    print("Honesty notes (hardware mode):")
    print("  • This is microbench, not Fusion Compiler wall time.")
    print("  • Cite alongside numastat / stage wall time when claiming farm wins.")
    print("  • Hard membind only when peak RSS fits the node’s free RAM.")

print("=" * 72)
# machine-readable claim gate for scripts
(out / "CLAIM_GATE.txt").write_text(
    "CITEABLE=yes\n" if citeable else "CITEABLE=no\nDO_NOT_CITE=emulated_or_single_node\n"
)
print(f"claim gate: {out / 'CLAIM_GATE.txt'} -> {'CITEABLE' if citeable else 'DO_NOT_CITE'}")
PY

echo
echo "Summary: ${OUT_DIR}/SUMMARY.txt"
if [[ "$CITEABLE" == "0" ]]; then
  echo "Claim gate: DO_NOT_CITE (emulated). Get a 2S box before posting numbers."
else
  echo "Claim gate: CITEABLE (hardware remote vs local)."
fi
