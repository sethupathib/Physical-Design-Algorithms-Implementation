#!/usr/bin/env bash
# Compare policies; write SUMMARY + CLAIM_GATE.
# Default: always-runnable interactive burn vs batch (CPU share / layer weights).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DURATION="${DURATION:-30}"
IX_MODE="${IX_MODE:-burn}"
# Pin to 2 CPUs so 6 batch threads + 1 burn definitively oversubscribe.
PIN_CPUS="${PIN_CPUS:-0-1}"
BATCH_WORKERS="${BATCH_WORKERS:-6}"
export DURATION IX_MODE PIN_CPUS BATCH_WORKERS

cd "$ROOT"
make -s

mkdir -p results
rm -f results/*.json results/*.txt results/SUMMARY.txt results/CLAIM_GATE.txt

POLICIES=(flat nice sched_batch layers protect)

for p in "${POLICIES[@]}"; do
  echo "===== POLICY $p ====="
  LABEL="$p" OUT_JSON="$ROOT/results/${p}.json" OUT_TXT="$ROOT/results/${p}.txt" \
    "$ROOT/scripts/run_one_policy.sh" "$p"
done

python3 - "$ROOT/results" <<'PY'
import json, sys
from pathlib import Path

res = Path(sys.argv[1])
rows = []
for p in ["flat", "nice", "sched_batch", "layers", "protect"]:
    path = res / f"{p}.json"
    if not path.exists():
        continue
    rows.append(json.loads(path.read_text()))

if not rows:
    raise SystemExit("no results")

base = next(r for r in rows if r["label"] == "flat")
mode = base.get("ix_role", "burn")
base_batch = base["batch_iters_per_s"]

lines = []
if mode == "burn":
    base_ix = base["ix_cpu_eq"]
    lines.append("policy\tix_cpu_eq\tix_iters_per_s\tbatch_iters_per_s\tix_vs_flat\tbatch_vs_flat")
    for r in rows:
        ix = r["ix_cpu_eq"]
        b = r["batch_iters_per_s"]
        lines.append(
            f"{r['label']}\t{ix:.3f}\t{r['ix_iters_per_s']:.2f}\t{b:.2f}\t"
            f"{ix/base_ix if base_ix else float('nan'):.3f}x\t"
            f"{b/base_batch if base_batch else float('nan'):.3f}x"
        )
else:
    base_max = base["ix_max_us"]
    base_ppm = base["ix_outlier_ppm"]
    lines.append("policy\tix_p50_us\tix_p99_us\tix_max_us\toutlier_ppm\tbatch_iters_per_s")
    for r in rows:
        lines.append(
            f"{r['label']}\t{r['ix_p50_us']:.1f}\t{r['ix_p99_us']:.1f}\t"
            f"{r['ix_max_us']:.1f}\t{r['ix_outlier_ppm']:.1f}\t{r['batch_iters_per_s']:.2f}"
        )

summary = "\n".join(lines) + "\n"
(res / "SUMMARY.txt").write_text(summary)
print(summary)

gate = ["CLAIM_GATE", f"ix_role={mode}"]
if mode == "burn":
    gate.append(f"baseline flat: ix_cpu_eq={base['ix_cpu_eq']:.3f} batch_iters_per_s={base_batch:.2f}")
    gate.append(
        "rule: postable iff ix_cpu_eq >= 1.40 * flat_ix_cpu_eq "
        "AND batch_rate >= 0.55 * flat_batch"
    )
    gate.append(
        "meaning: layer weights must give the interactive-class burn a clearly larger "
        "CPU share without collapsing batch below 55% of flat"
    )
    gate.append("")
    postable = []
    for r in rows:
        if r["label"] == "flat":
            continue
        ok_ix = r["ix_cpu_eq"] >= 1.40 * base["ix_cpu_eq"]
        ok_batch = r["batch_iters_per_s"] >= 0.55 * base_batch
        status = "PASS" if (ok_ix and ok_batch) else "FAIL"
        gate.append(
            f"{r['label']}: ix_cpu_eq={r['ix_cpu_eq']:.3f} ({'ok' if ok_ix else 'no'}) "
            f"batch={r['batch_iters_per_s']:.2f} ({'ok' if ok_batch else 'no'}) => {status}"
        )
        if status == "PASS":
            postable.append(r["label"])
else:
    gate.append("latency-mode gate omitted in this run path — re-run with IX_MODE=interactive")
    postable = []

gate.append("")
if postable:
    gate.append("POSTABLE_POLICIES=" + ",".join(postable))
    gate.append(
        "LINKEDIN: cite only POSTABLE_POLICIES. Claim = CPU-share control for "
        "interactive-class work under FC-batch oversubscription via layer weights. "
        "Do NOT claim a BPF sched_ext scheduler was loaded on this host."
    )
else:
    gate.append("POSTABLE_POLICIES=")
    gate.append("LINKEDIN: no postable win on this host run — say that, or re-run on a farm node.")

gate += [
    "",
    "KERNEL_FACTS:",
    "  /sys/kernel/sched_ext absent => CONFIG_SCHED_EXT not enabled here",
    "  control plane measured: cgroup v2 cpu.weight / nice / SCHED_BATCH",
    "  configs/scx_layered_*.json = same policy shape for when SCX is available",
]
text = "\n".join(gate) + "\n"
(res / "CLAIM_GATE.txt").write_text(text)
print(text)
PY
