#!/usr/bin/env bash
# Shared environment helpers for PD tmpfs + rsync job management.
# shellcheck disable=SC2034

set -euo pipefail

pd_job_defaults() {
  : "${PD_JOB_NAME:=pd_job_$(date +%Y%m%d_%H%M%S)}"
  : "${PD_DURABLE_ROOT:=}"
  : "${PD_TMPFS_ROOT:=/dev/shm/pdjobs/${USER:-user}}"
  : "${PD_TMPFS_SIZE:=8G}"
  : "${PD_MOUNT_TMPFS:=auto}"   # auto | yes | no
  : "${PD_CHECKPOINT_SECS:=0}"  # 0 = disabled
  : "${PD_KEEP_TMPFS:=0}"       # 1 = leave workspace after finalize
  : "${PD_RSYNC_OPTS:=-aH --human-readable --info=stats2}"
  : "${PD_EXCLUDE_FILE:=}"
  : "${PD_TOOL_CMD:=}"
  : "${PD_DEMO:=0}"

  PD_WORK_DIR="${PD_TMPFS_ROOT}/${PD_JOB_NAME}"
  PD_STATUS_DIR="${PD_DURABLE_ROOT}/.pd_job_status"
  PD_LOG_DIR="${PD_DURABLE_ROOT}/logs"
}

pd_require_cmd() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || {
      echo "ERROR: required command not found: $c" >&2
      exit 127
    }
  done
}

pd_log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] $*"
}

pd_die() {
  echo "ERROR: $*" >&2
  exit 1
}

# Decide whether we can mount a dedicated tmpfs, or just use /dev/shm.
pd_prepare_workspace() {
  mkdir -p "$PD_TMPFS_ROOT"

  local do_mount=0
  case "$PD_MOUNT_TMPFS" in
    yes) do_mount=1 ;;
    no)  do_mount=0 ;;
    auto)
      if [[ -d /dev/shm && -w /dev/shm ]]; then
        # /dev/shm is already tmpfs on most Linux hosts — no mount needed.
        do_mount=0
      elif [[ "$(id -u)" -eq 0 ]]; then
        do_mount=1
      else
        do_mount=0
      fi
      ;;
    *) pd_die "PD_MOUNT_TMPFS must be auto|yes|no" ;;
  esac

  mkdir -p "$PD_WORK_DIR"

  if [[ "$do_mount" -eq 1 ]]; then
    if ! mountpoint -q "$PD_WORK_DIR" 2>/dev/null; then
      pd_log "Mounting tmpfs at $PD_WORK_DIR (size=$PD_TMPFS_SIZE)"
      mount -t tmpfs -o "size=${PD_TMPFS_SIZE},mode=0755" tmpfs "$PD_WORK_DIR" \
        || pd_die "tmpfs mount failed (need root/CAP_SYS_ADMIN, or set PD_MOUNT_TMPFS=no)"
    fi
  else
    pd_log "Using existing RAM-backed path: $PD_WORK_DIR (under ${PD_TMPFS_ROOT})"
  fi
}

pd_rsync_excludes() {
  local args=()
  # Regenerable / noisy PD artifacts — tune for your flow.
  args+=(
    --exclude='.pd_job_status/'
    --exclude='*.tmp'
    --exclude='*.swp'
    --exclude='core'
    --exclude='core.*'
    --exclude='.nfs*'
  )
  if [[ -n "${PD_EXCLUDE_FILE}" && -f "${PD_EXCLUDE_FILE}" ]]; then
    args+=(--exclude-from="$PD_EXCLUDE_FILE")
  fi
  printf '%s\0' "${args[@]}"
}

pd_rsync() {
  # Usage: pd_rsync SRC/ DEST/
  local src="$1" dest="$2"
  mkdir -p "$dest"
  # shellcheck disable=SC2086
  local -a excl=()
  local item
  while IFS= read -r -d '' item; do
    excl+=("$item")
  done < <(pd_rsync_excludes)

  # shellcheck disable=SC2086
  rsync ${PD_RSYNC_OPTS} "${excl[@]}" "$src" "$dest"
}
