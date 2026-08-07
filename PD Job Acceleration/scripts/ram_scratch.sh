#!/usr/bin/env bash
# Limited-RAM mode: keep design + (usually) logs on disk; put small scratch in tmpfs.
#
# IMPORTANT: Do NOT put huge PD logs (often 10–50GB+) into RAM by default.
# Prefer local SSD/NVMe for fat logs. RAM is for small, high-IOPS, short-lived
# temp dirs / TMPDIR only — unless you have measured the log and it fits.
#
# Usage:
#   ram_scratch.sh setup    # create RAM scratch + redirect paths
#   ram_scratch.sh flush    # rsync RAM scratch worth keeping → durable
#   ram_scratch.sh teardown # flush + remove redirects + free RAM
#   ram_scratch.sh env      # print export lines (TMPDIR, etc.) for the tool
#   ram_scratch.sh --demo   # self-contained demo
#
# Env:
#   PD_DURABLE_ROOT   Job directory on disk/NFS (required)
#   PD_JOB_NAME       Name slice under /dev/shm (default: scratch_<pid>)
#   PD_SCRATCH_SIZE   Soft target for docs only; /dev/shm is shared RAM
#   PD_RAM_PATHS      Space-separated relative dirs to put in RAM
#                     default: "tmp"  (NOT logs — logs are often huge)
#   PD_FLUSH_ON_TEARDOWN  1 (default) flush before removing RAM copies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=pd_job_env.sh
source "${SCRIPT_DIR}/pd_job_env.sh"

: "${PD_TMPFS_ROOT:=/dev/shm/pdjobs/${USER:-user}}"
: "${PD_RAM_PATHS:=tmp}"
: "${PD_FLUSH_ON_TEARDOWN:=1}"
: "${PD_SCRATCH_SIZE:=2G}"

PD_SCRATCH_DIR=""
PD_META_DIR=""

