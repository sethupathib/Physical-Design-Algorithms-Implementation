#!/usr/bin/env bash
# Compare an I/O-bound PD-flavored job: baseline disk vs Mode B/A acceleration.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/examples/compare_pd_io_results"
JOB_SRC="${ROOT}/examples/pd_io_bound_job.sh"

# Tunables (override on CLI env)
export N_CELLS="${N_CELLS:-40000}"
export N_LOOKUPS="${N_LOOKUPS:-400000}"
export DB_MB="${DB_MB:-64}"
export N_CHECKPOINTS="${N_CHECKPOINTS:-4}"
export N_REPORTS="${N_REPORTS:-5000}"

mkdir -p "$OUT_DIR"
chmod +x "$JOB_SRC"

prepare_job() {
  local dest="$1"
  rm -rf "$dest"
  mkdir -p "$dest"/{inputs,scripts,logs,tmp,outputs}
  cp -a "$JOB_SRC" "$dest/scripts/pd_io_bound_job.sh"
  chmod +x "$dest/scripts/pd_io_bound_job.sh"
  # seed a tiny marker input on durable disk
  echo "pd_io_bound seed $(date -Iseconds)" > "$dest/inputs/README.txt"
}

time_now() { date +%s.%N; }
elapsed() { python3 -c "print(f'{float('$2')-float('$1'):.3f}')"; }

tool_seconds_from_log() {
  python3 - <<PY
start=done=None
for line in open("$1"):
    line=line.strip()
    if line.startswith("start_epoch="): start=float(line.split("=",1)[1])
    if line.startswith("done_epoch="): done=float(line.split("=",1)[1])
assert start is not None and done is not None
print(f"{done-start:.3f}")
PY
}

drop_caches() {
  sync
  echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
}

run_baseline() {
  local dest="${OUT_DIR}/baseline_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  drop_caches
  echo "---- BASELINE (no acceleration; everything on disk) ----"
  local t0 t1
  t0=$(time_now)
  (
    cd "$dest"
    N_CELLS="$N_CELLS" N_LOOKUPS="$N_LOOKUPS" DB_MB="$DB_MB" \
      N_CHECKPOINTS="$N_CHECKPOINTS" N_REPORTS="$N_REPORTS" \
      bash scripts/pd_io_bound_job.sh >/dev/null
  )
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/baseline.e2e"
  tool_seconds_from_log "$dest/logs/pd_io.log" > "${OUT_DIR}/baseline.tool"
  echo "baseline  e2e=$(cat "${OUT_DIR}/baseline.e2e")s  tool=$(cat "${OUT_DIR}/baseline.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|phase=|start_epoch=|done_epoch=|checksum=' "$dest/logs/pd_io.log" | head -30
  cp -f "$dest/logs/pd_io.log" "${OUT_DIR}/baseline.log"
  cp -f "$dest/outputs/lookup_checksum.txt" "${OUT_DIR}/baseline.checksum"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
}

run_mode_b() {
  local dest="${OUT_DIR}/mode_b_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="pdio_mode_b"
  export PD_TOOL_CMD="env N_CELLS=$N_CELLS N_LOOKUPS=$N_LOOKUPS DB_MB=$DB_MB N_CHECKPOINTS=$N_CHECKPOINTS N_REPORTS=$N_REPORTS bash scripts/pd_io_bound_job.sh"
  export PD_RAM_PATHS="tmp" PD_KEEP_LOGS_ON_DISK=1
  # outputs/ already has deliverables — don't flush regenerable vault/DBs home
  export PD_FLUSH_ON_TEARDOWN=0
  drop_caches
  echo "---- MODE B (tmp/TMPDIR in RAM; logs on disk) ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/ram_scratch.sh" run >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_b.e2e"
  tool_seconds_from_log "$dest/logs/pd_io.log" > "${OUT_DIR}/mode_b.tool"
  echo "mode_b    e2e=$(cat "${OUT_DIR}/mode_b.e2e")s  tool=$(cat "${OUT_DIR}/mode_b.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|phase=|start_epoch=|done_epoch=|checksum=' "$dest/logs/pd_io.log" | head -30
  cp -f "$dest/logs/pd_io.log" "${OUT_DIR}/mode_b.log"
  cp -f "$dest/outputs/lookup_checksum.txt" "${OUT_DIR}/mode_b.checksum"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
}

