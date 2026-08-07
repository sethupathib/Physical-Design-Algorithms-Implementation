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
  # Fat PD logs often exceed 20GB — keep them on disk even in Mode A.
  : "${PD_KEEP_LOGS_ON_DISK:=1}"
  : "${PD_RSYNC_OPTS:=-aH --human-readable --info=stats2}"
  : "${PD_EXCLUDE_FILE:=}"
  : "${PD_TOOL_CMD:=}"
  : "${PD_DEMO:=0}"
  # Durability flush after rsync (the shell `sync` command — not rsync).
  #   off    — no fsync/sync (fastest; weaker crash durability)
  #   file   — sync marker file under durable root (GNU sync FILE)
  #   fs     — sync filesystem(s) containing durable root (GNU sync -f)
  #   global — sync entire machine (heavy; avoid on busy farm nodes)
  : "${PD_SYNC_MODE:=fs}"
  : "${PD_SYNC_AFTER_CHECKPOINT:=0}"  # 1 = also sync after each checkpoint
  : "${PD_SYNC_AFTER_FINALIZE:=1}"    # 1 = sync after final rsync (recommended)
  # Optional tool wrapping: PD_PERF=1 runs the tool under pd_perf_profile.sh
  : "${PD_PERF:=0}"
  : "${PD_PERF_RECORD:=0}"

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
    --exclude='.pd_ram_scratch/'
    --exclude='*.tmp'
    --exclude='*.swp'
    --exclude='core'
    --exclude='core.*'
    --exclude='.nfs*'
  )
  # When logs live on durable disk (symlink from workspace), do not rsync them
  # through tmpfs — avoids copying 20GB+ logs into / out of RAM.
  # Use 'logs' not 'logs/': a workspace symlink named logs does not match 'logs/'.
  if [[ "${PD_KEEP_LOGS_ON_DISK:-1}" == "1" ]]; then
    args+=(--exclude='logs' --exclude='logs/***')
  fi
  if [[ -n "${PD_EXCLUDE_FILE}" && -f "${PD_EXCLUDE_FILE}" ]]; then
    args+=(--exclude-from="$PD_EXCLUDE_FILE")
  fi
  printf '%s\0' "${args[@]}"
}

# After staging Mode A workspace: point logs/ at durable disk, not tmpfs.
pd_rewire_logs_to_disk() {
  if [[ "${PD_KEEP_LOGS_ON_DISK:-1}" != "1" ]]; then
    pd_log "PD_KEEP_LOGS_ON_DISK=0 — logs may consume tmpfs (dangerous if huge)"
    return 0
  fi

  # Durable logs must be a real directory — never a symlink (avoids cycles if a
  # prior rsync wrongly copied workspace logs → durable).
  if [[ -L "${PD_DURABLE_ROOT}/logs" ]]; then
    pd_log "WARN: durable logs/ was a symlink; replacing with a real directory"
    rm -f "${PD_DURABLE_ROOT}/logs"
  fi
  mkdir -p "${PD_DURABLE_ROOT}/logs"

  rm -rf "${PD_WORK_DIR}/logs"
  ln -s "${PD_DURABLE_ROOT}/logs" "${PD_WORK_DIR}/logs"
  pd_log "logs/ → durable disk (${PD_DURABLE_ROOT}/logs); excluded from tmpfs rsync"
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

# Push kernel writeback to durable media after rsync.
# rsync only copies into the page cache unless the destination already fsynced;
# without this, a node crash can lose a "successful" checkpoint.
#
# Usage: pd_durable_sync [reason]
pd_durable_sync() {
  local reason="${1:-manual}"
  local mode="${PD_SYNC_MODE:-fs}"
  local root="${PD_DURABLE_ROOT:-}"
  local start end marker

  case "$mode" in
    off|0|no|none)
      pd_log "durable sync skipped (PD_SYNC_MODE=${mode}) reason=${reason}"
      return 0
      ;;
  esac

  command -v sync >/dev/null 2>&1 || {
    pd_log "WARN: sync(1) not found; cannot harden durability after ${reason}"
    return 0
  }

  start=$(date +%s)
  case "$mode" in
    file)
      [[ -n "$root" && -d "$root" ]] || {
        pd_log "WARN: PD_DURABLE_ROOT missing for file sync; falling back to global sync"
        sync
        return 0
      }
      mkdir -p "${root}/.pd_job_status"
      marker="${root}/.pd_job_status/last_sync_marker"
      date -Iseconds >"$marker" 2>/dev/null || echo "synced" >"$marker"
      # GNU sync FILE → fsync that file (and often enough for NFS client writeback).
      if sync "$marker" 2>/dev/null; then
        :
      else
        sync
      fi
      ;;
    fs|filesystem)
      if [[ -n "$root" && -e "$root" ]] && sync -f "$root" 2>/dev/null; then
        :
      elif [[ -n "$root" && -e "$root" ]] && sync "$root" 2>/dev/null; then
        :
      else
        sync
      fi
      ;;
    global|all)
      sync
      ;;
    *)
      pd_log "WARN: unknown PD_SYNC_MODE=${mode}; using fs"
      if [[ -n "$root" && -e "$root" ]] && sync -f "$root" 2>/dev/null; then
        :
      else
        sync
      fi
      ;;
  esac
  end=$(date +%s)
  pd_log "durable sync (${mode}) after ${reason} in $((end - start))s"

  if [[ -n "$root" ]]; then
    mkdir -p "${root}/.pd_job_status"
    echo "sync mode=${mode} reason=${reason} $(date -Iseconds)" \
      >> "${root}/.pd_job_status/sync.log" 2>/dev/null || true
  fi
}

# Resolve a usable perf binary (cloud images often ship a mismatched wrapper).
pd_find_perf() {
  local p cand
  if [[ -n "${PD_PERF_BIN:-}" && -x "${PD_PERF_BIN}" ]]; then
    printf '%s\n' "${PD_PERF_BIN}"
    return 0
  fi
  for cand in \
    "$(command -v perf 2>/dev/null || true)" \
    /usr/lib/linux-tools-*/perf
  do
    [[ -n "$cand" && -x "$cand" ]] || continue
    # Reject the stub that only prints "perf not found for kernel ..."
    if "$cand" --version >/dev/null 2>&1; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  return 1
}
