#!/usr/bin/env bash
# Hardware-only: remote membind vs local membind (median of TRIALS).
# Exits 2 on single-node hosts — does not invent remote DRAM numbers.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/examples/compare_results"
BIN="${ROOT}/build/numa_mem_bench"
NUMACTL="${ROOT}/tools/numactl-root/usr/bin/numactl"
[[ -x "$NUMACTL" ]] || NUMACTL="$(command -v numactl || true)"

BYTES="${BYTES:-512M}"
THREADS="${THREADS:-$(nproc)}"
TRIALS="${TRIALS:-5}"
mkdir -p "$OUT"
[[ -x "$BIN" ]] || make -C "$ROOT" -j"$(nproc)"
[[ -n "${NUMACTL}" && -x "$NUMACTL" ]] || { echo "ERROR: numactl missing" >&2; exit 1; }

NODES=$(find /sys/devices/system/node -maxdepth 1 -type d -name 'node[0-9]*' 2>/dev/null | wc -l | tr -d ' ')
if [[ "$NODES" -lt 2 ]]; then
  cat >&2 <<EOF
ERROR: need ≥2 NUMA nodes (host has ${NODES}).
Refusing to write a fake remote-vs-local SUMMARY.
Useful on this host: ./scripts/numa_report.sh | make smoke | make gif
EOF
  printf 'CITEABLE=no\nREASON=single_numa_node\n' >"$OUT/CLAIM_GATE.txt"
  exit 2
fi

COMMON=(--bytes "$BYTES" --threads "$THREADS")
run_median() {
  local label="$1"; shift
  local jsonl="$OUT/${label}.trials.jsonl" json="$OUT/${label}.json" log="$OUT/${label}.log"
  : >"$jsonl"
  echo "---- ${label} ----" | tee "$log"
  echo "cmd: $*" | tee -a "$log"
  local t
  for t in $(seq 1 "$TRIALS"); do
    echo "  trial $t/$TRIALS" | tee -a "$log"
    "$@" --json | tee -a "$jsonl" >/dev/null
  done
  python3 - "$jsonl" "$json" <<'PY' | tee -a "$log"
import json,sys
from pathlib import Path
rows=[json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
med={k: sorted(r[k] for r in rows)[len(rows)//2] for k in ("triad_gib_s","chase_ns")}
base=dict(rows[-1]); base.update(med); base["trials"]=len(rows); base["aggregate"]="median"
Path(sys.argv[2]).write_text(json.dumps(base)+"\n")
ts=sorted(r["triad_gib_s"] for r in rows); cs=sorted(r["chase_ns"] for r in rows)
print(f"  median triad={med['triad_gib_s']:.3f} GiB/s  chase={med['chase_ns']:.2f} ns")
print(f"  triad[{ts[0]:.3f},{ts[-1]:.3f}]  chase[{cs[0]:.2f},{cs[-1]:.2f}]")
PY
  echo
}

echo "host=$(hostname) nodes=$NODES trials=$TRIALS bytes=$BYTES threads=$THREADS"
"$NUMACTL" -H | sed 's/^/[numa] /'
run_median unbound "$BIN" "${COMMON[@]}"
run_median remote "$NUMACTL" --cpunodebind=0 --membind=1 "$BIN" "${COMMON[@]}"
run_median local  "$NUMACTL" --cpunodebind=0 --membind=0 "$BIN" "${COMMON[@]}"

export OUT BYTES THREADS TRIALS NODES
python3 - <<'PY' | tee "$OUT/SUMMARY.txt"
import json,os
from pathlib import Path
out=Path(os.environ["OUT"])
ub,remote,local=(json.loads((out/f).read_text()) for f in ("unbound.json","remote.json","local.json"))
def r(a,b): return b/a if a else float("nan")
print("="*72)
print("HARDWARE NUMA compare (microbench — not FC wall time)")
print(f"nodes={os.environ['NODES']} bytes={os.environ['BYTES']} threads={os.environ['THREADS']} trials={os.environ['TRIALS']} median")
print("="*72)
print(f"{'config':<36} {'triad_GiB/s':>12} {'chase_ns':>10}")
print("-"*72)
for n,j in [("unbound",ub),("REMOTE membind=1",remote),("LOCAL  membind=0",local)]:
    print(f"{n:<36} {j['triad_gib_s']:12.3f} {j['chase_ns']:10.2f}")
print("-"*72)
print(f"{'LOCAL/REMOTE triad':<36} {r(remote['triad_gib_s'], local['triad_gib_s']):12.3f}x")
print(f"{'REMOTE/LOCAL chase':<36} {r(local['chase_ns'], remote['chase_ns']):12.3f}x")
print("="*72)
print("Pair with FC stage wall time + numastat -p <pid> for farm claims.")
(out/"CLAIM_GATE.txt").write_text("CITEABLE=yes\nKIND=hardware_microbench\n")
PY
echo "SUMMARY=$OUT/SUMMARY.txt  CLAIM_GATE=CITEABLE=yes"
