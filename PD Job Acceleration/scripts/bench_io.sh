#!/usr/bin/env bash
# Microbench: sequential write/read on disk vs tmpfs (/dev/shm).
# Useful numbers to quote in a LinkedIn post (same host, same size).
set -euo pipefail

SIZE_MB="${1:-256}"
DISK_DIR="${BENCH_DISK_DIR:-$(pwd)/.bench_disk}"
RAM_DIR="${BENCH_RAM_DIR:-/dev/shm/pd_bench_${USER:-user}}"

mkdir -p "$DISK_DIR" "$RAM_DIR"

bench_one() {
  local label="$1" dir="$2"
  local f="${dir}/blob_${SIZE_MB}m.bin"
  local write_s read_s

  rm -f "$f"
  sync
  write_s=$(
    TIMEFORMAT='%R'
    { time dd if=/dev/zero of="$f" bs=1M count="$SIZE_MB" conv=fdatasync status=none; } 2>&1
  )
  read_s=$(
    TIMEFORMAT='%R'
    { time dd if="$f" of=/dev/null bs=1M status=none; } 2>&1
  )
  local mib_w mib_r
  mib_w=$(awk -v s="$write_s" -v n="$SIZE_MB" 'BEGIN{ if (s+0>0) printf "%.1f", n/s; else print "inf" }')
  mib_r=$(awk -v s="$read_s" -v n="$SIZE_MB" 'BEGIN{ if (s+0>0) printf "%.1f", n/s; else print "inf" }')
  printf '%-8s  write %6ss (%7s MiB/s)  read %6ss (%7s MiB/s)  path=%s\n' \
    "$label" "$write_s" "$mib_w" "$read_s" "$mib_r" "$dir"
  rm -f "$f"
}

echo "PD I/O microbench: ${SIZE_MB} MiB sequential"
echo "host=$(hostname)  date=$(date -Iseconds)"
echo

bench_one "disk" "$DISK_DIR"
bench_one "tmpfs" "$RAM_DIR"

echo
echo "Note: wall-clock PD wins also come from fewer NFS round-trips on tiny random I/O,"
echo "not only from raw sequential bandwidth."

rmdir "$RAM_DIR" 2>/dev/null || true
