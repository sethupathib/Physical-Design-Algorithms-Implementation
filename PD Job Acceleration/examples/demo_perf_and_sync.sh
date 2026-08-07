#!/usr/bin/env bash
# Smoke demo: profile a tiny disk-heavy job with perf, then Mode B + durable sync.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../scripts/pd_job_env.sh
source "${ROOT}/scripts/pd_job_env.sh"

JOB="${ROOT}/examples/demo_perf_sync_job"
rm -rf "$JOB"
mkdir -p "$JOB/tmp" "$JOB/logs" "$JOB/outputs"

# Tiny I/O-ish workload: many small files + a fat write.
cat >"$JOB/scripts_run.sh" <<'EOS'
set -euo pipefail
mkdir -p tmp/vault outputs logs
for i in $(seq 1 2000); do
  printf 'cell_%05d delay=%d\n' "$i" "$i" >"tmp/vault/c_${i}.libfrag"
done
# random reads
for i in $(seq 1 5000); do
  n=$(( (i * 7919) % 2000 + 1 ))
  cat "tmp/vault/c_${n}.libfrag" >/dev/null
done
dd if=/dev/urandom of=outputs/eco.db bs=1M count=8 status=none
echo "ok $(date -Iseconds)" | tee logs/job.log
EOS

echo "=== 1) Baseline profile on disk ==="
export PD_DURABLE_ROOT="$JOB"
export PD_JOB_NAME="perf_sync_demo"
export PD_TOOL_CMD='bash ./scripts_run.sh'
(
  cd "$JOB"
  "${ROOT}/scripts/pd_perf_profile.sh" --out "${JOB}/logs/perf_baseline" -- bash ./scripts_run.sh
)
echo
cat "${JOB}/logs/perf_baseline/SUMMARY.txt"

echo
echo "=== 2) Mode B (tmp in RAM) + finalize durability sync ==="
rm -rf "$JOB/tmp" "$JOB/outputs" "$JOB/logs/job.log"
mkdir -p "$JOB/tmp" "$JOB/outputs"
export PD_RAM_PATHS="tmp"
export PD_SYNC_MODE="fs"
export PD_SYNC_AFTER_FINALIZE="1"
export PD_PERF="1"
"${ROOT}/scripts/ram_scratch.sh" run

echo
echo "=== Artifacts ==="
ls -la "${JOB}/.pd_job_status" 2>/dev/null || true
ls -la "${JOB}/logs"/perf_* 2>/dev/null || true
[[ -f "${JOB}/.pd_job_status/sync.log" ]] && { echo "-- sync.log --"; cat "${JOB}/.pd_job_status/sync.log"; }
if [[ -f "${JOB}/logs/perf_perf_sync_demo/SUMMARY.txt" ]]; then
  echo "-- Mode B perf SUMMARY --"
  cat "${JOB}/logs/perf_perf_sync_demo/SUMMARY.txt"
fi
echo "demo done"
