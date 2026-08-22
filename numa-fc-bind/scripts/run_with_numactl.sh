#!/usr/bin/env bash
# Pin an EDA (or any) command to one NUMA node's CPUs + memory.
#
#   ./scripts/run_with_numactl.sh 0 fc_shell -f run.tcl
#
# Env: MIN_MEMFREE_GIB=8  POLICY=membind|preferred  FORCE=1
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

NODE="$1"; shift
MIN_MEMFREE_GIB="${MIN_MEMFREE_GIB:-8}"
POLICY="${POLICY:-membind}"

[[ -n "${NUMACTL}" && -x "$NUMACTL" ]] || { echo "ERROR: numactl not found" >&2; exit 1; }

NODES=$(find /sys/devices/system/node -maxdepth 1 -type d -name 'node[0-9]*' 2>/dev/null | wc -l | tr -d ' ')
if [[ "${NODES}" -lt 2 ]]; then
  echo "WARNING: only ${NODES} NUMA node(s) — binding will not change DRAM locality." >&2
fi

[[ -d "/sys/devices/system/node/node${NODE}" ]] || {
  echo "ERROR: node${NODE} missing" >&2
  "$NUMACTL" -H >&2 || true
  exit 1
}

MEMFREE_KB=$(awk '/MemFree:/ {print $4}' "/sys/devices/system/node/node${NODE}/meminfo" 2>/dev/null || echo 0)
MEMFREE_GIB=$(awk -v k="$MEMFREE_KB" 'BEGIN { printf "%.2f", k/1024/1024 }')
MEMTOT_GIB=$(awk '/MemTotal:/ {printf "%.2f", $4/1024/1024}' "/sys/devices/system/node/node${NODE}/meminfo")

echo "[run_with_numactl] host=$(hostname) date=$(date -Is)"
echo "[run_with_numactl] nodes=${NODES} target=${NODE} MemTotal≈${MEMTOT_GIB}G MemFree≈${MEMFREE_GIB}G"
echo "[run_with_numactl] policy=${POLICY} cmd: $*"
"$NUMACTL" -H | sed 's/^/[numa] /'

if awk -v k="$MEMFREE_KB" -v m="$MIN_MEMFREE_GIB" 'BEGIN { exit !(k < m*1024*1024) }'; then
  if [[ "${FORCE:-0}" != "1" ]]; then
    echo "ERROR: MemFree ${MEMFREE_GIB}G < MIN_MEMFREE_GIB=${MIN_MEMFREE_GIB}. Use POLICY=preferred or FORCE=1." >&2
    exit 1
  fi
  echo "WARNING: FORCE=1 overriding MemFree guard"
fi

case "$POLICY" in
  membind) BIND=(--cpunodebind="${NODE}" --membind="${NODE}") ;;
  preferred) BIND=(--cpunodebind="${NODE}" --preferred="${NODE}") ;;
  *) echo "ERROR: POLICY=membind|preferred" >&2; exit 2 ;;
esac

echo "[run_with_numactl] exec: numactl ${BIND[*]} $*"
[[ -n "${NUMASTAT}" && -x "$NUMASTAT" ]] && echo "[run_with_numactl] later: ${NUMASTAT} -p <pid>"
exec "$NUMACTL" "${BIND[@]}" "$@"
