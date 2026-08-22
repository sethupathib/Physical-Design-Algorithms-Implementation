#!/usr/bin/env bash
# Topology + recommendation for NUMA-aware EDA runs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NUMACTL="${ROOT}/tools/numactl-root/usr/bin/numactl"
[[ -x "$NUMACTL" ]] || NUMACTL="$(command -v numactl || true)"

echo "=============================="
echo " NUMA report"
echo "=============================="
echo "host: $(hostname)"
echo "date: $(date -Is)"
echo

if command -v lscpu >/dev/null 2>&1; then
  echo "---- lscpu ----"
  lscpu | grep -E 'CPU\(s\)|Socket|NUMA|Model name|Thread|Core' || true
  echo
fi

if [[ -n "${NUMACTL}" && -x "$NUMACTL" ]]; then
  echo "---- numactl -H ----"
  "$NUMACTL" -H
  echo
else
  echo "numactl: not found"
  echo
fi

NODES=0
if [[ -d /sys/devices/system/node ]]; then
  echo "---- per-node memory ----"
  for n in /sys/devices/system/node/node[0-9]*; do
    [[ -e "$n" ]] || continue
    NODES=$((NODES + 1))
    node=$(basename "$n")
    cpus=$(cat "$n/cpulist" 2>/dev/null || echo "?")
    tot=$(awk '/MemTotal:/ {printf "%.2f", $4/1024/1024}' "$n/meminfo")
    free=$(awk '/MemFree:/ {printf "%.2f", $4/1024/1024}' "$n/meminfo")
    echo "  ${node}  cpus=${cpus}  MemTotal≈${tot} GiB  MemFree≈${free} GiB"
  done
  echo
fi

echo "---- free -h ----"
free -h 2>/dev/null || true
echo

echo "---- recommendation ----"
if [[ "$NODES" -lt 2 ]]; then
  echo "Single NUMA node (${NODES})."
  echo "  → numactl membind will NOT create a local/remote contrast here."
  echo "  → Use this toolkit on a 2S/4S farm node to measure and to wrap FC."
else
  echo "Multi-node system (${NODES} nodes)."
  echo "  If one FC/Innovus job fits in node0 free RAM:"
  echo "    ./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl"
  echo "  Measure microbench (citeable as microbench only):"
  echo "    ./examples/compare_numa.sh"
  echo "  Live check during a run:"
  echo "    numastat -p \$(pgrep -n fc_shell)"
fi
