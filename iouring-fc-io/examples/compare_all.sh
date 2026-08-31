#!/usr/bin/env bash
# Measure posix vs io_uring on FC-shaped dataset. Writes results/SUMMARY.txt
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/results"
mkdir -p "$OUT"
cd "$ROOT"

make -s all
if [[ ! -d data/small ]] || [[ "${REGEN:-0}" == "1" ]]; then
  bash scripts/gen_dataset.sh
fi

echo "==== bench ===="
./build/fc_io_bench --root data --mode all --backend all --repeat 5 | tee "$OUT/raw.jsonl"

python3 - <<'PY' | tee "$OUT/SUMMARY.txt"
import json, statistics
from pathlib import Path
from collections import defaultdict
root = Path(".")
rows = [json.loads(l) for l in (root/"results"/"raw.jsonl").read_text().splitlines() if l.strip()]
groups = defaultdict(list)
for r in rows:
    groups[(r["backend"], r["subset"])].append(r)

lines = []
lines.append("=" * 72)
lines.append("SUMMARY — io_uring vs POSIX for FC-shaped I/O")
lines.append("=" * 72)
lines.append("")
lines.append("SCOPE")
lines.append("  NOT Synopsys Fusion Compiler internals (closed binary).")
lines.append("  Measures wrappers / deck stage-in / log+lib hydrate patterns.")
lines.append("  FC wall time improves only when the job is I/O-bound on these paths.")
lines.append("")
lines.append(f"{'backend':<16} {'subset':<14} {'median_s':>10} {'MiB/s':>10} {'nfiles':>8}")
med = {}
for (backend, subset), rs in sorted(groups.items()):
    secs = [r["sec"] for r in rs]
    mibs = [r["MiB_s"] for r in rs]
    m = statistics.median(secs)
    mb = statistics.median(mibs)
    med[(backend, subset)] = m
    lines.append(f"{backend:<16} {subset:<14} {m:10.4f} {mb:10.1f} {rs[0]['nfiles']:8d}")

lines.append("")
lines.append("Speedup vs posix (posix_median / backend_median), >1 = faster than posix:")
for subset in ("small_files", "large_files", "mixed"):
    p = med.get(("posix", subset))
    if not p: continue
    for be in ("iouring", "iouring_openat"):
        u = med.get((be, subset))
        if u and u > 0:
            lines.append(f"  {subset:<14}  {be:<16}  {p/u:.3f}x")

best = 0.0
for subset in ("small_files", "large_files", "mixed"):
    p = med.get(("posix", subset))
    if not p: continue
    for be in ("iouring", "iouring_openat"):
        u = med.get((be, subset))
        if u and u > 0:
            best = max(best, p/u - 1.0)
if best >= 0.15:
    gate = "CITEABLE=yes_iouring_win"
elif best > 0.0:
    gate = "CITEABLE=yes_iouring_small_win"
else:
    gate = "CITEABLE=yes_measured_no_win"
lines.append("")
lines.append("CLAIM_GATE")
lines.append(f"  {gate}")
lines.append("  Never claim 'FC got Xx faster' — claim 'stage-in/hydrate path improved'.")
lines.append("=" * 72)
print("\n".join(lines))
(root/"results"/"CLAIM_GATE.txt").write_text(gate + "\n")
(root/"results"/"summary.json").write_text(json.dumps({
    "medians_sec": {f"{b}:{s}": med[(b,s)] for b,s in med},
    "claim_gate": gate,
}, indent=2))
PY
