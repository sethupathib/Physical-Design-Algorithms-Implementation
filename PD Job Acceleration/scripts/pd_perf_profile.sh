#!/usr/bin/env bash
# Profile a PD tool command with perf (+ GNU time fallback) to decide whether
# tmpfs/rsync acceleration is worth applying, and where the bottleneck is.
#
# Usage:
#   pd_perf_profile.sh [--out DIR] -- <command...>
#   PD_TOOL_CMD='...' pd_perf_profile.sh [--out DIR]
#
# Env:
#   PD_PERF_RECORD=1   also run `perf record -g` (needs writable out dir)
#   PD_PERF_BIN=path   force a specific perf binary
#   PD_PERF_EVENTS=... comma-separated perf events (optional override)
#
# Exit code: the wrapped command's exit code.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd_job_env.sh
source "${SCRIPT_DIR}/pd_job_env.sh"

usage() {
  cat <<'EOF'
Usage: pd_perf_profile.sh [--out DIR] [--record] -- <command...>
       PD_TOOL_CMD='innovus ...' pd_perf_profile.sh [--out DIR]

Collects:
  - wall / user / sys time (GNU time or bash SECONDS)
  - perf stat counters when a working perf is available
  - a short I/O-vs-CPU classification + Mode A/B recommendation

This does not accelerate the job by itself — it tells you whether tmpfs+rsync
will help, and what to measure next.
EOF
}

OUT_DIR=""
DO_RECORD=0
CMD=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT_DIR="${2:-}"; shift 2 ;;
    --record) DO_RECORD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; CMD=("$@"); break ;;
    *)
      # Allow: pd_perf_profile.sh cmd args...
      CMD=("$@")
      break
      ;;
  esac
done

