#!/usr/bin/env bash
# Report NUMA / CPU topology and suggest an EDA numactl policy.
set -euo pipefail

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

if command -v numactl >/dev/null 2>&1; then
  echo "---- numactl -H ----"
  numactl -H
  echo
else
  echo "numactl: NOT INSTALLED (install package 'numactl')"
  echo
fi

if [[ -d /sys/devices/system/node ]]; then
  echo "---- sysfs nodes ----"
  for n in /sys/devices/system/node/node[0-9]*; do
    [[ -e "$n" ]] || continue
    node=$(basename "$n")
    cpus=$(cat "$n/cpulist" 2>/dev/null || echo "?")
    mem=$(cat "$n/meminfo" 2>/dev/null | awk '/MemTotal/ {print $4/1024/1024 " GiB"}')
    echo "  $node  cpus=$cpus  MemTotal≈${mem:-?}"
  done
  echo
fi

echo "---- free -h ----"
free -h 2>/dev/null || true
echo

NODES=$(ls -d /sys/devices/system/node/node[0-9]* 2>/dev/null | wc -l | tr -d ' ')
echo "---- recommendation ----"
if [[ "${NODES:-0}" -le 1 ]]; then
  echo "Single NUMA node detected (or topology unavailable)."
  echo "→ numactl pin will NOT help here. Focus on TMPDIR/local disk and mpstat."
else
  echo "Multi-node system ($NODES nodes)."
  echo "If ONE Fusion Compiler / Innovus job fits in node0 RAM:"
  echo "  numactl --cpunodebind=0 --membind=0 <eda_command>"
  echo "If the working set exceeds one node's free RAM:"
  echo "  use --preferred=0 (spill allowed) OR size the machine / split jobs."
  echo "Verify live:"
  echo "  numastat -p \$(pgrep -n fc_shell)"
fi
