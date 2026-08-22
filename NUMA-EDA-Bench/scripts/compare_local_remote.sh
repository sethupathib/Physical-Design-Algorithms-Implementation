#!/usr/bin/env bash
# Compare local-ish vs unconstrained runs of numa_mem_bench.
# On 1-node machines both paths look similar — still validates the workflow.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${ROOT}/build/numa_mem_bench"
if [[ ! -x "$BIN" ]]; then
  echo "Build first: cmake -S . -B build && cmake --build build -j" >&2
  exit 1
fi

BYTES="${BYTES:-512M}"
THREADS="${THREADS:-$(nproc)}"

echo "=== unconstrained ==="
"$BIN" --bytes "$BYTES" --threads "$THREADS"

if command -v numactl >/dev/null 2>&1; then
  echo
  echo "=== numactl cpunodebind=0 membind=0 ==="
  numactl --cpunodebind=0 --membind=0 "$BIN" --bytes "$BYTES" --threads "$THREADS"
  NODES=$(ls -d /sys/devices/system/node/node[0-9]* 2>/dev/null | wc -l | tr -d ' ')
  if [[ "${NODES}" -ge 2 ]]; then
    echo
    echo "=== numactl cpunodebind=0 membind=1 (REMOTE — expect slower) ==="
    numactl --cpunodebind=0 --membind=1 "$BIN" --bytes "$BYTES" --threads "$THREADS" || true
  else
    echo
    echo "(only 1 NUMA node — skip remote contrast)"
  fi
else
  echo
  echo "numactl not installed — skip bound runs"
fi
