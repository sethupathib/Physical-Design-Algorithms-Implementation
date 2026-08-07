#!/usr/bin/env bash
# Final rsync from tmpfs → durable, write status, optional cleanup.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd_job_env.sh
source "${SCRIPT_DIR}/pd_job_env.sh"

usage() {
  cat <<'EOF'
Usage: finalize_job.sh [exit_code]

Required env:
  PD_DURABLE_ROOT
  PD_JOB_NAME

Optional:
  PD_KEEP_TMPFS=1   keep RAM workspace after finalize
EOF
}

main() {
  pd_require_cmd rsync
  pd_job_defaults

  local tool_rc="${1:-0}"
  [[ -n "$PD_DURABLE_ROOT" ]] || { usage; pd_die "PD_DURABLE_ROOT is required"; }

  mkdir -p "$PD_STATUS_DIR" "$PD_LOG_DIR"

  if [[ -d "$PD_WORK_DIR" ]]; then
    pd_log "Final sync: ${PD_WORK_DIR}/ → ${PD_DURABLE_ROOT}/"
    local start end
    start=$(date +%s)
    PD_RSYNC_OPTS="${PD_RSYNC_OPTS} --partial --delete-delay"
    # --delete-delay: durable mirrors workspace; regenerable junk already excluded.
    pd_rsync "${PD_WORK_DIR}/" "${PD_DURABLE_ROOT}/"
    # Harden durability: rsync ≠ durable on media until writeback is flushed.
    if [[ "${PD_SYNC_AFTER_FINALIZE:-1}" == "1" ]]; then
      pd_durable_sync "finalize"
    fi
    end=$(date +%s)
    echo "finalized $(date -Iseconds) duration_s=$((end - start)) tool_rc=${tool_rc} sync_mode=${PD_SYNC_MODE:-fs}" \
      > "${PD_STATUS_DIR}/last_finalize.txt"
    pd_log "Final sync done in $((end - start))s"
  else
    pd_log "WARN: workspace missing at finalize: $PD_WORK_DIR"
  fi

  if [[ "$tool_rc" -eq 0 ]]; then
    echo "PASS $(date -Iseconds)" > "${PD_STATUS_DIR}/STATUS"
  else
    echo "FAIL rc=${tool_rc} $(date -Iseconds)" > "${PD_STATUS_DIR}/STATUS"
  fi

  if [[ "${PD_KEEP_TMPFS}" != "1" && -d "$PD_WORK_DIR" ]]; then
    if mountpoint -q "$PD_WORK_DIR" 2>/dev/null; then
      pd_log "Unmounting $PD_WORK_DIR"
      umount "$PD_WORK_DIR" || pd_log "WARN: umount failed"
      rmdir "$PD_WORK_DIR" 2>/dev/null || true
    else
      pd_log "Removing workspace $PD_WORK_DIR"
      rm -rf "$PD_WORK_DIR"
    fi
  else
    pd_log "Keeping workspace (PD_KEEP_TMPFS=${PD_KEEP_TMPFS}): $PD_WORK_DIR"
  fi

  exit "$tool_rc"
}

main "$@"