run_mode_a() {
  local dest="${OUT_DIR}/mode_a_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="pdio_mode_a"
  export PD_TOOL_CMD="env N_CELLS=$N_CELLS N_LOOKUPS=$N_LOOKUPS DB_MB=$DB_MB N_CHECKPOINTS=$N_CHECKPOINTS N_REPORTS=$N_REPORTS bash scripts/pd_io_bound_job.sh"
  export PD_CHECKPOINT_SECS=0 PD_KEEP_LOGS_ON_DISK=1
  export PD_EXCLUDE_FILE="${ROOT}/examples/pd_io_rsync_excludes.txt"
  drop_caches
  echo "---- MODE A (workspace in tmpfs; logs on disk) ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/run_pd_job.sh" >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_a.e2e"
  tool_seconds_from_log "$dest/logs/pd_io.log" > "${OUT_DIR}/mode_a.tool"
  echo "mode_a    e2e=$(cat "${OUT_DIR}/mode_a.e2e")s  tool=$(cat "${OUT_DIR}/mode_a.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|phase=|start_epoch=|done_epoch=|checksum=' "$dest/logs/pd_io.log" | head -30
  cp -f "$dest/logs/pd_io.log" "${OUT_DIR}/mode_a.log"
  cp -f "$dest/outputs/lookup_checksum.txt" "${OUT_DIR}/mode_a.checksum"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
}

summarize() {
  python3 - <<PY | tee "${OUT_DIR}/SUMMARY.txt"
from pathlib import Path
out = Path("$OUT_DIR")
def r(n): return float((out/n).read_text().strip())
rows = [
    ("baseline (disk only)", r("baseline.tool"), r("baseline.e2e")),
    ("Mode B (tmp in RAM)", r("mode_b.tool"), r("mode_b.e2e")),
    ("Mode A (workspace tmpfs)", r("mode_a.tool"), r("mode_a.e2e")),
]
bt, be = rows[0][1], rows[0][2]
print("=" * 72)
print("I/O-bound PD job — WITH vs WITHOUT acceleration")
print(f"cells=${N_CELLS} lookups=${N_LOOKUPS} db=${DB_MB}MB x ${N_CHECKPOINTS} ckpts reports=${N_REPORTS}")
print("=" * 72)
print(f"{'config':<28} {'tool_s':>10} {'vs base':>10} {'e2e_s':>10} {'vs base':>10}")
print("-" * 72)
for name, tool, e2e in rows:
    dt = (bt-tool)/bt*100 if bt else 0
    de = (be-e2e)/be*100 if be else 0
    print(f"{name:<28} {tool:>10.3f} {'—' if name.startswith('baseline') else f'{dt:+.1f}%':>10} {e2e:>10.3f} {'—' if name.startswith('baseline') else f'{de:+.1f}%':>10}")
print("-" * 72)
print("Workload: tiny random liberty lookups + fat DEF/DB checkpoints + report spam.")
print("tool_s = job start→done; e2e_s includes stage/rsync/teardown.")
print("logs/ on disk; hot vault/DB/reports under tmp/ (RAM in Mode B/A).")
print("=" * 72)
PY
  echo
  echo "Functional checksums (liberty lookup stamp):"
  for c in baseline mode_b mode_a; do
    echo "  $c: $(cat "${OUT_DIR}/${c}.checksum")"
  done
  echo
  echo "Where tmp lived:"
  for c in baseline mode_b mode_a; do
    echo -n "  $c: "
    grep '^tmp_resolved=' "${OUT_DIR}/${c}.log"
  done
}

rm -rf /dev/shm/pdjobs/"${USER:-user}" 2>/dev/null || true
echo "PD I/O-bound compare  cells=${N_CELLS} lookups=${N_LOOKUPS} db=${DB_MB}MB x${N_CHECKPOINTS}"
run_baseline
echo
run_mode_b
echo
run_mode_a
echo
summarize
echo
echo "Summary: ${OUT_DIR}/SUMMARY.txt"
