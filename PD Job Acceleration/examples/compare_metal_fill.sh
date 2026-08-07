#!/usr/bin/env bash
# Compare gpu_metal_fill WITH vs WITHOUT tmpfs/rsync acceleration.
# Same exercise as compare_accel.sh, but for the BEOL metal-fill job.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/.." && pwd)"
FILL_SRC="${REPO_ROOT}/gpu_metal_fill"
OUT_DIR="${ROOT}/examples/compare_metal_fill_results"
SM_GRID="${SM_GRID:-4}"          # make_gpu_block -n
OUTER="${OUTER:-2}"              # repeat fill this many times
mkdir -p "$OUT_DIR"

[[ -x "${FILL_SRC}/build/run_fill" && -x "${FILL_SRC}/build/make_gpu_block" ]] || {
  echo "Building gpu_metal_fill..."
  make -C "$FILL_SRC" -j"$(nproc)"
}

write_run_job() {
  local dest="$1"
  cat > "${dest}/scripts/run_job.sh" <<'JOB'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
MAKE_BLOCK="__MAKE_BLOCK__"
RUN_FILL="__RUN_FILL__"
GDSINFO="__GDSINFO__"
SM_GRID=__SM_GRID__
OUTER=__OUTER__
LOG="${ROOT}/logs/metal_fill.log"
mkdir -p logs tmp outputs
{
  echo "cwd=${ROOT}"
  echo "TMPDIR=${TMPDIR:-unset}"
  echo "tmp_resolved=$(readlink -f tmp)"
  echo "logs_resolved=$(readlink -f logs)"
  echo "start_epoch=$(date +%s.%N)"
  echo "start=$(date -Iseconds)"
} | tee "$LOG"

# Generate input once into durable inputs/ (if missing) — generation is not timed
# as the "fill job"; we time the fill loop. For fairness, pre-generated in prepare.

for i in $(seq 1 "$OUTER"); do
  echo "==== fill pass $i/$OUTER ====" | tee -a "$LOG"
  # Write large filled GDS into tmp/ (hot path), report into logs/ (disk)
  "$RUN_FILL" \
      -i "${ROOT}/inputs/gpu_block.gds" \
      -o "${ROOT}/tmp/gpu_filled_p${i}.gds" \
      -r "${ROOT}/logs/report_p${i}.txt" \
      2>&1 | tee -a "$LOG"
  # Scratch churn: copy/read the filled GDS in tmp
  dd if="${ROOT}/tmp/gpu_filled_p${i}.gds" of="${ROOT}/tmp/gpu_filled_p${i}.copy" bs=4M status=none
  dd if="${ROOT}/tmp/gpu_filled_p${i}.copy" of=/dev/null bs=4M status=none
done

# Final deliverables on durable outputs/
cp -f "${ROOT}/tmp/gpu_filled_p${OUTER}.gds" "${ROOT}/outputs/gpu_filled.gds"
cp -f "${ROOT}/logs/report_p${OUTER}.txt" "${ROOT}/outputs/report.txt"
"$GDSINFO" "${ROOT}/inputs/gpu_block.gds" "${ROOT}/outputs/gpu_filled.gds" \
  > "${ROOT}/outputs/gdsinfo.txt" 2>&1 || true

{
  echo "done_epoch=$(date +%s.%N)"
  echo "done=$(date -Iseconds)"
  ls -lh outputs/ tmp/*.gds 2>/dev/null | head -20
} | tee -a "$LOG"
echo PASS > logs/STATUS
du -sh tmp logs outputs >>"$LOG"
JOB
  sed -i \
    -e "s|__MAKE_BLOCK__|${dest}/scripts/make_gpu_block|g" \
    -e "s|__RUN_FILL__|${dest}/scripts/run_fill|g" \
    -e "s|__GDSINFO__|${dest}/scripts/gdsinfo|g" \
    -e "s|__SM_GRID__|${SM_GRID}|g" \
    -e "s|__OUTER__|${OUTER}|g" \
    "${dest}/scripts/run_job.sh"
  chmod +x "${dest}/scripts/run_job.sh"
}

prepare_job() {
  local dest="$1"
  rm -rf "$dest"
  mkdir -p "$dest"/{inputs,scripts,logs,tmp,outputs}

  # Binaries on durable disk ( /dev/shm is often noexec )
  cp -a "${FILL_SRC}/build/make_gpu_block" \
        "${FILL_SRC}/build/run_fill" \
        "${FILL_SRC}/build/gdsinfo" \
        "$dest/scripts/"
  chmod +x "$dest/scripts/"*

  echo "Generating gpu_block.gds (SM_GRID=${SM_GRID}) into ${dest}/inputs ..."
  "${dest}/scripts/make_gpu_block" -o "${dest}/inputs/gpu_block.gds" -n "$SM_GRID"
  ls -lh "${dest}/inputs/gpu_block.gds"

  write_run_job "$dest"
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
assert start is not None and done is not None, "missing epoch stamps"
print(f"{done-start:.3f}")
PY
}

run_baseline() {
  local dest="${OUT_DIR}/baseline_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
  echo "---- BASELINE (no acceleration; everything on disk) ----"
  local t0 t1
  t0=$(time_now)
  ( cd "$dest" && bash scripts/run_job.sh >/dev/null )
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/baseline.e2e"
  tool_seconds_from_log "$dest/logs/metal_fill.log" > "${OUT_DIR}/baseline.tool"
  echo "baseline  e2e=$(cat "${OUT_DIR}/baseline.e2e")s  tool=$(cat "${OUT_DIR}/baseline.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|start_epoch=|done_epoch=|total time' "$dest/logs/metal_fill.log" | head -20
  cp -f "$dest/logs/metal_fill.log" "${OUT_DIR}/baseline.log"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
  ls -lh "$dest/outputs/"
}

run_mode_b() {
  local dest="${OUT_DIR}/mode_b_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="mfill_mode_b"
  export PD_TOOL_CMD='bash scripts/run_job.sh' PD_RAM_PATHS="tmp" PD_KEEP_LOGS_ON_DISK=1
  sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
  echo "---- MODE B (tmp/TMPDIR in RAM; logs on disk) ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/ram_scratch.sh" run >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_b.e2e"
  tool_seconds_from_log "$dest/logs/metal_fill.log" > "${OUT_DIR}/mode_b.tool"
  echo "mode_b    e2e=$(cat "${OUT_DIR}/mode_b.e2e")s  tool=$(cat "${OUT_DIR}/mode_b.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|start_epoch=|done_epoch=|total time' "$dest/logs/metal_fill.log" | head -20
  cp -f "$dest/logs/metal_fill.log" "${OUT_DIR}/mode_b.log"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
  ls -lh "$dest/outputs/"
}

run_mode_a() {
  local dest="${OUT_DIR}/mode_a_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="mfill_mode_a"
  export PD_TOOL_CMD='bash scripts/run_job.sh' PD_CHECKPOINT_SECS=0 PD_KEEP_LOGS_ON_DISK=1
  sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
  echo "---- MODE A (workspace in tmpfs; logs on disk) ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/run_pd_job.sh" >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_a.e2e"
  tool_seconds_from_log "$dest/logs/metal_fill.log" > "${OUT_DIR}/mode_a.tool"
  echo "mode_a    e2e=$(cat "${OUT_DIR}/mode_a.e2e")s  tool=$(cat "${OUT_DIR}/mode_a.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|start_epoch=|done_epoch=|total time' "$dest/logs/metal_fill.log" | head -20
  cp -f "$dest/logs/metal_fill.log" "${OUT_DIR}/mode_a.log"
  du -sh "$dest/tmp" "$dest/outputs" "$dest/logs"
  ls -lh "$dest/outputs/"
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
print("gpu_metal_fill — WITH vs WITHOUT acceleration")
print(f"SM_GRID=${SM_GRID}  OUTER=${OUTER}  (filled GDS written via tmp/)")
print("=" * 72)
print(f"{'config':<28} {'tool_s':>10} {'vs base':>10} {'e2e_s':>10} {'vs base':>10}")
print("-" * 72)
for name, tool, e2e in rows:
    dt = (bt-tool)/bt*100 if bt else 0
    de = (be-e2e)/be*100 if be else 0
    print(f"{name:<28} {tool:>10.3f} {'—' if name.startswith('baseline') else f'{dt:+.1f}%':>10} {e2e:>10.3f} {'—' if name.startswith('baseline') else f'{de:+.1f}%':>10}")
print("-" * 72)
print("tool_s = fill start→done (includes large GDS write/read in tmp/)")
print("e2e_s  = includes stage / rsync materialize / teardown")
print("logs/ always on disk; fat filled.gds goes through tmp/ first.")
print("Note: gpu_metal_fill is mostly CPU-bound (OpenMP fill); I/O accel helps")
print("the GDS write/read slice. On NFS that slice is usually a larger fraction.")
print("Filled GDS checksums should match; report.txt may differ (timers).")
print("=" * 72)
PY
  echo
  echo "Output GDS checksums (same results?):"
  (
    cd "$OUT_DIR"
    for d in baseline_job mode_b_job mode_a_job; do
      echo "-- $d --"
      sha256sum "$d"/outputs/gpu_filled.gds "$d"/outputs/report.txt 2>/dev/null
      ls -lh "$d"/outputs/gpu_filled.gds
    done
  )
}

rm -rf /dev/shm/pdjobs/"${USER:-user}" 2>/dev/null || true
echo "Metal fill acceleration compare  SM_GRID=${SM_GRID} OUTER=${OUTER}"
run_baseline
echo
run_mode_b
echo
run_mode_a
echo
summarize
echo
echo "Summary: ${OUT_DIR}/SUMMARY.txt"
