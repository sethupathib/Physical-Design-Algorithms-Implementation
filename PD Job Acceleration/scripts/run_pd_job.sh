#!/usr/bin/env bash
# Mode A orchestrator: stage job tree into tmpfs → run → checkpoint → finalize.
#
# By default PD_KEEP_LOGS_ON_DISK=1: after staging, workspace logs/ is a symlink
# to durable disk and logs/ are excluded from rsync. Fat PD logs must not fill RAM.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=pd_job_env.sh
source "${SCRIPT_DIR}/pd_job_env.sh"

# Globals used by EXIT trap (must not be `local` — trap runs after main returns).
PD_ORCH_TOOL_RC=0
PD_ORCH_CKPT_PID=""
PD_ORCH_CLEANED=0

usage() {
  cat <<'EOF'
Usage: run_pd_job.sh [--demo] [--keep]

Mode A: full workspace in tmpfs — only when the design/scratch fits in RAM.
Prefer ram_scratch.sh (Mode B) when RAM is limited.

Environment:
  PD_DURABLE_ROOT   Persistent job dir (required unless --demo)
  PD_JOB_NAME       Job name
  PD_TOOL_CMD       Command to run inside workspace (required unless --demo)
  PD_CHECKPOINT_SECS  Periodic checkpoint interval (0=off)
  PD_TMPFS_ROOT     Default /dev/shm/pdjobs/$USER
  PD_TMPFS_SIZE     Default 8G
  PD_KEEP_TMPFS=1   Keep RAM workspace after job
  PD_KEEP_LOGS_ON_DISK  Default 1 — logs/ stays on durable disk (not tmpfs)
  PD_SYNC_MODE          off|file|fs|global — durability flush after rsync (default fs)
  PD_SYNC_AFTER_FINALIZE  Default 1 — run shell sync after final rsync
  PD_SYNC_AFTER_CHECKPOINT  Default 0 — sync after each checkpoint (costly on NFS)
  PD_PERF=1             Wrap tool with pd_perf_profile.sh (I/O vs CPU report)

Examples:
  ./scripts/run_pd_job.sh --demo
  PD_DURABLE_ROOT=/proj/b/run1 PD_TOOL_CMD='innovus -files route.tcl -log logs/route.log' \
    ./scripts/run_pd_job.sh
EOF
}

setup_demo_tree() {
  local durable="${ROOT_DIR}/examples/demo_durable"
  rm -rf "$durable"
  mkdir -p "$durable/inputs/lef" "$durable/inputs/libs" "$durable/scripts"

  # Fake LEF / liberty / DEF-ish inputs (a few MB of compressible + random data)
  dd if=/dev/urandom of="$durable/inputs/lef/tech.lef.bin" bs=1M count=4 status=none
  dd if=/dev/urandom of="$durable/inputs/libs/slow.lib.bin" bs=1M count=6 status=none
  dd if=/dev/urandom of="$durable/inputs/libs/fast.lib.bin" bs=1M count=6 status=none
  dd if=/dev/urandom of="$durable/inputs/design.def.bin" bs=1M count=8 status=none
  printf 'VERSION 5.8 ;\nDESIGN demo ;\nEND DESIGN\n' > "$durable/inputs/design.def.header"
  cat > "$durable/scripts/run_route.tcl" <<'TCL'
# Placeholder — real flows would call Innovus/ICC2/FC here.
puts "demo tcl — actual tool command is provided by PD_TOOL_CMD"
TCL

  export PD_DURABLE_ROOT="$durable"
  export PD_JOB_NAME="${PD_JOB_NAME:-demo_block_route}"
  # Quote-safe command string for paths with spaces.
  export PD_TOOL_CMD="${PD_TOOL_CMD:-bash \"${SCRIPT_DIR}/demo_pd_workload.sh\" .}"
  export PD_CHECKPOINT_SECS="${PD_CHECKPOINT_SECS:-2}"
  export PD_DEMO=1
  pd_log "Demo durable tree ready at $PD_DURABLE_ROOT"
}

