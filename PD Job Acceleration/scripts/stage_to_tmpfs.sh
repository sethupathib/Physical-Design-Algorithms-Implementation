#!/usr/bin/env bash
# Stage a durable PD job tree into a RAM-backed workspace.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd_job_env.sh
source "${SCRIPT_DIR}/pd_job_env.sh"

usage() {
  cat <<'EOF'
Usage: stage_to_tmpfs.sh

Required env:
  PD_DURABLE_ROOT   Persistent job directory (NFS / disk)
  PD_JOB_NAME       Job name (workspace under PD_TMPFS_ROOT)

Optional env:
  PD_TMPFS_ROOT     Default: /dev/shm/pdjobs/$USER
  PD_TMPFS_SIZE     Default: 8G (only used if mounting)
  PD_MOUNT_TMPFS    auto|yes|no (default: auto)
  PD_EXCLUDE_FILE   Extra rsync exclude patterns file
EOF
}

main() {
  pd_require_cmd rsync mkdir
  pd_job_defaults

  [[ -n "$PD_DURABLE_ROOT" ]] || { usage; pd_die "PD_DURABLE_ROOT is required"; }
  [[ -d "$PD_DURABLE_ROOT" ]] || pd_die "PD_DURABLE_ROOT does not exist: $PD_DURABLE_ROOT"

  pd_prepare_workspace
  mkdir -p "$PD_STATUS_DIR" "$PD_LOG_DIR"

  pd_log "Staging durable → tmpfs"
  pd_log "  from: ${PD_DURABLE_ROOT}/"
  pd_log "  to:   ${PD_WORK_DIR}/"

  local start end
  start=$(date +%s)
  pd_rsync "${PD_DURABLE_ROOT}/" "${PD_WORK_DIR}/"
  end=$(date +%s)

  echo "staged $(date -Iseconds) duration_s=$((end - start))" \
    > "${PD_STATUS_DIR}/last_stage.txt"
  pd_log "Stage complete in $((end - start))s → ${PD_WORK_DIR}"
}

main "$@"
