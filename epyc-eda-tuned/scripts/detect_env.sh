#!/usr/bin/env bash
# detect_env.sh — inventory host capability for epyc-eda experiments.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/results/host_inventory.txt}"
mkdir -p "$(dirname "$OUT")"

{
  echo "# epyc-eda-tuned host inventory"
  echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname)"
  echo "uname=$(uname -a)"
  echo

  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "os_name=${NAME:-unknown}"
    echo "os_version=${VERSION_ID:-unknown}"
  fi

  echo "nproc=$(nproc)"
  if command -v lscpu >/dev/null 2>&1; then
    echo "cpu_model=$(lscpu | awk -F: '/Model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
    echo "cpu_vendor=$(lscpu | awk -F: '/Vendor ID/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
    echo "sockets=$(lscpu | awk -F: '/Socket\(s\)/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
    echo "cores_per_socket=$(lscpu | awk -F: '/Core\(s\) per socket/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
    echo "threads_per_core=$(lscpu | awk -F: '/Thread\(s\) per core/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
    echo "numa_nodes=$(lscpu | awk -F: '/NUMA node\(s\)/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
  fi

  echo
  echo "## tuned"
  if command -v tuned-adm >/dev/null 2>&1; then
    echo "tuned_adm=present"
    tuned-adm active 2>/dev/null | sed 's/^/tuned_active_line=/' || echo "tuned_active_line=error"
    if tuned-adm list 2>/dev/null | grep -q 'epyc-eda'; then
      echo "epyc_eda_profile=available"
    else
      echo "epyc_eda_profile=missing"
    fi
  else
    echo "tuned_adm=absent"
    echo "epyc_eda_profile=unavailable"
  fi

  echo
  echo "## sched_migration_cost_ns paths"
  MIG_PROC=/proc/sys/kernel/sched_migration_cost_ns
  MIG_DBG=/sys/kernel/debug/sched/migration_cost_ns
  if [[ -r "$MIG_PROC" ]]; then
    echo "migration_cost_path=$MIG_PROC"
    echo "migration_cost_ns=$(cat "$MIG_PROC")"
    if [[ -w "$MIG_PROC" ]]; then echo "migration_cost_writable=yes"; else echo "migration_cost_writable=no"; fi
  elif [[ -r "$MIG_DBG" ]]; then
    echo "migration_cost_path=$MIG_DBG"
    echo "migration_cost_ns=$(cat "$MIG_DBG")"
    if [[ -w "$MIG_DBG" ]]; then echo "migration_cost_writable=yes"; else echo "migration_cost_writable=no"; fi
  else
    echo "migration_cost_path=none"
    echo "migration_cost_ns=unknown"
    echo "migration_cost_writable=no"
    echo "note=debugfs may need: mount -t debugfs none /sys/kernel/debug (root)"
  fi

  echo
  echo "## capability flags"
  AMD=0
  if lscpu 2>/dev/null | grep -qi 'AuthenticAMD\|AMD'; then AMD=1; fi
  echo "is_amd=$AMD"

  TUNED=0
  command -v tuned-adm >/dev/null 2>&1 && TUNED=1
  echo "has_tuned=$TUNED"

  WRITE=0
  if [[ -w "${MIG_PROC:-/}" ]] || [[ -w "${MIG_DBG:-/}" ]]; then WRITE=1; fi
  # recompute writable carefully
  WRITE=0
  [[ -w "$MIG_PROC" ]] && WRITE=1
  [[ -w "$MIG_DBG" ]] && WRITE=1
  echo "can_set_migration_cost=$WRITE"

  if [[ $WRITE -eq 1 ]]; then
    echo "claim_gate_eligible=yes"
    echo "claim_gate_blockers="
  else
    echo "claim_gate_eligible=no"
    blockers=()
    [[ $WRITE -eq 0 ]] && blockers+=("migration_cost_not_writable")
    [[ $TUNED -eq 0 ]] && blockers+=("tuned_absent_optional")
    echo "claim_gate_blockers=$(IFS=,; echo "${blockers[*]}")"
  fi
} | tee "$OUT"

echo "wrote=$OUT" >&2
