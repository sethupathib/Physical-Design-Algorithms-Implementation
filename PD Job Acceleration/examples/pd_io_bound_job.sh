#!/usr/bin/env bash
# I/O-bound Physical Design–flavored workload (no EDA license).
#
# Mimics farm I/O patterns that hurt over NFS / disk:
#   - liberty-like cell vault: tens of thousands of tiny files, random reads
#   - large DEF/DB-like streams: sequential write + read
#   - frequent checkpoint / report appends
#
# Intentionally little CPU between I/O so wall time tracks filesystem latency.
set -euo pipefail

ROOT="$(pwd)"
LOG="${ROOT}/logs/pd_io.log"
N_CELLS="${N_CELLS:-20000}"
N_LOOKUPS="${N_LOOKUPS:-80000}"
DB_MB="${DB_MB:-256}"
N_CHECKPOINTS="${N_CHECKPOINTS:-8}"
N_REPORTS="${N_REPORTS:-2000}"

mkdir -p logs tmp outputs inputs/libs inputs/lef

{
  echo "cwd=${ROOT}"
  echo "TMPDIR=${TMPDIR:-unset}"
  echo "tmp_resolved=$(readlink -f tmp)"
  echo "logs_resolved=$(readlink -f logs)"
  echo "N_CELLS=${N_CELLS} N_LOOKUPS=${N_LOOKUPS} DB_MB=${DB_MB}"
  echo "start_epoch=$(date +%s.%N)"
  echo "start=$(date -Iseconds)"
} | tee "$LOG"

# ---------- 1) Build / refresh liberty-like cell vault (many tiny files) ----------
# Prefer regenerating into tmp/ (hot), then the job reads from there.
VAULT="${ROOT}/tmp/lib_vault"
rm -rf "$VAULT"
mkdir -p "$VAULT"

echo "phase=gen_vault cells=${N_CELLS}" | tee -a "$LOG"
# Batch-create tiny "liberty" snippets (name + 2 timing arcs). Keep CPU light.
python3 - <<PY
import os
vault = "$VAULT"
n = int("$N_CELLS")
os.makedirs(vault, exist_ok=True)
# Write in batches to reduce Python overhead but keep many small files.
for i in range(n):
    path = os.path.join(vault, f"cell_{i:05d}.lib")
    with open(path, "w", buffering=4096) as f:
        f.write(f"cell(CELL_{i:05d}) {{\n")
        f.write(f"  area : {1.0 + (i % 50) * 0.01};\n")
        f.write(f"  pin(A) {{ direction : input; capacitance : 0.{i%900:03d}; }}\n")
        f.write(f"  pin(Z) {{ direction : output; function : \"A\"; }}\n")
        f.write("}\n")
print(f"wrote {n} cells -> {vault}")
PY

# Also a fat LEF-like blob (sequential)
echo "phase=gen_lef" | tee -a "$LOG"
dd if=/dev/urandom of="${ROOT}/tmp/tech.lef.bin" bs=1M count=64 status=none

# ---------- 2) Random liberty lookups (tiny random reads — classic NFS killer) ----------
echo "phase=lib_lookups count=${N_LOOKUPS}" | tee -a "$LOG"
python3 - <<PY
import os, random, time
vault = "$VAULT"
n_cells = int("$N_CELLS")
n_lookups = int("$N_LOOKUPS")
rng = random.Random(42)
t0 = time.perf_counter()
checksum = 0
for _ in range(n_lookups):
    i = rng.randrange(n_cells)
    path = os.path.join(vault, f"cell_{i:05d}.lib")
    with open(path, "rb") as f:
        data = f.read()
    checksum = (checksum + data[0] + len(data)) & 0xFFFFFFFF
# touch a stamp so we can't DCE the loop
open(os.path.join("$ROOT", "tmp", "lookup_checksum.txt"), "w").write(f"{checksum}\n")
print(f"lookups_done checksum={checksum} seconds={time.perf_counter()-t0:.3f}")
PY
tee -a "$LOG" < "${ROOT}/tmp/lookup_checksum.txt" >/dev/null
echo "lookups_checksum=$(cat tmp/lookup_checksum.txt)" | tee -a "$LOG"

# Sequential read of fat LEF
echo "phase=lef_scan" | tee -a "$LOG"
dd if="${ROOT}/tmp/tech.lef.bin" of=/dev/null bs=1M status=none

# ---------- 3) Growing "design DB" checkpoints (large sequential writes) ----------
echo "phase=checkpoints n=${N_CHECKPOINTS} each=${DB_MB}MB" | tee -a "$LOG"
for c in $(seq 1 "$N_CHECKPOINTS"); do
  dd if=/dev/urandom of="${ROOT}/tmp/design_iter${c}.db" bs=1M count="$DB_MB" status=none
  # read-back verify (placement tool style)
  dd if="${ROOT}/tmp/design_iter${c}.db" of=/dev/null bs=1M status=none
  echo "checkpoint=${c} bytes=$(wc -c < tmp/design_iter${c}.db)" >>"$LOG"
done

# ---------- 4) Report spam (many small appends / files) ----------
echo "phase=reports n=${N_REPORTS}" | tee -a "$LOG"
mkdir -p tmp/reports
python3 - <<PY
import os
root = os.path.join("$ROOT", "tmp", "reports")
os.makedirs(root, exist_ok=True)
n = int("$N_REPORTS")
# one directory of tiny report fragments + one growing log
grow = open(os.path.join("$ROOT", "logs", "opt_grow.log"), "w", buffering=1024)
for i in range(n):
    with open(os.path.join(root, f"win_{i:04d}.rpt"), "w") as f:
        f.write(f"WINDOW {i}\nwns=-0.{i%99:02d}\ntns=-{i%500}.0\n")
    grow.write(f"OPT step={i} cost={i*17%10007} dens=0.{50+i%40}\n")
grow.close()
print(f"reports_done n={n}")
PY

# ---------- 5) Final deliverables on durable outputs/ ----------
echo "phase=finalize_outputs" | tee -a "$LOG"
cp -f tmp/design_iter${N_CHECKPOINTS}.db outputs/design_final.db
cp -f tmp/lookup_checksum.txt outputs/lookup_checksum.txt
# pack a small manifest
{
  echo "cells=${N_CELLS}"
  echo "lookups=${N_LOOKUPS}"
  echo "checkpoints=${N_CHECKPOINTS}"
  echo "db_mb=${DB_MB}"
  echo "checksum=$(cat tmp/lookup_checksum.txt)"
  ls -lh tmp/*.db tmp/tech.lef.bin 2>/dev/null | head
} > outputs/JOB_SUMMARY.txt

{
  echo "done_epoch=$(date +%s.%N)"
  echo "done=$(date -Iseconds)"
  du -sh tmp logs outputs inputs 2>/dev/null
} | tee -a "$LOG"

echo PASS > logs/STATUS
cat outputs/JOB_SUMMARY.txt | tee -a "$LOG"
