#!/usr/bin/env bash
# Wrap an EDA command with NUMA CPU + memory binding on the SAME node.
#
# Usage:
#   ./scripts/run_eda_numactl.sh <node> <command> [args...]
#   ./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl
#
# Env:
#   MIN_MEMFREE_GIB  default 8 — refuse membind below this unless FORCE=1
#   POLICY           membind (default) | preferred
#   FORCE=1          override MemFree guard
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NUMACTL="${ROOT}/tools/numactl-root/usr/bin/numactl"
[[ -x "$NUMACTL" ]] || NUMACTL="$(command -v numactl || true)"
NUMASTAT="${ROOT}/tools/numactl-root/usr/bin/numastat"
[[ -x "$NUMASTAT" ]] || NUMASTAT="$(command -v numastat || true)"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <numa_node> <command> [args...]" >&2
  exit 2
fi

NODE="$1"
shift
MIN_MEMFREE_GIB="${MIN_MEMFREE_GIB:-8}"
POLICY="${POLICY:-membind}"

if [[ -z "${NUMACTL}" || ! -x "$NUMACTL" ]]; then
  echo "ERROR: numactl not found." >&2
  exit 1
fi

NODES=$(find /sys/devices/system/node -maxdepth 1 -type d -name 'node[0-9]*' 2>/dev/null | wc -l | tr -d ' ')
if [[ "${NODES}" -lt 2 ]]; then
  echo "WARNING: only ${NODES} NUMA node(s). Binding will not change DRAM locality." >&2
  echo "WARNING: proceeding anyway (affinity still applied if multiple CPUs)." >&2
fi

if [[ ! -d "/sys/devices/system/node/node${NODE}" ]]; then
  echo "ERROR: NUMA node${NODE} does not exist." >&2
  "$NUMACTL" -H >&2 || true
  exit 1
fi

MEMFREE_KB=$(awk '/MemFree:/ {print $4}' "/sys/devices/system/node/node${NODE}/meminfo" 2>/dev/null || echo 0)
MEMFREE_GIB=$(awk -v k="$MEMFREE_KB" 'BEGIN { printf "%.2f", k/1024/1024 }')
MEMTOT_KB=$(awk '/MemTotal:/ {print $4}' "/sys/devices/system/node/node${NODE}/meminfo" 2>/dev/null || echo 0)
MEMTOT_GIB=$(awk -v k="$MEMTOT_KB" 'BEGIN { printf "%.2f", k/1024/1024 }')

echo "[run_eda_numactl] host=$(hostname) date=$(date -Is)"
echo "[run_eda_numactl] nodes=${NODES} target_node=${NODE}"
echo "[run_eda_numactl] node${NODE} MemTotal≈${MEMTOT_GIB} GiB  MemFree≈${MEMFREE_GIB} GiB"
echo "[run_eda_numactl] policy=${POLICY}  cmd: $*"
"$NUMACTL" -H | sed 's/^/[numa] /'

if awk -v k="$MEMFREE_KB" -v m="$MIN_MEMFREE_GIB" 'BEGIN { exit !(k < m*1024*1024) }'; then
  if [[ "${FORCE:-0}" != "1" ]]; then
    echo "ERROR: node${NODE} MemFree ${MEMFREE_GIB} GiB < MIN_MEMFREE_GIB=${MIN_MEMFREE_GIB}." >&2
    echo "ERROR: hard membind can OOM. Use POLICY=preferred, lower RSS, or FORCE=1." >&2
    exit 1
  fi
  echo "WARNING: FORCE=1 — overriding MemFree guard."
fi

case "$POLICY" in
  membind)
    BIND=(--cpunodebind="${NODE}" --membind="${NODE}")
    ;;
  preferred)
    BIND=(--cpunodebind="${NODE}" --preferred="${NODE}")
    ;;
  *)
    echo "ERROR: POLICY must be membind or preferred (got: ${POLICY})" >&2
    exit 2
    ;;
esac

echo "[run_eda_numactl] exec: numactl ${BIND[*]} $*"
if [[ -n "${NUMASTAT}" && -x "$NUMASTAT" ]]; then
  echo "[run_eda_numactl] after start, check: ${NUMASTAT} -p <pid>"
fi

exec "$NUMACTL" "${BIND[@]}" "$@"
