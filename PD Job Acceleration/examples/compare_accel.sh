#!/usr/bin/env bash
# Compare the same RC Extraction job: baseline (disk only) vs accelerated.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/.." && pwd)"
RCX_SRC="${REPO_ROOT}/RC Extraction"
OUT_DIR="${ROOT}/examples/compare_results"
SCRATCH_MB="${SCRATCH_MB:-32}"
PASSES="${PASSES:-4}"
OUTER="${OUTER:-3}"
mkdir -p "$OUT_DIR"

[[ -x "${RCX_SRC}/rcx_extract" ]] || make -C "$RCX_SRC" -j"$(nproc)"

write_run_job() {
  local dest="$1"
  local rcx_bin="${dest}/scripts/rcx_extract"
  # Quoted heredoc so nothing expands early; inject values with envsubst-like sed.
  cat > "${dest}/scripts/run_job.sh" <<'JOB'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
RCX="__RCX_BIN__"
LOG="${ROOT}/logs/rcx_extract.log"
SCRATCH_MB=__SCRATCH_MB__
PASSES=__PASSES__
OUTER=__OUTER__
mkdir -p logs tmp outputs
{
  echo "cwd=${ROOT}"
  echo "TMPDIR=${TMPDIR:-unset}"
  echo "tmp_resolved=$(readlink -f tmp)"
  echo "logs_resolved=$(readlink -f logs)"
  echo "start_epoch=$(date +%s.%N)"
  echo "start=$(date -Iseconds)"
} | tee "$LOG"

run_one() {
  local lay="$1" tag="$2" p
  for p in $(seq 1 "$PASSES"); do
    local spef_tmp="${ROOT}/tmp/${tag}_p${p}.spef"
    "$RCX" "inputs/${lay}" --spef "$spef_tmp" >>"$LOG" 2>&1
    dd if=/dev/urandom of="${ROOT}/tmp/${tag}_p${p}.bin" bs=1M count="$SCRATCH_MB" status=none
    dd if="${ROOT}/tmp/${tag}_p${p}.bin" of=/dev/null bs=1M status=none
  done
  cp -f "${ROOT}/tmp/${tag}_p${PASSES}.spef" "${ROOT}/outputs/${tag}.spef"
}

for _ in $(seq 1 "$OUTER"); do
  run_one simple_net.lay simple_net
  run_one coupled_nets.lay coupled_nets
  run_one via_stack.lay via_stack
  run_one big_bus.lay big_bus
done

{
  echo "done_epoch=$(date +%s.%N)"
  echo "done=$(date -Iseconds)"
} | tee -a "$LOG"
echo PASS > logs/STATUS
du -sh tmp logs outputs >>"$LOG"
JOB
  sed -i \
    -e "s|__RCX_BIN__|${rcx_bin}|g" \
    -e "s|__SCRATCH_MB__|${SCRATCH_MB}|g" \
    -e "s|__PASSES__|${PASSES}|g" \
    -e "s|__OUTER__|${OUTER}|g" \
    "${dest}/scripts/run_job.sh"
  chmod +x "${dest}/scripts/run_job.sh"
}

prepare_job() {
  local dest="$1"
  rm -rf "$dest"
  mkdir -p "$dest"/{inputs,scripts,logs,tmp,outputs}
  cp -a "${RCX_SRC}/examples/"*.lay "$dest/inputs/"
  cp -a "${RCX_SRC}/rcx_extract" "$dest/scripts/rcx_extract"
  chmod +x "$dest/scripts/rcx_extract"
  python3 - <<'PY' > "$dest/inputs/big_bus.lay"
print("NAME big_bus")
for i in range(120):
    y0 = i * 0.5
    y1 = y0 + 0.14
    net = f"n{i}"
    print(f"METAL M1 {net} w{i}_m1 0.0 {y0:.3f} 160.0 {y1:.3f}")
    print(f"VIA VIA1 {net} v{i} 159.8 {y0:.3f} 160.0 {y1:.3f}")
    print(f"METAL M2 {net} w{i}_m2 160.0 {y0:.3f} 200.0 {y1:.3f}")
    print(f"PIN D{i} {net} M1 O 0.0 {(y0+y1)/2:.3f}")
    print(f"PIN L{i} {net} M2 I 200.0 {(y0+y1)/2:.3f}")
PY
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
assert start is not None and done is not None, "missing epoch stamps in $1"
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
  tool_seconds_from_log "$dest/logs/rcx_extract.log" > "${OUT_DIR}/baseline.tool"
  echo "baseline  e2e=$(cat "${OUT_DIR}/baseline.e2e")s  tool=$(cat "${OUT_DIR}/baseline.tool")s"
  echo "  tmp=$(readlink -f "$dest/tmp")"
  echo "  logs=$(readlink -f "$dest/logs")"
  grep -E 'tmp_resolved=|logs_resolved=|start_epoch=|done_epoch=' "$dest/logs/rcx_extract.log"
  cp -f "$dest/logs/rcx_extract.log" "${OUT_DIR}/baseline.log"
  du -sh "$dest/tmp" "$dest/outputs"
}

