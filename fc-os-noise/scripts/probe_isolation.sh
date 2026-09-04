#!/usr/bin/env bash
# Probe host readiness for FC OS-noise isolation.
set -euo pipefail

echo "kernel: $(uname -r)"
echo "cmdline: $(cat /proc/cmdline)"
echo "nproc: $(nproc)"
echo "online: $(cat /sys/devices/system/cpu/online)"
echo -n "isolated(sysfs): "
cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "(empty/absent)"
echo -n "nohz_full(sysfs): "
cat /sys/devices/system/cpu/nohz_full 2>/dev/null || echo "(empty/absent)"

if grep -qE 'isolcpus=' /proc/cmdline; then
  echo "boot_isolcpus: PRESENT"
else
  echo "boot_isolcpus: ABSENT  (demo uses taskset/cpuset soft-isolation without reboot)"
fi
if grep -qE 'nohz_full=' /proc/cmdline; then
  echo "boot_nohz_full: PRESENT"
else
  echo "boot_nohz_full: ABSENT"
fi
if grep -qE 'rcu_nocbs=' /proc/cmdline; then
  echo "boot_rcu_nocbs: PRESENT"
else
  echo "boot_rcu_nocbs: ABSENT"
fi

echo "taskset: $(command -v taskset)"
echo "cpuset_controller: $(grep -w cpuset /sys/fs/cgroup/cgroup.controllers 2>/dev/null || echo no)"
