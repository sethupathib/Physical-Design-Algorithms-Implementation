#!/usr/bin/env bash
# Monumental before/after: PD farm I/O suite
#   baseline  = durable disk + emulated NFS RTT on every tiny op
#   Mode B/A  = same work on tmpfs with nfs-us=0
#
# This is the real-world gap the pattern targets (NFS metadata vs RAM),
# not local-SSD vs tmpfs (which is often modest).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/examples/compare_pd_farm_io_results"
SUITE="${ROOT}/examples/pd_farm_io_suite.py"

# Emulated NFS per-op RTT for the baseline path only (microseconds).
NFS_US="${NFS_US:-400}"
CELLS="${CELLS:-20000}"
LOOKUPS="${LOOKUPS:-150000}"
NETS="${NETS:-15000}"
CHECKPOINTS="${CHECKPOINTS:-3}"
DB_MB="${DB_MB:-16}"
REPORTS="${REPORTS:-3000}"

mkdir -p "$OUT_DIR"
chmod +x "$SUITE"

prepare_job() {
  local dest="$1"
  rm -rf "$dest"
  mkdir -p "$dest"/{inputs,scripts,logs,tmp,outputs}
  cp -a "$SUITE" "$dest/scripts/pd_farm_io_suite.py"
  echo "pd farm io suite" > "$dest/inputs/README.txt"
}

time_now() { date +%s.%N; }
elapsed() { python3 -c "print(f'{float('$2')-float('$1'):.3f}')"; }

tool_seconds_from_log() {
  python3 - <<PY
start=done=None
for raw in open("$1"):
    for part in raw.strip().split():
        if part.startswith("start_epoch="):
            start=float(part.split("=",1)[1])
        if part.startswith("done_epoch="):
            done=float(part.split("=",1)[1])
assert start is not None and done is not None, "missing epoch stamps"
print(f"{done-start:.3f}")
PY
}

drop_caches() { sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true; }

run_cmd() {
  local nfs="$1"
  python3 scripts/pd_farm_io_suite.py \
    --root . \
    --nfs-us "$nfs" \
    --cells "$CELLS" \
    --lookups "$LOOKUPS" \
    --nets "$NETS" \
    --checkpoints "$CHECKPOINTS" \
    --db-mb "$DB_MB" \
    --reports "$REPORTS"
}

run_baseline() {
  local dest="${OUT_DIR}/baseline_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  drop_caches
  echo "---- BASELINE: disk + emulated NFS RTT (${NFS_US}µs/op) ----"
  local t0 t1
  t0=$(time_now)
  ( cd "$dest" && run_cmd "$NFS_US" >/dev/null )
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/baseline.e2e"
  tool_seconds_from_log "$dest/logs/pd_farm_io.log" > "${OUT_DIR}/baseline.tool"
  echo "baseline  e2e=$(cat "${OUT_DIR}/baseline.e2e")s  tool=$(cat "${OUT_DIR}/baseline.tool")s"
  grep -E 'phase=|nfs_us=|tmp_resolved=|checksum=|ops=' "$dest/logs/pd_farm_io.log" | head -40
  cp -f "$dest/logs/pd_farm_io.log" "${OUT_DIR}/baseline.log"
  cp -f "$dest/outputs/lookup_checksum.txt" "${OUT_DIR}/baseline.checksum"
  cp -f "$dest/outputs/JOB_SUMMARY.txt" "${OUT_DIR}/baseline.summary"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
}

run_mode_b() {
  local dest="${OUT_DIR}/mode_b_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="farmio_mode_b"
  export PD_RAM_PATHS="tmp" PD_KEEP_LOGS_ON_DISK=1 PD_FLUSH_ON_TEARDOWN=0
  # Accelerated path: no NFS tax (tmpfs is local RAM)
  export PD_TOOL_CMD="python3 scripts/pd_farm_io_suite.py --root . --nfs-us 0 --cells $CELLS --lookups $LOOKUPS --nets $NETS --checkpoints $CHECKPOINTS --db-mb $DB_MB --reports $REPORTS"
  drop_caches
  echo "---- MODE B: tmp in RAM, nfs-us=0 ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/ram_scratch.sh" run >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_b.e2e"
  tool_seconds_from_log "$dest/logs/pd_farm_io.log" > "${OUT_DIR}/mode_b.tool"
  echo "mode_b    e2e=$(cat "${OUT_DIR}/mode_b.e2e")s  tool=$(cat "${OUT_DIR}/mode_b.tool")s"
  grep -E 'phase=|nfs_us=|tmp_resolved=|checksum=|ops=' "$dest/logs/pd_farm_io.log" | head -40
  cp -f "$dest/logs/pd_farm_io.log" "${OUT_DIR}/mode_b.log"
  cp -f "$dest/outputs/lookup_checksum.txt" "${OUT_DIR}/mode_b.checksum"
  cp -f "$dest/outputs/JOB_SUMMARY.txt" "${OUT_DIR}/mode_b.summary"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
}

