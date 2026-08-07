#!/usr/bin/env bash
# Synthetic Physical Design I/O workload for Mode A demos (no EDA license).
# Writes relative logs/ — with PD_KEEP_LOGS_ON_DISK=1 those hit durable disk
# via symlink, not tmpfs.
set -euo pipefail

WORK_DIR="${1:-.}"
cd "$WORK_DIR"

mkdir -p inputs outputs/reports outputs/dbs logs

echo "[demo] PD workload starting in $(pwd)"

# --- ingest phase (random reads over "libs") ---
echo "[demo] reading design inputs..."
find inputs -type f -print0 2>/dev/null | while IFS= read -r -d '' f; do
  # force page cache / tmpfs read traffic
  dd if="$f" of=/dev/null bs=1M status=none 2>/dev/null || cat "$f" >/dev/null
done

# --- "place" iteration ---
for iter in 1 2 3; do
  echo "[demo] place/opt iteration ${iter}" | tee -a logs/place.log
  # growing "database"
  dd if=/dev/urandom of="outputs/dbs/design_iter${iter}.db" bs=1M count=8 status=none
  # report spam
  {
    echo "ITER ${iter}"
    echo "wns=-0.$((RANDOM % 90))"
    echo "tns=-$((RANDOM % 400)).$((RANDOM % 99))"
    echo "density=0.$((70 + RANDOM % 20))"
  } > "outputs/reports/place_iter${iter}.rpt"
  # tool log chatter
  for i in $(seq 1 50); do
    echo "$(date -Iseconds) OPT step=$i cost=$((RANDOM % 10000))" >> logs/place.log
  done
  sleep 0.3
done

# --- "route" phase ---
echo "[demo] global/detail route..." | tee -a logs/route.log
dd if=/dev/urandom of="outputs/dbs/design_routed.db" bs=1M count=16 status=none
{
  echo "drc_violations=$((RANDOM % 20))"
  echo "wirelength_um=$((500000 + RANDOM % 200000))"
} > outputs/reports/route.rpt
for i in $(seq 1 80); do
  echo "$(date -Iseconds) ROUTE layer=M$((1 + i % 8)) nets=$i" >> logs/route.log
done

# leave a stamp the orchestrator / LinkedIn demo can show
cat > outputs/JOB_SUMMARY.txt <<EOF
demo_pd_workload
host=$(hostname)
cwd=$(pwd)
finished=$(date -Iseconds)
files=$(find . -type f | wc -l)
bytes=$(du -sb . | awk '{print $1}')
EOF

echo "[demo] PD workload complete"
cat outputs/JOB_SUMMARY.txt
