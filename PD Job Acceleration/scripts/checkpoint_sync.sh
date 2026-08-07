#!/usr/bin/env bash
# Incremental sync: tmpfs workspace → durable storage (checkpoint).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd_job_env.sh
source "${SCRIPT_DIR}/pd_job_env.sh"

usage() {
  cat <<'EOF'
Usage: checkpoint_sync.sh [--loop SECONDS]

Sync hot PD workspace back to durable storage.
With --loop, checkpoint forever every SECONDS (until killed).

Required env:
  PD_DURABLE_ROOT
  PD_JOB_NAME
EOF
}

do_checkpoint() {
  local n="${1:-manual}"
  [[ -d "$PD_WORK_DIR" ]] || pd_die "workspace missing: $PD_WORK_DIR"
  [[ -d "$PD_DURABLE_ROOT" ]] || pd_die "durable root missing: $PD_DURABLE_ROOT"

  mkdir -p "$PD_STATUS_DIR" "$PD_LOG_DIR"
  pd_log "Checkpoint #$n : ${PD_WORK_DIR}/ → ${PD_DURABLE_ROOT}/"

  local start end
  start=$(date +%s)
  # Prefer newer / changed files; keep partials if NFS hiccups mid-transfer.
  PD_RSYNC_OPTS="${PD_RSYNC_OPTS} --partial"
  pd_rsync "${PD_WORK_DIR}/" "${PD_DURABLE_ROOT}/"

  # Optional: push writeback so a crash cannot silently lose this checkpoint.
  # Default off — frequent sync on NFS can dominate; enable for long ECO jobs.
  if [[ "${PD_SYNC_AFTER_CHECKPOINT:-0}" == "1" ]]; then
    pd_durable_sync "checkpoint_${n}"
  fi
  end=$(date +%s)

  echo "checkpoint n=${n} $(date -Iseconds) duration_s=$((end - start)) sync_after=${PD_SYNC_AFTER_CHECKPOINT:-0}" \
    | tee -a "${PD_STATUS_DIR}/checkpoints.log"
  pd_log "Checkpoint #$n done in $((end - start))s"
}

main() {
  pd_require_cmd rsync
  pd_job_defaults

  [[ -n "$PD_DURABLE_ROOT" ]] || { usage; pd_die "PD_DURABLE_ROOT is required"; }

  if [[ "${1:-}" == "--loop" ]]; then
    local secs="${2:-}"
    [[ -n "$secs" && "$secs" =~ ^[0-9]+$ && "$secs" -gt 0 ]] \
      || pd_die "--loop requires positive SECONDS"
    local i=1
    while true; do
      do_checkpoint "$i" || pd_log "WARN: checkpoint $i failed (will retry)"
      i=$((i + 1))
      sleep "$secs"
    done
  else
    do_checkpoint "manual"
  fi
}

main "$@"
