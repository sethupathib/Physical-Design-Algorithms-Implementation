#!/usr/bin/env bash
# Wrap an EDA (or any) command with NUMA CPU+memory binding.
#
# Usage:
#   ./scripts/run_eda_numactl.sh <node> <command> [args...]
# Example:
#   ./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl
#
# Safety: refuses membind if node MemFree looks wildly small (< 8 GiB) unless
# FORCE=1 is set. Tune for your farm.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <numa_node> <command> [args...]" >&2
  exit 2
fi

NODE="$1"
shift

if ! command -v numactl >/dev/null 2>&1; then
  echo "ERROR: numactl not found. Install numactl or run without this wrapper." >&2
  exit 1
fi

if [[ ! -d "/sys/devices/system/node/node${NODE}" ]]; then
  echo "ERROR: NUMA node${NODE} does not exist." >&2
  numactl -H >&2 || true
  exit 1
fi

MEMFREE_KB=$(awk '/MemFree:/ {print $4}' "/sys/devices/system/node/node${NODE}/meminfo" 2>/dev/null || echo 0)
MEMFREE_GIB=$(awk -v k="$MEMFREE_KB" 'BEGIN { printf "%.1f", k/1024/1024 }')
echo "[run_eda_numactl] node=${NODE} MemFree≈${MEMFREE_GIB} GiB"
echo "[run_eda_numactl] policy: --cpunodebind=${NODE} --membind=${NODE}"
echo "[run_eda_numactl] cmd: $*"

if awk -v k="$MEMFREE_KB" 'BEGIN { exit !(k < 8*1024*1024) }'; then
  if [[ "${FORCE:-0}" != "1" ]]; then
    echo "ERROR: node${NODE} MemFree < 8 GiB. Refusing membind (set FORCE=1 to override)." >&2
    exit 1
  fi
  echo "WARNING: FORCE=1 — proceeding with low MemFree."
fi

# Manifest-friendly breadcrumbs
echo "[run_eda_numactl] host=$(hostname) date=$(date -Is)"
numactl -H | sed 's/^/[numa] /'

exec numactl --cpunodebind="${NODE}" --membind="${NODE}" "$@"
