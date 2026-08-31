#!/usr/bin/env bash
# Probe whether this kernel can actually run sched_ext BPF schedulers.
set -euo pipefail

echo "kernel: $(uname -r)"
if [[ -d /sys/kernel/sched_ext ]]; then
  echo "sched_ext_sysfs: PRESENT"
  ls -la /sys/kernel/sched_ext || true
else
  echo "sched_ext_sysfs: ABSENT  (CONFIG_SCHED_EXT almost certainly off)"
fi

if [[ -e /sys/kernel/btf/vmlinux ]]; then
  echo "btf_vmlinux: PRESENT"
else
  echo "btf_vmlinux: ABSENT  (BPF typed schedulers cannot load)"
fi

echo "cgroup_controllers: $(cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null || echo none)"
echo "nproc: $(nproc)"