run_mode_a() {
  local dest="${OUT_DIR}/mode_a_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="farmio_mode_a"
  export PD_CHECKPOINT_SECS=0 PD_KEEP_LOGS_ON_DISK=1
  export PD_EXCLUDE_FILE="${ROOT}/examples/pd_io_rsync_excludes.txt"
  export PD_TOOL_CMD="python3 scripts/pd_farm_io_suite.py --root . --nfs-us 0 --cells $CELLS --lookups $LOOKUPS --nets $NETS --checkpoints $CHECKPOINTS --db-mb $DB_MB --reports $REPORTS"
  drop_caches
  echo "---- MODE A: workspace tmpfs, nfs-us=0 ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/run_pd_job.sh" >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_a.e2e"
  tool_seconds_from_log "$dest/logs/pd_farm_io.log" > "${OUT_DIR}/mode_a.tool"
  echo "mode_a    e2e=$(cat "${OUT_DIR}/mode_a.e2e")s  tool=$(cat "${OUT_DIR}/mode_a.tool")s"
  grep -E 'phase=|nfs_us=|tmp_resolved=|checksum=|ops=' "$dest/logs/pd_farm_io.log" | head -40
  cp -f "$dest/logs/pd_farm_io.log" "${OUT_DIR}/mode_a.log"
  cp -f "$dest/outputs/lookup_checksum.txt" "${OUT_DIR}/mode_a.checksum"
  cp -f "$dest/outputs/JOB_SUMMARY.txt" "${OUT_DIR}/mode_a.summary"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
}

summarize() {
  python3 - <<PY | tee "${OUT_DIR}/SUMMARY.txt"
from pathlib import Path
out = Path("$OUT_DIR")
def r(n): return float((out/n).read_text().strip())
rows = [
    ("baseline (disk+NFS RTT)", r("baseline.tool"), r("baseline.e2e")),
    ("Mode B (tmpfs, no RTT)", r("mode_b.tool"), r("mode_b.e2e")),
    ("Mode A (tmpfs, no RTT)", r("mode_a.tool"), r("mode_a.e2e")),
]
bt, be = rows[0][1], rows[0][2]
print("=" * 76)
print("PD FARM I/O SUITE — monumental with vs without acceleration")
print(f"NFS_US=${NFS_US}µs/op  cells=${CELLS} lookups=${LOOKUPS} nets=${NETS}")
print(f"checkpoints=${CHECKPOINTS}x${DB_MB}MB  reports=${REPORTS}")
print("=" * 76)
print(f"{'config':<28} {'tool_s':>10} {'speedup':>10} {'e2e_s':>10} {'speedup':>10}")
print("-" * 76)
for name, tool, e2e in rows:
    st = (bt/tool) if tool else 0
    se = (be/e2e) if e2e else 0
    if name.startswith("baseline"):
        print(f"{name:<28} {tool:>10.3f} {'—':>10} {e2e:>10.3f} {'—':>10}")
    else:
        print(f"{name:<28} {tool:>10.3f} {st:>9.1f}x {e2e:>10.3f} {se:>9.1f}x")
print("-" * 76)
print("Phases: liberty vault → random lib lookups → SPEF shard merge →")
print("         ECO checkpoints → report spam")
print("Baseline adds emulated NFS metadata RTT on every tiny op (farm model).")
print("Mode B/A run identical work on tmpfs with nfs-us=0 (RAM model).")
print("Checksums must match. logs/ stay on disk; hot data under tmp/.")
print("=" * 76)
PY
  echo
  echo "Checksums:"
  for c in baseline mode_b mode_a; do
    echo "  $c: $(cat "${OUT_DIR}/${c}.checksum")  ops/bytes: $(tr '\n' ' ' < "${OUT_DIR}/${c}.summary")"
  done
  echo
  echo "tmp_resolved:"
  for c in baseline mode_b mode_a; do
    echo -n "  $c: "
    grep -o 'tmp_resolved=[^ ]*' "${OUT_DIR}/${c}.log" | head -1
  done
}

rm -rf /dev/shm/pdjobs/"${USER:-user}" 2>/dev/null || true
echo "PD farm I/O monumental compare  NFS_US=${NFS_US}µs"
run_baseline
echo
run_mode_b
echo
run_mode_a
echo
summarize
echo
echo "Summary: ${OUT_DIR}/SUMMARY.txt"
