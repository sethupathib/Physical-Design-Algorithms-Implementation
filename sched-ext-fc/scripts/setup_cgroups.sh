#!/usr/bin/env bash
# Setup / tear down cgroup v2 layer trees for FC-farm policy experiments.
# Requires root. Maps to scx_layered "layers" (see configs/).
set -euo pipefail

ROOT="${CG_ROOT:-/sys/fs/cgroup/sched_ext_fc}"
ACTION="${1:-}"

usage() {
  echo "Usage: $0 {create-flat|create-layers|create-protect|destroy|status}" >&2
  exit 1
}

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "need root (sudo) for cgroup ops" >&2
    exit 1
  fi
}

enable_cpu() {
  # Ensure cpu controller is delegated on the parent we create under.
  if ! grep -qw cpu /sys/fs/cgroup/cgroup.controllers; then
    echo "cpu controller not in cgroup.controllers" >&2
    exit 1
  fi
  local cur
  cur="$(cat /sys/fs/cgroup/cgroup.subtree_control || true)"
  if ! grep -qw cpu <<<"$cur"; then
    echo "+cpu" > /sys/fs/cgroup/cgroup.subtree_control
  fi
}

destroy_tree() {
  need_root
  if [[ ! -d "$ROOT" ]]; then
    return 0
  fi
  # Kill leftover procs if any, then remove children then root.
  for d in "$ROOT"/*; do
    [[ -d "$d" ]] || continue
    if [[ -f "$d/cgroup.procs" ]]; then
      while read -r pid; do
        [[ -n "$pid" ]] || continue
        kill -TERM "$pid" 2>/dev/null || true
      done < "$d/cgroup.procs" || true
    fi
  done
  sleep 0.2
  for d in "$ROOT"/*; do
    [[ -d "$d" ]] || continue
    rmdir "$d" 2>/dev/null || true
  done
  rmdir "$ROOT" 2>/dev/null || true
}

create_base() {
  need_root
  enable_cpu
  destroy_tree
  mkdir -p "$ROOT"
  # Delegate cpu to children of ROOT.
  echo "+cpu" > "$ROOT/cgroup.subtree_control"
}

set_weight() {
  local path="$1" weight="$2"
  echo "$weight" > "$path/cpu.weight"
}

case "$ACTION" in
  create-flat)
    create_base
    mkdir -p "$ROOT/all"
    set_weight "$ROOT/all" 100
    echo "flat: $ROOT/all weight=100"
    ;;
  create-layers)
    # 5:1 interactive:batch — portable proxy for scx_layered weights.
    create_base
    mkdir -p "$ROOT/interactive" "$ROOT/batch"
    set_weight "$ROOT/interactive" 500
    set_weight "$ROOT/batch" 100
    echo "layers: interactive=500 batch=100"
    ;;
  create-protect)
    # Stronger interactive bias + batch cpu.max ceiling (50% of one CPU * n?).
    # cpu.max = $MAX $PERIOD — here batch capped to 200000/100000 = 2 CPUs worth
    # on a 4-CPU box when sharing with interactive.
    create_base
    mkdir -p "$ROOT/interactive" "$ROOT/batch"
    set_weight "$ROOT/interactive" 1000
    set_weight "$ROOT/batch" 50
    # Cap batch to ~2 CPUs of runtime per 100ms period (leaves headroom).
    echo "200000 100000" > "$ROOT/batch/cpu.max"
    echo "protect: interactive=1000 batch=50 cpu.max=200000/100000"
    ;;
  destroy)
    destroy_tree
    echo "destroyed $ROOT"
    ;;
  status)
    if [[ -d "$ROOT" ]]; then
      find "$ROOT" -type f \( -name cpu.weight -o -name cpu.max -o -name cgroup.procs \) -printf '%p: ' -exec cat {} \;
    else
      echo "no tree at $ROOT"
    fi
    ;;
  *)
    usage
    ;;
esac
