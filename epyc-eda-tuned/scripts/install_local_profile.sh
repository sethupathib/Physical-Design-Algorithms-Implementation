#!/usr/bin/env bash
# install_local_profile.sh — install mirrored epyc-eda into /etc/tuned (root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/etc/tuned/epyc-eda

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-run as root: sudo $0" >&2
  exit 2
fi

mkdir -p "$DEST"
cp -a "$ROOT/profiles/epyc-eda/tuned.conf" "$DEST/tuned.conf"
# Ensure parent throughput-performance exists in system tuned
if [[ ! -f /usr/lib/tuned/throughput-performance/tuned.conf ]] && \
   [[ ! -f /usr/lib/tuned/profiles/throughput-performance/tuned.conf ]]; then
  echo "WARNING: system throughput-performance profile not found; epyc-eda include= may fail." >&2
fi
echo "installed=$DEST/tuned.conf"
tuned-adm profile epyc-eda
tuned-adm active
