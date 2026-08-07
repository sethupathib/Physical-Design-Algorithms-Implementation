#!/usr/bin/env bash
# Run the RC Extraction project through PD Job Acceleration (Mode B by default).
#
# There is no "metal fill" project on main of this repo. Closest real PD workload
# available is RC Extraction (branch cursor/rc-extraction-signoff-6f4a).
#
# Usage:
#   ./examples/run_rcx_accelerated.sh          # Mode B (tmp/TMPDIR in RAM)
#   ./examples/run_rcx_accelerated.sh --mode-a # Mode A (workspace in tmpfs; logs on disk)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/.." && pwd)"
RCX_SRC="${REPO_ROOT}/RC Extraction"
SCRIPTS="${ROOT}/scripts"
MODE="b"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode-a|-a) MODE="a"; shift ;;
    --mode-b|-b) MODE="b"; shift ;;
    -h|--help)
      echo "Usage: $0 [--mode-a|--mode-b]"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -x "${RCX_SRC}/rcx_extract" ]] || {
  echo "Building RC Extraction..."
  make -C "$RCX_SRC" -j"$(nproc)"
}

JOB_DURABLE="${ROOT}/examples/rcx_job_durable"
rm -rf "$JOB_DURABLE"
mkdir -p "$JOB_DURABLE"/{inputs,scripts,logs,tmp,outputs}

cp -a "${RCX_SRC}/examples/"*.lay "$JOB_DURABLE/inputs/"
cp -a "${RCX_SRC}/rcx_extract" "$JOB_DURABLE/scripts/rcx_extract"
chmod +x "$JOB_DURABLE/scripts/rcx_extract"

# Synthetic larger layout (more geometry / SPEF I/O)
python3 - <<'PY' > "$JOB_DURABLE/inputs/big_bus.lay"
print("NAME big_bus")
for i in range(40):
    y0 = i * 0.5
    y1 = y0 + 0.14
    net = f"n{i}"
    print(f"METAL M1 {net} w{i}_m1 0.0 {y0:.3f} 80.0 {y1:.3f}")
    print(f"VIA VIA1 {net} v{i} 79.8 {y0:.3f} 80.0 {y1:.3f}")
    print(f"METAL M2 {net} w{i}_m2 80.0 {y0:.3f} 95.0 {y1:.3f}")
    print(f"PIN D{i} {net} M1 O 0.0 {(y0+y1)/2:.3f}")
    print(f"PIN L{i} {net} M2 I 95.0 {(y0+y1)/2:.3f}")
PY

# Job body. Binary is always invoked from durable disk because /dev/shm is
# often mounted noexec (Mode A would otherwise get "Permission denied").
cat > "$JOB_DURABLE/scripts/run_job.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="\$(pwd)"
RCX="${JOB_DURABLE}/scripts/rcx_extract"
LOG="\${ROOT}/logs/rcx_extract.log"
mkdir -p logs tmp outputs

{
  echo "=== RC Extraction accelerated job ==="
  echo "host=\$(hostname)"
  echo "cwd=\${ROOT}"
  echo "rcx=\${RCX}"
  echo "TMPDIR=\${TMPDIR:-unset}"
  echo "tmp_resolved=\$(readlink -f tmp)"
  echo "logs_resolved=\$(readlink -f logs)"
  echo "start=\$(date -Iseconds)"
} | tee "\$LOG"

run_one() {
  local lay="\$1" tag="\$2"
  local spef_tmp="\${ROOT}/tmp/\${tag}.spef"
  local spef_out="\${ROOT}/outputs/\${tag}.spef"
  echo "---- extracting \${lay} ----" | tee -a "\$LOG"
  "\$RCX" "inputs/\${lay}" --spef "\$spef_tmp" 2>&1 | tee -a "\$LOG"
  cp -f "\$spef_tmp" "\$spef_out"
  dd if=/dev/urandom of="\${ROOT}/tmp/\${tag}.scratch.bin" bs=1M count=4 status=none
}

run_one simple_net.lay simple_net
run_one coupled_nets.lay coupled_nets
run_one via_stack.lay via_stack
run_one big_bus.lay big_bus

{
  echo "done=\$(date -Iseconds)"
  echo "outputs:"
  ls -lh outputs/
  echo "tmp (scratch):"
  ls -lh tmp/ | head
} | tee -a "\$LOG"

echo "PASS" > logs/STATUS
EOF
chmod +x "$JOB_DURABLE/scripts/run_job.sh"

# Do not leak TMPDIR from prior manual tests into Mode A.
unset TMPDIR TMP TEMP || true

export PD_DURABLE_ROOT="$JOB_DURABLE"
export PD_JOB_NAME="rcx_extract_accel"
export PD_TOOL_CMD='bash scripts/run_job.sh'
export PD_RAM_PATHS="tmp"
export PD_CHECKPOINT_SECS="${PD_CHECKPOINT_SECS:-2}"
export PD_KEEP_LOGS_ON_DISK=1

echo "============================================"
echo " RC Extraction × PD Job Acceleration"
echo " mode=${MODE}  durable=${JOB_DURABLE}"
echo "============================================"

if [[ "$MODE" == "b" ]]; then
  "${SCRIPTS}/ram_scratch.sh" run
else
  "${SCRIPTS}/run_pd_job.sh"
fi

echo
echo "==== results ===="
echo "STATUS: $(cat "${JOB_DURABLE}/logs/STATUS" 2>/dev/null || echo missing)"
echo "logs on disk:"
ls -la "${JOB_DURABLE}/logs/"
echo "SPEF outputs:"
ls -lh "${JOB_DURABLE}/outputs/"
echo "tmp after job:"
ls -lh "${JOB_DURABLE}/tmp/" 2>/dev/null | head || true
echo "shm leftover:"
ls /dev/shm/pdjobs/"${USER:-user}" 2>/dev/null || echo "(cleaned)"
echo "---- log tail ----"
tail -n 20 "${JOB_DURABLE}/logs/rcx_extract.log"
