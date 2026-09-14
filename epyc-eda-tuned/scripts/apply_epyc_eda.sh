#!/usr/bin/env bash
# apply_epyc_eda.sh — apply TuneD epyc-eda profile (or dry-run / manual overlay).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-apply}"  # apply | dry-run | show | manual-sysctl

PROFILE_SRC="$ROOT/profiles/epyc-eda/tuned.conf"

usage() {
  cat <<EOF
Usage: $0 [apply|dry-run|show|manual-sysctl]

  apply          sudo tuned-adm profile epyc-eda  (requires tuned + epyc-eda)
  dry-run        print actions without changing the system
  show           print mirrored profile + active tuned state
  manual-sysctl  set only sched_migration_cost_ns=10000 without TuneD
                 (for hosts that lack the epyc-eda profile; still needs write access)
EOF
}

resolve_mig_path() {
  if [[ -e /proc/sys/kernel/sched_migration_cost_ns ]]; then
    echo /proc/sys/kernel/sched_migration_cost_ns
  elif [[ -e /sys/kernel/debug/sched/migration_cost_ns ]]; then
    echo /sys/kernel/debug/sched/migration_cost_ns
  else
    echo ""
  fi
}

case "$MODE" in
  -h|--help) usage; exit 0 ;;
  show)
    echo "=== mirrored profile: $PROFILE_SRC ==="
    cat "$PROFILE_SRC"
    echo
    if command -v tuned-adm >/dev/null 2>&1; then
      echo "=== tuned-adm active ==="
      tuned-adm active || true
      echo "=== tuned-adm list (epyc) ==="
      tuned-adm list 2>/dev/null | grep -i epyc || echo "(no epyc profiles listed)"
    else
      echo "tuned-adm: absent"
    fi
    ;;
  dry-run)
    echo "DRY-RUN would execute:"
    echo "  sudo tuned-adm profile epyc-eda"
    echo "  tuned-adm verify"
    echo "Mirrored profile includes:"
    grep -E 'include=|sched_migration_cost' "$PROFILE_SRC" || true
    ;;
  apply)
    if ! command -v tuned-adm >/dev/null 2>&1; then
      echo "ERROR: tuned-adm not found. Install tuned (RHEL/Alma/Rocky 8.10+) or use: $0 manual-sysctl" >&2
      exit 2
    fi
    if ! tuned-adm list 2>/dev/null | grep -q 'epyc-eda'; then
      echo "ERROR: epyc-eda profile not installed in this tuned package." >&2
      echo "Hint: need tuned >= 2.22.1 with RHEL-27528, or copy $PROFILE_SRC to /etc/tuned/epyc-eda/" >&2
      exit 2
    fi
    sudo tuned-adm profile epyc-eda
    tuned-adm active
    tuned-adm verify || true
    "$ROOT/scripts/dump_sched_knobs.sh" "$ROOT/results/sched_knobs_after_apply.txt"
    ;;
  manual-sysctl)
    PATH_MIG="$(resolve_mig_path)"
    if [[ -z "$PATH_MIG" ]]; then
      echo "ERROR: cannot locate sched_migration_cost_ns (try mounting debugfs as root)" >&2
      exit 2
    fi
    if [[ ! -w "$PATH_MIG" ]]; then
      echo "ERROR: $PATH_MIG not writable (need root)" >&2
      exit 2
    fi
    BEFORE=$(cat "$PATH_MIG")
    echo "$BEFORE" > "$ROOT/results/migration_cost_before.txt"
    echo 10000 | sudo tee "$PATH_MIG" >/dev/null
    AFTER=$(cat "$PATH_MIG")
    echo "migration_cost_before=$BEFORE"
    echo "migration_cost_after=$AFTER"
    echo "migration_cost_path=$PATH_MIG"
    echo "NOTE: manual-sysctl does NOT apply the rest of throughput-performance."
    ;;
  *)
    usage
    exit 2
    ;;
esac
