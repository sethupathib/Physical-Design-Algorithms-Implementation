#!/usr/bin/env bash
# dump_sched_knobs.sh — snapshot scheduler / VM knobs relevant to epyc-eda.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/results/sched_knobs.txt}"
mkdir -p "$(dirname "$OUT")"

dump_file() {
  local f="$1"
  if [[ -r "$f" ]]; then
    echo "$f=$(cat "$f" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  else
    echo "$f=UNREADABLE"
  fi
}

{
  echo "# sched / vm knob dump"
  echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  dump_file /proc/sys/kernel/sched_migration_cost_ns
  dump_file /sys/kernel/debug/sched/migration_cost_ns
  dump_file /proc/sys/kernel/sched_min_granularity_ns
  dump_file /sys/kernel/debug/sched/min_granularity_ns
  dump_file /proc/sys/kernel/sched_wakeup_granularity_ns
  dump_file /sys/kernel/debug/sched/wakeup_granularity_ns
  dump_file /proc/sys/kernel/sched_latency_ns
  dump_file /sys/kernel/debug/sched/latency_ns
  dump_file /proc/sys/kernel/numa_balancing
  dump_file /proc/sys/vm/swappiness
  dump_file /proc/sys/vm/dirty_ratio
  dump_file /proc/sys/vm/dirty_background_ratio
  if [[ -r /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]]; then
    echo "scaling_governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
  fi
  if command -v tuned-adm >/dev/null 2>&1; then
    tuned-adm active 2>/dev/null | sed 's/^/tuned_active=/' || true
  fi
} | tee "$OUT"
echo "wrote=$OUT" >&2
