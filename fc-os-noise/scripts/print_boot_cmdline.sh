#!/usr/bin/env bash
# Print recommended kernel cmdline additions for a given job CPU set.
set -euo pipefail
CPUS="${1:-8-15}"
HK="${2:-0-7}"
cat <<EOF
# Housekeeping CPUs (OS, IRQs, ssh, license heartbeats): $HK
# Job CPUs (Fusion Compiler / FC-class workers):         $CPUS

# Append to GRUB_CMDLINE_LINUX (then update-grub && reboot):
isolcpus=$CPUS nohz_full=$CPUS rcu_nocbs=$CPUS

# After reboot, verify:
cat /proc/cmdline
cat /sys/devices/system/cpu/isolated
cat /sys/devices/system/cpu/nohz_full

# Run FC on the quiet set:
taskset -c $CPUS fc_shell -f run.tcl
# or:
./scripts/run_fc_isolated.sh $CPUS fc_shell -f run.tcl

# Match tool thread count to the isolated width (example: 8 CPUs):
#   set_host_options -max_cores 8
EOF
