#!/usr/bin/env bash
# Quick topology + numactl sanity.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NUMACTL="${ROOT}/tools/numactl-root/usr/bin/numactl"
[[ -x "$NUMACTL" ]] || NUMACTL="$(command -v numactl || true)"

echo "=============================="
echo " NUMA / CPU report (EDA ops)"
echo "=============================="
echo "host: $(hostname)"
echo "date: $(date -Is)"
echo

if command -v lscpu >/dev/null 2>&1; then
  echo "---- lscpu (NUMA / sockets) ----"
  lscpu | grep -E 'CPU\(s\)|Socket|NUMA|Model name|Thread|Core' || lscpu | head -40
  echo
fi

if [[ -n "${NUMACTL}" && -x "$NUMACTL" ]]; then
  echo "---- numactl -H ----"
  "$NUMACTL" -H
  echo
else
  echo "numactl: NOT FOUND"
  echo
fi

if [[ -d /sys/devices/system/node ]]; then
  echo "---- sysfs nodes ----"
  for n in /sys/devices/system/node/node[0-9]*; do
    [[ -e "$n" ]] || continue
    node=$(basename "$n")
    cpus=$(cat "$n/cpulist" 2>/dev/null || echo "?")
    mem=$(awk '/MemTotal/ {printf "%.2f GiB", $4/1024/1024}' "$n/meminfo" 2>/dev/null || echo "?")
    echo "  $node  cpus=$cpus  MemTotal≈${mem}"
  done
  echo
fi

echo "---- free -h ----"
free -h 2>/dev/null || true
echo

NODES=$(find /sys/devices/system/node -maxdepth 1 -type d -name 'node[0-9]*' 2>/dev/null | wc -l | tr -d ' ')
echo "---- recommendation ----"
if [[ "${NODES:-0}" -le 1 ]]; then
  echo "Single NUMA node. Hardware local/remote contrast unavailable."
  echo "→ Run: ./examples/compare_numa.sh   (uses emulated remote tax)"
else
  echo "Multi-node system ($NODES nodes)."
  echo "→ Run: ./examples/compare_numa.sh   (hardware remote vs local)"
  echo "Production wrap:"
  echo "  ./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl"
fi