if [[ ${#CMD[@]} -eq 0 ]]; then
  if [[ -n "${PD_TOOL_CMD:-}" ]]; then
    CMD=(bash -c "$PD_TOOL_CMD")
  else
    usage
    pd_die "no command provided (use -- cmd, or set PD_TOOL_CMD)"
  fi
fi

[[ "${PD_PERF_RECORD:-0}" == "1" ]] && DO_RECORD=1

if [[ -z "$OUT_DIR" ]]; then
  if [[ -n "${PD_DURABLE_ROOT:-}" ]]; then
    OUT_DIR="${PD_DURABLE_ROOT}/logs/perf_${PD_JOB_NAME:-profile}"
  else
    OUT_DIR="${TMPDIR:-/tmp}/pd_perf_$$"
  fi
fi
mkdir -p "$OUT_DIR"

STAT_TXT="${OUT_DIR}/perf_stat.txt"
TIME_TXT="${OUT_DIR}/gnu_time.txt"
SUMMARY="${OUT_DIR}/SUMMARY.txt"
RECORD_DATA="${OUT_DIR}/perf.data"
IO_BEFORE="${OUT_DIR}/proc_io_before.txt"
IO_AFTER="${OUT_DIR}/proc_io_after.txt"
META="${OUT_DIR}/meta.env"

PERF_BIN=""
if PERF_BIN="$(pd_find_perf)"; then
  pd_log "Using perf: $PERF_BIN ($("$PERF_BIN" --version 2>/dev/null | head -1))"
else
  PERF_BIN=""
  pd_log "WARN: no working perf binary — falling back to GNU time / wall clock"
fi

# Default event set: soft events work in VMs; HW events when PMU exists.
DEFAULT_EVENTS="task-clock,context-switches,cpu-migrations,page-faults,cycles,instructions,cache-references,cache-misses"
EVENTS="${PD_PERF_EVENTS:-$DEFAULT_EVENTS}"

HAVE_GNU_TIME=0
if command -v /usr/bin/time >/dev/null 2>&1 && /usr/bin/time --version >/dev/null 2>&1; then
  HAVE_GNU_TIME=1
fi

# Snapshot host diskstats (coarse) around the run.
snap_disk() {
  local f="$1"
  {
    echo "timestamp=$(date -Iseconds)"
    echo "--- /proc/diskstats ---"
    cat /proc/diskstats 2>/dev/null || true
    echo "--- /proc/meminfo (selected) ---"
    awk '/MemTotal|MemAvailable|Dirty|Writeback|Cached|SwapTotal|SwapFree/ {print}' \
      /proc/meminfo 2>/dev/null || true
  } >"$f"
}

snap_disk "${OUT_DIR}/host_before.txt"

{
  echo "PD_PERF_OUT=$OUT_DIR"
  echo "PD_PERF_BIN=${PERF_BIN:-none}"
  echo "PD_PERF_EVENTS=$EVENTS"
  echo "PD_PERF_RECORD=$DO_RECORD"
  echo "CMD=${CMD[*]}"
  echo "START=$(date -Iseconds)"
} >"$META"

pd_log "Profiling → $OUT_DIR"
pd_log "Command: ${CMD[*]}"

TOOL_RC=0
WALL_START=$(date +%s)

run_cmd() {
  "${CMD[@]}"
}

set +e
if [[ -n "$PERF_BIN" ]]; then
  # shellcheck disable=SC2086
  if [[ "$HAVE_GNU_TIME" -eq 1 ]]; then
    /usr/bin/time -v -o "$TIME_TXT" -- \
      "$PERF_BIN" stat -e "$EVENTS" -o "$STAT_TXT" -- \
      "${CMD[@]}"
  else
    "$PERF_BIN" stat -e "$EVENTS" -o "$STAT_TXT" -- \
      "${CMD[@]}"
  fi
  TOOL_RC=$?
else
  if [[ "$HAVE_GNU_TIME" -eq 1 ]]; then
    /usr/bin/time -v -o "$TIME_TXT" -- "${CMD[@]}"
    TOOL_RC=$?
  else
    run_cmd
    TOOL_RC=$?
  fi
fi
set -e

WALL_END=$(date +%s)
WALL_S=$((WALL_END - WALL_START))
echo "END=$(date -Iseconds)" >>"$META"
echo "WALL_S=$WALL_S" >>"$META"
echo "TOOL_RC=$TOOL_RC" >>"$META"

snap_disk "${OUT_DIR}/host_after.txt"

if [[ "$DO_RECORD" -eq 1 && -n "$PERF_BIN" ]]; then
  pd_log "Optional perf record pass (PD_PERF_RECORD) — re-running briefly is NOT done;"
  pd_log "run manually: $PERF_BIN record -g -o $RECORD_DATA -- <cmd>"
  echo "perf record skipped automatically (would double runtime). Suggested:" \
    >"${OUT_DIR}/perf_record_HINT.txt"
  echo "$PERF_BIN record -g -o $RECORD_DATA -- ${CMD[*]}" \
    >>"${OUT_DIR}/perf_record_HINT.txt"
fi

# --- Classify ---------------------------------------------------------------
python3 - "$SUMMARY" "$STAT_TXT" "$TIME_TXT" "$WALL_S" "$TOOL_RC" <<'PY'
import re, sys
from pathlib import Path

summary, stat_p, time_p, wall_s, tool_rc = sys.argv[1:6]
wall_s = int(wall_s)
tool_rc = int(tool_rc)

stat = Path(stat_p).read_text(errors="replace") if Path(stat_p).exists() else ""
gt = Path(time_p).read_text(errors="replace") if Path(time_p).exists() else ""

def grab_perf(name):
    # lines like:
    #   "          123,456      page-faults:u"
    #   "          2,878.00 msec task-clock:u"
    pat = (
        rf"^\s*([0-9][0-9,]*(?:\.[0-9]+)?|<not supported>)"
        rf"(?:\s+\w+)?\s+{re.escape(name)}"
    )
    m = re.search(pat, stat, re.M)
    if not m:
        # event may appear with :u / :k suffix
        pat2 = (
            rf"^\s*([0-9][0-9,]*(?:\.[0-9]+)?|<not supported>)"
            rf"(?:\s+\w+)?\s+{re.escape(name)}(?::[a-z]+)?"
        )
        m = re.search(pat2, stat, re.M)
    if not m:
        return None
    v = m.group(1)
    if "not supported" in v:
        return None
    return float(v.replace(",", ""))

def grab_time(label):
    m = re.search(rf"^\s*{re.escape(label)}:\s*(.+)$", gt, re.M)
    return m.group(1).strip() if m else None

task_clock = grab_perf("task-clock") or grab_perf("task-clock:u")
cs = grab_perf("context-switches") or grab_perf("context-switches:u")
pf = grab_perf("page-faults") or grab_perf("page-faults:u")
cycles = grab_perf("cycles") or grab_perf("cycles:u")
insns = grab_perf("instructions") or grab_perf("instructions:u")

elapsed = grab_time("Elapsed (wall clock) time (h:mm:ss or m:ss)")
user_t = grab_time("User time (seconds)")
sys_t = grab_time("System time (seconds)")
pct_cpu = grab_time("Percent of CPU this job got")
maj_pf = grab_time("Major (requiring I/O) page faults")
vol_cs = grab_time("Voluntary context switches")
inv_cs = grab_time("Involuntary context switches")
fs_in = grab_time("File system inputs")
fs_out = grab_time("File system outputs")

ipc = None
if cycles and insns and cycles > 0:
    ipc = insns / cycles

# Heuristic classification
signals = []
score_io = 0
score_cpu = 0

def pct_from_str(s):
    if not s:
        return None
    m = re.search(r"([0-9]+)", s)
    return int(m.group(1)) if m else None

cpu_pct = pct_from_str(pct_cpu)
if cpu_pct is not None:
    if cpu_pct < 55:
        score_io += 2
        signals.append(f"low CPU utilization ({cpu_pct}%) → likely waiting on I/O or locks")
    elif cpu_pct > 85:
        score_cpu += 2
        signals.append(f"high CPU utilization ({cpu_pct}%) → compute-heavy phase")

try:
    u = float(user_t) if user_t else None
    s = float(sys_t) if sys_t else None
except ValueError:
    u = s = None
if u is not None and s is not None and wall_s > 0:
    busy = u + s
    if busy < 0.45 * wall_s:
        score_io += 2
        signals.append(f"user+sys ({busy:.1f}s) << wall ({wall_s}s) → stalled / I/O wait")
    elif busy > 0.85 * wall_s:
        score_cpu += 1
        signals.append(f"user+sys fills most of wall time → CPU-bound")

try:
    maj = int(str(maj_pf).replace(",", "")) if maj_pf else 0
except ValueError:
    maj = 0
if maj > 1000:
    score_io += 2
    signals.append(f"many major page faults ({maj}) → cold cache / mmap I/O")

try:
    fsi = int(str(fs_in).replace(",", "")) if fs_in else 0
    fso = int(str(fs_out).replace(",", "")) if fs_out else 0
except ValueError:
    fsi = fso = 0
if fsi + fso > 100_000:
    score_io += 1
    signals.append(f"heavy filesystem ops (in={fsi}, out={fso})")

if pf and wall_s > 0 and (pf / max(wall_s, 1)) > 50_000:
    score_io += 1
    signals.append(f"high page-fault rate ({pf:.0f} / {wall_s}s)")

if ipc is not None:
    if ipc < 0.6:
        score_io += 1
        signals.append(f"low IPC ({ipc:.2f}) — stalls (mem/I/O) possible")
    elif ipc > 1.5:
        score_cpu += 1
        signals.append(f"healthy IPC ({ipc:.2f})")

if score_io >= score_cpu + 2:
    klass = "I/O-bound (or I/O-dominated)"
    rec = (
        "tmpfs+rsync is likely to help. Prefer Mode B (RAM scratch / TMPDIR) first; "
        "use Mode A only if the working set fits. Keep fat logs on disk. "
        "After rsync checkpoints, use PD_SYNC_AFTER_FINALIZE=1 (shell sync) for durability."
    )
elif score_cpu >= score_io + 2:
    klass = "CPU-bound"
    rec = (
        "Filesystem placement will not move the needle much. Optimize algorithms/threads "
        "(taskset/OMP), not tmpfs. Still keep fat logs off NFS if possible."
    )
else:
    klass = "Mixed / unclear"
    rec = (
        "Re-profile the hottest phase alone (lib load vs route vs extract). "
        "Try Mode B on TMPDIR/tmp and compare wall time + this SUMMARY."
    )

lines = []
lines.append("PD job perf profile")
lines.append("===================")
lines.append(f"wall_s={wall_s}  tool_rc={tool_rc}")
lines.append(f"classification={klass}")
lines.append(f"score_io={score_io}  score_cpu={score_cpu}")
lines.append("")
lines.append("Recommendation:")
lines.append(f"  {rec}")
lines.append("")
lines.append("Signals:")
if signals:
    for s in signals:
        lines.append(f"  - {s}")
else:
    lines.append("  - (few counters available; install matching linux-tools / use GNU time)")
lines.append("")
lines.append("Key metrics:")
lines.append(f"  elapsed(time -v)={elapsed}")
lines.append(f"  user_s={user_t}  sys_s={sys_t}  cpu%={pct_cpu}")
lines.append(f"  major_page_faults={maj_pf}")
lines.append(f"  voluntary_cs={vol_cs}  involuntary_cs={inv_cs}")
lines.append(f"  fs_inputs={fs_in}  fs_outputs={fs_out}")
lines.append(f"  perf.task_clock_ms={task_clock}")
lines.append(f"  perf.context_switches={cs}")
lines.append(f"  perf.page_faults={pf}")
lines.append(f"  perf.cycles={cycles}  instructions={insns}  ipc={ipc}")
lines.append("")
lines.append("Artifacts:")
lines.append(f"  {stat_p}")
lines.append(f"  {time_p}")
lines.append("")
lines.append("Notes:")
lines.append("  - perf HW counters may be <not supported> in VMs — soft events still help.")
lines.append("  - Compare the same command on disk vs Mode B/A to quantify I/O win.")
lines.append("  - shell `sync` after finalize ≠ rsync; it flushes writeback for durability.")

Path(summary).write_text("\n".join(lines) + "\n")
print("\n".join(lines))
PY

pd_log "Wrote $SUMMARY"
exit "$TOOL_RC"
