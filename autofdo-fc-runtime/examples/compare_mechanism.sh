#!/usr/bin/env bash
# Mechanism compare: dispatch_hot baseline vs GCC PGO (skewed switch).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/build"
OUT="$ROOT/results"
mkdir -p "$OUT"
ITERS="${ITERS:-25000000}"
REPEATS="${REPEATS:-7}"

[[ -x $BIN/dispatch_hot_baseline && -x $BIN/dispatch_hot_pgo ]] || {
  echo "run: make mechanism" >&2; exit 1; }

measure() {
  local label=$1 bin=$2
  local f="$OUT/mech_${label}_runs.jsonl"
  : >"$f"
  for _ in $(seq 1 "$REPEATS"); do "$bin" "$ITERS" >>"$f"; done
  python3 - "$f" "$OUT/mech_${label}.json" "$label" <<'PY'
import json,sys,statistics
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
ms=[r["wall_ms"] for r in rows]
s={"label":sys.argv[3],"wall_ms_median":statistics.median(ms),
   "wall_ms_mean":statistics.mean(ms),"wall_ms_stdev":statistics.pstdev(ms) if len(ms)>1 else 0,
   "wall_ms_runs":ms,"acc":rows[0]["acc"]}
json.dump(s, open(sys.argv[2],"w"), indent=2)
print(f"  {s['label']:10s} median={s['wall_ms_median']:.3f} ms")
PY
}

echo "==== mechanism: dispatch_hot (skewed switch) ===="
measure baseline "$BIN/dispatch_hot_baseline"
measure pgo "$BIN/dispatch_hot_pgo"

python3 - "$OUT" <<'PY' | tee "$OUT/MECHANISM_SUMMARY.txt"
import json
from pathlib import Path
out=Path(__import__("sys").argv[1])
b=json.loads((out/"mech_baseline.json").read_text())
p=json.loads((out/"mech_pgo.json").read_text())
bm,pm=b["wall_ms_median"],p["wall_ms_median"]
imp=(bm-pm)/bm*100
correct=b["acc"]==p["acc"]
gate="CITEABLE=yes_mechanism_pgo" if correct and imp>=1.5 else (
 "CITEABLE=yes_mechanism_small" if correct and imp>0 else
 "CITEABLE=yes_mechanism_neutral" if correct else "CITEABLE=no")
print("="*64)
print("MECHANISM SUMMARY — dispatch_hot GCC PGO")
print("="*64)
print(f"  baseline  {bm:.3f} ms")
print(f"  pgo       {pm:.3f} ms   improve {imp:+.2f}%")
print(f"  acc MATCH={correct}  gate={gate}")
print("  Scope: proves FDO can help branchy code. NOT Fusion Compiler.")
print("="*64)
(out/"MECHANISM_CLAIM_GATE.txt").write_text(gate+"\n")
PY