run_mode_b() {
  local dest="${OUT_DIR}/mode_b_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="compare_mode_b"
  export PD_TOOL_CMD='bash scripts/run_job.sh' PD_RAM_PATHS="tmp" PD_KEEP_LOGS_ON_DISK=1
  sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
  echo "---- MODE B (tmp/TMPDIR in RAM; logs on disk) ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/ram_scratch.sh" run >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_b.e2e"
  tool_seconds_from_log "$dest/logs/rcx_extract.log" > "${OUT_DIR}/mode_b.tool"
  echo "mode_b    e2e=$(cat "${OUT_DIR}/mode_b.e2e")s  tool=$(cat "${OUT_DIR}/mode_b.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|start_epoch=|done_epoch=' "$dest/logs/rcx_extract.log"
  cp -f "$dest/logs/rcx_extract.log" "${OUT_DIR}/mode_b.log"
  du -sh "$dest/tmp" "$dest/outputs"
}

run_mode_a() {
  local dest="${OUT_DIR}/mode_a_job"
  prepare_job "$dest"
  unset TMPDIR TMP TEMP || true
  export PD_DURABLE_ROOT="$dest" PD_JOB_NAME="compare_mode_a"
  export PD_TOOL_CMD='bash scripts/run_job.sh' PD_CHECKPOINT_SECS=0 PD_KEEP_LOGS_ON_DISK=1
  sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
  echo "---- MODE A (workspace in tmpfs; logs on disk) ----"
  local t0 t1
  t0=$(time_now)
  "${ROOT}/scripts/run_pd_job.sh" >/dev/null
  t1=$(time_now)
  elapsed "$t0" "$t1" > "${OUT_DIR}/mode_a.e2e"
  tool_seconds_from_log "$dest/logs/rcx_extract.log" > "${OUT_DIR}/mode_a.tool"
  echo "mode_a    e2e=$(cat "${OUT_DIR}/mode_a.e2e")s  tool=$(cat "${OUT_DIR}/mode_a.tool")s"
  grep -E 'tmp_resolved=|logs_resolved=|start_epoch=|done_epoch=' "$dest/logs/rcx_extract.log"
  cp -f "$dest/logs/rcx_extract.log" "${OUT_DIR}/mode_a.log"
  du -sh "$dest/tmp" "$dest/outputs"
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
print("RC Extraction — WITH vs WITHOUT acceleration")
print(f"scratch=${SCRATCH_MB}MiB/pass  passes=${PASSES}  outer=${OUTER}")
print("=" * 72)
print(f"{'config':<28} {'tool_s':>10} {'vs base':>10} {'e2e_s':>10} {'vs base':>10}")
print("-" * 72)
for name, tool, e2e in rows:
    dt = (bt-tool)/bt*100 if bt else 0
    de = (be-e2e)/be*100 if be else 0
    print(f"{name:<28} {tool:>10.3f} {'—' if name.startswith('baseline') else f'{dt:+.1f}%':>10} {e2e:>10.3f} {'—' if name.startswith('baseline') else f'{de:+.1f}%':>10}")
print("-" * 72)
print("tool_s = job start→done (compute + scratch I/O only)")
print("e2e_s  = includes stage / rsync materialize / teardown")
print("SPEF checksums should match (same functional results).")
print("This host disk is local/fast; NFS usually amplifies tool_s wins.")
print("=" * 72)
PY
  echo
  echo "SPEF checksums (same results?):"
  (
    cd "$OUT_DIR"
    for d in baseline_job mode_b_job mode_a_job; do
      echo "-- $d --"
      sha256sum "$d"/outputs/*.spef | awk '{print $1, $2}' | sort -k2
    done
  )
}

rm -rf /dev/shm/pdjobs/"${USER:-user}" 2>/dev/null || true
run_baseline
echo
run_mode_b
echo
run_mode_a
echo
summarize
echo
echo "Summary file: ${OUT_DIR}/SUMMARY.txt"
