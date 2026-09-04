#!/usr/bin/env bash
# Farm wrapper: run an FC-class command on isolated / pinned CPUs.
#
# Usage:
#   ./scripts/run_fc_isolated.sh 8-15 fc_shell -f run.tcl
#   JOB_CPUS=8-15 ./scripts/run_fc_isolated.sh -- fc_shell -f run.tcl
#
# Recommended boot cmdline on the farm node (reboot once):
#   isolcpus=8-15 nohz_full=8-15 rcu_nocbs=8-15
# Also move IRQs off the job set (see configs/irq_affinity.example).
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 2 ]]; then
  echo "Usage: $0 <JOB_CPUS> <command> [args...]" >&2
  echo "   or: JOB_CPUS=8-15 $0 -- <command> [args...]" >&2
  exit 1
fi

if [[ "$1" == "--" ]]; then
  shift
  CPUS="${JOB_CPUS:?set JOB_CPUS or pass CPU list as first arg}"
else
  CPUS="$1"
  shift
fi

if [[ $# -lt 1 ]]; then
  echo "missing command" >&2
  exit 1
fi

echo "[fc-os-noise] pinning to CPUs $CPUS: $*"
echo "[fc-os-noise] isolated(sysfs)=$(cat /sys/devices/system/cpu/isolated 2>/dev/null || echo none)"
exec taskset -c "$CPUS" "$@"