usage() {
  cat <<'EOF'
Usage: ram_scratch.sh {setup|flush|teardown|env|run|--demo}

Keep big design DBs and fat logs on disk. Redirect only small scratch
paths into /dev/shm, and set TMPDIR there.

  setup      Create scratch + symlink PD_RAM_PATHS from durable → RAM
  flush      rsync selected RAM dirs back into durable (replace symlinks' targets)
  teardown   flush (default) + unlink redirects + rm scratch
  env        Print shell exports for the tool process
  run        setup, run PD_TOOL_CMD with TMPDIR in RAM, teardown
  --demo     DB+logs on disk; only tmp/TMPDIR in RAM

Example (default: tmp only — not logs):
  export PD_DURABLE_ROOT=/proj/blockA/run1
  export PD_RAM_PATHS="tmp"          # add more only if sized + measured
  export PD_TOOL_CMD='innovus -files route.tcl -log logs/route.log'
  ./scripts/ram_scratch.sh run

Fat logs (20GB+): keep on local SSD/NVMe, not tmpfs. NFS if you must.
EOF
}

require_durable() {
  [[ -n "${PD_DURABLE_ROOT:-}" ]] || pd_die "PD_DURABLE_ROOT is required"
  [[ -d "$PD_DURABLE_ROOT" ]] || pd_die "PD_DURABLE_ROOT missing: $PD_DURABLE_ROOT"
  : "${PD_JOB_NAME:=scratch_$$}"
  PD_SCRATCH_DIR="${PD_TMPFS_ROOT}/${PD_JOB_NAME}.scratch"
  PD_META_DIR="${PD_DURABLE_ROOT}/.pd_ram_scratch"
}

rel_paths() {
  # shellcheck disable=SC2206
  local -a paths=( $PD_RAM_PATHS )
  local p
  for p in "${paths[@]}"; do
    [[ -n "$p" ]] || continue
    [[ "$p" != /* ]] || pd_die "PD_RAM_PATHS must be relative (got: $p)"
    [[ "$p" != *..* ]] || pd_die "PD_RAM_PATHS cannot contain .. (got: $p)"
    printf '%s\n' "$p"
  done
}

setup_scratch() {
  require_durable
  pd_require_cmd rsync mkdir ln rm

  mkdir -p "$PD_SCRATCH_DIR" "$PD_META_DIR"
  # Always provide a generic temp root tools honor via TMPDIR.
  mkdir -p "${PD_SCRATCH_DIR}/_tmpdir"

  local rel ram_target durable_path backup
  while IFS= read -r rel; do
    ram_target="${PD_SCRATCH_DIR}/${rel}"
    durable_path="${PD_DURABLE_ROOT}/${rel}"
    mkdir -p "$ram_target"

    if [[ -L "$durable_path" ]]; then
      # Already redirected; ensure it points at our scratch.
      ln -sfn "$ram_target" "$durable_path"
    elif [[ -d "$durable_path" ]]; then
      # Preserve any pre-existing durable logs, then replace dir with symlink.
      backup="${PD_META_DIR}/backup_$(echo "$rel" | tr '/' '_')"
      mkdir -p "$backup"
      # Copy existing content into RAM so the tool still sees prior logs.
      rsync -a "${durable_path}/" "${ram_target}/"
      # Keep a durable backup copy, then swap in the symlink.
      rsync -a "${durable_path}/" "${backup}/"
      rm -rf "$durable_path"
      ln -s "$ram_target" "$durable_path"
      pd_log "Redirected ${rel}/ → RAM (prior files kept in RAM + backup ${backup})"
    elif [[ -e "$durable_path" ]]; then
      pd_die "refusing to redirect non-directory path: $durable_path"
    else
      ln -s "$ram_target" "$durable_path"
      pd_log "Redirected ${rel}/ → RAM (new)"
    fi
  done < <(rel_paths)

  # Record meta for flush/teardown.
  {
    echo "scratch_dir=$PD_SCRATCH_DIR"
    echo "job_name=$PD_JOB_NAME"
    echo "ram_paths=$PD_RAM_PATHS"
    echo "created=$(date -Iseconds)"
  } > "${PD_META_DIR}/active.env"

  pd_log "RAM scratch ready: $PD_SCRATCH_DIR (target size hint: $PD_SCRATCH_SIZE)"
  pd_log "Export TMPDIR before launching the tool (or use: ram_scratch.sh run)"
  df -h "$PD_SCRATCH_DIR" | tail -n 1 || true
}

print_env() {
  require_durable
  local tmp="${PD_SCRATCH_DIR}/_tmpdir"
  mkdir -p "$tmp"
  cat <<EOF
export TMPDIR="$tmp"
export TMP="$tmp"
export TEMP="$tmp"
# Keep tool logs on disk, e.g. -log logs/route.log (not in PD_RAM_PATHS).
EOF
}

flush_scratch() {
  require_durable
  pd_require_cmd rsync

  [[ -d "$PD_SCRATCH_DIR" ]] || {
    pd_log "Nothing to flush (no scratch at $PD_SCRATCH_DIR)"
    return 0
  }

  local rel ram_target durable_path staging
  while IFS= read -r rel; do
    ram_target="${PD_SCRATCH_DIR}/${rel}"
    durable_path="${PD_DURABLE_ROOT}/${rel}"
    [[ -d "$ram_target" ]] || continue

    # If durable path is a symlink into RAM, materialize onto disk beside it.
    staging="${PD_META_DIR}/flush_$(echo "$rel" | tr '/' '_')"
    rm -rf "$staging"
    mkdir -p "$staging"
    rsync -a --delete "${ram_target}/" "${staging}/"

    if [[ -L "$durable_path" ]]; then
      rm -f "$durable_path"
      mv "$staging" "$durable_path"
      # Recreate symlink? No — flush materializes durable copy.
      # setup() can re-redirect later if needed.
      pd_log "Flushed ${rel}/ from RAM → durable directory"
    else
      mkdir -p "$durable_path"
      rsync -a "${staging}/" "${durable_path}/"
      rm -rf "$staging"
      pd_log "Flushed ${rel}/ from RAM → ${durable_path}/"
    fi
  done < <(rel_paths)

  echo "flushed $(date -Iseconds)" >> "${PD_META_DIR}/flush.log"
}

teardown_scratch() {
  require_durable

  if [[ "${PD_FLUSH_ON_TEARDOWN}" == "1" ]]; then
    # Flush while symlinks still point at RAM.
    if [[ -d "$PD_SCRATCH_DIR" ]]; then
      # Materialize without going through flush's symlink removal for paths
      # that are still linked — use a dedicated path.
      local rel ram_target durable_path material
      while IFS= read -r rel; do
        ram_target="${PD_SCRATCH_DIR}/${rel}"
        durable_path="${PD_DURABLE_ROOT}/${rel}"
        [[ -d "$ram_target" ]] || continue
        material="${PD_META_DIR}/material_$(echo "$rel" | tr '/' '_')"
        rm -rf "$material"
        mkdir -p "$material"
        rsync -a "${ram_target}/" "${material}/"
        if [[ -L "$durable_path" || -e "$durable_path" ]]; then
          rm -rf "$durable_path"
        fi
        mv "$material" "$durable_path"
        pd_log "Materialized ${rel}/ onto durable storage"
      done < <(rel_paths)
    fi
  else
    # Drop redirects; discard RAM contents.
    local rel durable_path
    while IFS= read -r rel; do
      durable_path="${PD_DURABLE_ROOT}/${rel}"
      if [[ -L "$durable_path" ]]; then
        rm -f "$durable_path"
        mkdir -p "$durable_path"
        pd_log "Removed RAM redirect for ${rel}/ (not flushed)"
      fi
    done < <(rel_paths)
  fi

  if [[ -d "$PD_SCRATCH_DIR" ]]; then
    rm -rf "$PD_SCRATCH_DIR"
    pd_log "Freed RAM scratch: $PD_SCRATCH_DIR"
  fi
  rm -f "${PD_META_DIR}/active.env" 2>/dev/null || true
}

run_with_scratch() {
  require_durable
  [[ -n "${PD_TOOL_CMD:-}" ]] || pd_die "PD_TOOL_CMD is required for run"

  setup_scratch
  # shellcheck disable=SC1090
  eval "$(print_env)"

  local rc=0
  pd_log "Running tool with TMPDIR=$TMPDIR"
  (
    cd "$PD_DURABLE_ROOT"
    bash -c "$PD_TOOL_CMD"
  ) || rc=$?

  teardown_scratch
  return "$rc"
}

demo() {
  local durable="${ROOT_DIR}/examples/demo_ram_scratch"
  rm -rf "$durable"
  mkdir -p "$durable/outputs" "$durable/scripts"
  # "Big" design stays on disk — do NOT put this in PD_RAM_PATHS.
  dd if=/dev/urandom of="$durable/outputs/design.db" bs=1M count=32 status=none
  echo "fake db on disk" > "$durable/outputs/design.db.readme"

  export PD_DURABLE_ROOT="$durable"
  export PD_JOB_NAME="demo_ram_scratch"
  export PD_RAM_PATHS="tmp"   # deliberately NOT logs
  export PD_TOOL_CMD="bash \"${SCRIPT_DIR}/demo_ram_scratch_workload.sh\""

  pd_log "Demo durable tree: $durable (design.db + logs on disk; tmp in RAM)"
  run_with_scratch

  echo
  pd_log "After teardown:"
  echo "  design.db size:     $(du -h "$durable/outputs/design.db" | awk '{print $1}') (disk)"
  echo "  logs/run.log size:  $(du -h "$durable/logs/run.log" | awk '{print $1}') (disk, never RAM)"
  if [[ -L "$durable/logs" ]]; then
    echo "  logs is symlink?    yes (WRONG — logs should stay on disk)"
  else
    echo "  logs is symlink?    no (good — logs stayed on disk)"
  fi
  if [[ -L "$durable/tmp" ]]; then
    echo "  tmp is symlink?     yes (unexpected after teardown)"
  else
    echo "  tmp is symlink?     no (materialized after flush)"
  fi
  if [[ -d "${PD_TMPFS_ROOT}/demo_ram_scratch.scratch" ]]; then
    echo "  RAM scratch remains? yes"
  else
    echo "  RAM scratch remains? no"
  fi
  echo
  echo "---- logs/run.log (tail) ----"
  tail -n 8 "$durable/logs/run.log"
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    setup) setup_scratch ;;
    flush) flush_scratch ;;
    teardown) teardown_scratch ;;
    env) print_env ;;
    run) run_with_scratch ;;
    --demo) demo ;;
    -h|--help|"") usage; [[ -n "$cmd" ]] || exit 1 ;;
    *) usage; pd_die "unknown command: $cmd" ;;
  esac
}

main "$@"