pd_orch_cleanup() {
  # Idempotent: EXIT + INT/TERM may both fire.
  [[ "$PD_ORCH_CLEANED" -eq 1 ]] && return 0
  PD_ORCH_CLEANED=1

  if [[ -n "${PD_ORCH_CKPT_PID}" ]] && kill -0 "$PD_ORCH_CKPT_PID" 2>/dev/null; then
    pd_log "Stopping checkpoint loop (pid=$PD_ORCH_CKPT_PID)"
    kill "$PD_ORCH_CKPT_PID" 2>/dev/null || true
    wait "$PD_ORCH_CKPT_PID" 2>/dev/null || true
  fi

  PD_KEEP_TMPFS="${PD_KEEP_TMPFS:-0}" \
    PD_DURABLE_ROOT="${PD_DURABLE_ROOT}" \
    PD_JOB_NAME="${PD_JOB_NAME}" \
    PD_TMPFS_ROOT="${PD_TMPFS_ROOT}" \
    "${SCRIPT_DIR}/finalize_job.sh" "$PD_ORCH_TOOL_RC" || true

  pd_log "=== PD job end: ${PD_JOB_NAME} (tool_rc=${PD_ORCH_TOOL_RC}) ==="
}

main() {
  local keep_flag=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --demo) export PD_DEMO=1; shift ;;
      --keep) keep_flag=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) pd_die "unknown arg: $1" ;;
    esac
  done

  pd_require_cmd rsync date tee bash

  if [[ "${PD_DEMO:-0}" == "1" ]]; then
    setup_demo_tree
  fi

  pd_job_defaults
  [[ "$keep_flag" -eq 1 ]] && PD_KEEP_TMPFS=1
  export PD_KEEP_TMPFS PD_DURABLE_ROOT PD_JOB_NAME PD_TMPFS_ROOT PD_TMPFS_SIZE PD_MOUNT_TMPFS
  export PD_KEEP_LOGS_ON_DISK PD_EXCLUDE_FILE PD_RSYNC_OPTS

  [[ -n "$PD_DURABLE_ROOT" ]] || { usage; pd_die "PD_DURABLE_ROOT required (or pass --demo)"; }
  [[ -n "$PD_TOOL_CMD" ]] || { usage; pd_die "PD_TOOL_CMD required (or pass --demo)"; }
  [[ -d "$PD_DURABLE_ROOT" ]] || pd_die "missing durable root: $PD_DURABLE_ROOT"

  mkdir -p "$PD_STATUS_DIR" "$PD_LOG_DIR"
  local master_log="${PD_LOG_DIR}/orchestrator_${PD_JOB_NAME}.log"
  exec > >(tee -a "$master_log") 2>&1

  pd_log "=== PD job start: ${PD_JOB_NAME} ==="
  pd_log "durable: $PD_DURABLE_ROOT"
  pd_log "tmpfs:   $PD_WORK_DIR"
  pd_log "tool:    $PD_TOOL_CMD"
  pd_log "keep_logs_on_disk=${PD_KEEP_LOGS_ON_DISK}"

  # Flush outputs home even if the job is killed.
  trap pd_orch_cleanup EXIT INT TERM

  "${SCRIPT_DIR}/stage_to_tmpfs.sh"
  pd_rewire_logs_to_disk

  if [[ "${PD_CHECKPOINT_SECS}" =~ ^[0-9]+$ && "${PD_CHECKPOINT_SECS}" -gt 0 ]]; then
    pd_log "Starting checkpoint loop every ${PD_CHECKPOINT_SECS}s"
    "${SCRIPT_DIR}/checkpoint_sync.sh" --loop "${PD_CHECKPOINT_SECS}" &
    PD_ORCH_CKPT_PID=$!
  fi

  pd_log "Launching tool in workspace (PD_PERF=${PD_PERF:-0})"
  set +e
  (
    cd "$PD_WORK_DIR"
    # bash -c keeps quoted paths intact (e.g. directories with spaces).
    if [[ "${PD_PERF:-0}" == "1" ]]; then
      PD_DURABLE_ROOT="$PD_DURABLE_ROOT" PD_JOB_NAME="$PD_JOB_NAME" \
        PD_TOOL_CMD="$PD_TOOL_CMD" \
        "${SCRIPT_DIR}/pd_perf_profile.sh" --out "${PD_LOG_DIR}/perf_${PD_JOB_NAME}"
    else
      bash -c "$PD_TOOL_CMD"
    fi
  )
  PD_ORCH_TOOL_RC=$?
  set -e

  pd_log "Tool exited with rc=${PD_ORCH_TOOL_RC}"
  # EXIT trap runs finalize
}

main "$@"
exit "$PD_ORCH_TOOL_RC"
