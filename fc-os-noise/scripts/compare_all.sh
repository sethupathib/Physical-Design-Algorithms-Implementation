#!/usr/bin/env bash
# Compare soft-isolation policies; write SUMMARY + CLAIM_GATE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
make -s
mkdir -p results
rm -f results/*.json results/*.txt results/SUMMARY.txt results/CLAIM_GATE.txt

# Defaults tuned so contention is visible on a 4-CPU laptop/cloud VM.
export ROUNDS="${ROUNDS:-400}"
export BURST_US="${BURST_US:-2000}"
export THREADS="${THREADS:-2}"
export NOISE_PROCS="${NOISE_PROCS:-4}"
export NOISE_SLEEP_US="${NOISE_SLEEP_US:-0}"

"$ROOT/scripts/probe_isolation.sh" | tee results/PROBE.txt

POLICIES=(flat_quiet pin_only flat_contend pin_split)
for p in "${POLICIES[@]}"; do
  echo "===== $p ====="
  LABEL="$p" OUT_JSON="$ROOT/results/${p}.json" OUT_TXT="$ROOT/results/${p}.txt" \
    "$ROOT/scripts/run_one_policy.sh" "$p"
done

python3 - "$ROOT/results" <<'PY'
import json, sys
from pathlib import Path
res = Path(sys.argv[1])
order = ["flat_quiet", "pin_only", "flat_contend", "pin_split"]
rows = []
for p in order:
    path = res / f"{p}.json"
    if path.exists():
        rows.append(json.loads(path.read_text()))

lines = ["policy\twall_s\tp50_us\tp99_us\tmax_us"]
for r in rows:
    lines.append(
        f"{r['label']}\t{r['wall_s']:.3f}\t{r['round_p50_us']:.1f}\t"
        f"{r['round_p99_us']:.1f}\t{r['round_max_us']:.1f}"
    )
summary = "\n".join(lines) + "\n"
(res / "SUMMARY.txt").write_text(summary)
print(summary)

by = {r["label"]: r for r in rows}
gate = ["CLAIM_GATE", "soft-isolation (taskset) under synthetic OS noise"]
if "flat_contend" in by and "pin_split" in by:
    fc, ps = by["flat_contend"], by["pin_split"]
    ok_p99 = ps["round_p99_us"] <= 0.85 * fc["round_p99_us"]
    ok_wall = ps["wall_s"] <= 0.90 * fc["wall_s"]
    status = "PASS" if (ok_p99 or ok_wall) else "FAIL"
    gate += [
        f"flat_contend: wall={fc['wall_s']:.3f}s p99={fc['round_p99_us']:.1f}us",
        f"pin_split:    wall={ps['wall_s']:.3f}s p99={ps['round_p99_us']:.1f}us",
        f"p99_ratio pin/flat={ps['round_p99_us']/fc['round_p99_us']:.3f} ({'ok' if ok_p99 else 'no'})",
        f"wall_ratio pin/flat={ps['wall_s']/fc['wall_s']:.3f} ({'ok' if ok_wall else 'no'})",
        f"rule: p99<=0.85x OR wall<=0.90x => {status}",
        f"POSTABLE_SOFT_ISOLATION={'yes' if status=='PASS' else 'no'}",
    ]
else:
    gate += ["POSTABLE_SOFT_ISOLATION=no", "missing flat_contend or pin_split"]

gate += [
    "",
    "BOOT_PARAMS (farm node — requires reboot; not applied on this demo host):",
    "  isolcpus=<job_cpus> nohz_full=<job_cpus> rcu_nocbs=<job_cpus>",
    "  then: taskset -c <job_cpus> fc_shell -f run.tcl",
    "This demo proves the pinning half without reboot; full nohz/rcu needs cmdline.",
]
text = "\n".join(gate) + "\n"
(res / "CLAIM_GATE.txt").write_text(text)
print(text)
PY
