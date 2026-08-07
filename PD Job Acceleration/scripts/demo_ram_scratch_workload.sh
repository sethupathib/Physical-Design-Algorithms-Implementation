#!/usr/bin/env bash
# Hybrid demo: huge-ish log stays on disk; only small tmp + TMPDIR hit RAM.
set -euo pipefail
mkdir -p logs tmp

# Log on durable disk (do NOT put logs/ in PD_RAM_PATHS — real PD logs can be 20GB+).
{
  echo "start=$(date -Iseconds)"
  echo "note=logs stay on disk; only tmp/TMPDIR use RAM"
} | tee logs/run.log

for i in $(seq 1 20); do
  echo "log line $i (on disk)" >> logs/run.log
  dd if=/dev/urandom of="tmp/scratch_${i}.bin" bs=64K count=1 status=none
  sleep 0.02
done

{
  echo "TMPDIR=${TMPDIR:-unset}"
  echo "logs_resolved=$(readlink -f logs)"
  echo "tmp_resolved=$(readlink -f tmp)"
  echo "done=$(date -Iseconds)"
} >> logs/run.log
