#!/usr/bin/env bash
# Tiny workload for ram_scratch.sh --demo (logs/tmp only; DB stays on disk).
set -euo pipefail
mkdir -p logs tmp
echo "start=$(date -Iseconds)" | tee logs/run.log
for i in $(seq 1 20); do
  echo "log line $i" >> logs/run.log
  dd if=/dev/urandom of="tmp/scratch_${i}.bin" bs=1M count=1 status=none
  sleep 0.05
done
{
  echo "TMPDIR=${TMPDIR:-unset}"
  readlink -f logs
  readlink -f tmp
  echo "done=$(date -Iseconds)"
} >> logs/run.log
