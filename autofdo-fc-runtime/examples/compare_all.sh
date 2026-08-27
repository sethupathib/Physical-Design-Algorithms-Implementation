#!/usr/bin/env bash
# Compare baseline vs instrumentation-PGO (and sample-AutoFDO if present)
# on the signoff_proxy microbench. Emits CLAIM_GATE for honesty.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${ROOT}/build"
OUT="${ROOT}/results"
mkdir -p "$OUT"

BASE="${BIN}/signoff_proxy_baseline"
PGO="${BIN}/signoff_proxy_pgo"
AFDO="${BIN}/signoff_proxy_autofdo"

NODES="${NODES:-12000}"
ROUNDS="${ROUNDS:-50}"
QUERIES="${QUERIES:-250000}"
OPS="${OPS:-2000000}"
SEED="${SEED:-42}"
REPEATS="${REPEATS:-7}"

if [[ ! -x "$BASE" ]]; then
  echo "missing baseline binary — run: make baseline" >&2
  exit 1
fi
if [[ ! -x "$PGO" ]]; then
  echo "missing PGO binary — run: make pgo" >&2
  exit 1
fi

run_one() {
  local bin="$1"
  "$bin" --nodes "$NODES" --rounds "$ROUNDS" --queries "$QUERIES" --ops "$OPS" --seed "$SEED" --json
}

echo "================================================================"
echo " AutoFDO / PGO vs baseline — signoff_proxy (FC/signoff-shaped)"
echo "================================================================"
echo "nodes=$NODES rounds=$ROUNDS queries=$QUERIES ops=$OPS seed=$SEED repeats=$REPEATS"
echo

measure() {
  local label="$1" bin="$2"
  local f="$OUT/${label}_runs.jsonl"
  : >"$f"
  local i
  for i in $(seq 1 "$REPEATS"); do
    run_one "$bin" >>"$f"
  done
  python3 - "$f" "$OUT/${label}.json" "$label" <<'PY'
import json, sys, statistics
path, outp, label = sys.argv[1:4]
rows = [json.loads(l) for l in open(path) if l.strip()]
ms = [r["wall_ms"] for r in rows]
summary = {
    "label": label,
    "wall_ms_runs": ms,
    "wall_ms_median": statistics.median(ms),
    "wall_ms_mean": statistics.mean(ms),
    "wall_ms_stdev": statistics.pstdev(ms) if len(ms) > 1 else 0.0,
    "nodes": rows[0]["nodes"],
    "rounds": rows[0]["rounds"],
    "queries": rows[0]["queries"],
    "ops": rows[0].get("ops"),
    "seed": rows[0]["seed"],
    "checksum": rows[0]["checksum"],
    "dispatch": rows[0].get("dispatch"),
}
json.dump(summary, open(outp, "w"), indent=2)
print(f"  {label:12s}  median={summary['wall_ms_median']:.3f} ms  "
      f"mean={summary['wall_ms_mean']:.3f}  stdev={summary['wall_ms_stdev']:.3f}")
PY
}

echo "---- wall time ----"
measure baseline "$BASE"
measure pgo "$PGO"

AFDO_OK=0
if [[ -x "$AFDO" ]]; then
  measure autofdo "$AFDO"
  AFDO_OK=1
else
  echo "  autofdo      SKIP (make sample-autofdo first, or environment lacks sample profile)"
  echo '{"label":"autofdo","skipped":true}' >"$OUT/autofdo.json"
fi

python3 - "$OUT" "$AFDO_OK" <<'PY' | tee "$OUT/SUMMARY.txt"
import json, sys
from pathlib import Path

out = Path(sys.argv[1])
afdo_ok = sys.argv[2] == "1"

base = json.loads((out / "baseline.json").read_text())
pgo = json.loads((out / "pgo.json").read_text())
afdo = json.loads((out / "autofdo.json").read_text())

b = base["wall_ms_median"]
p = pgo["wall_ms_median"]
speedup_pgo = b / p if p > 0 else float("nan")
improve_pgo_pct = (b - p) / b * 100.0 if b > 0 else float("nan")

correct = (
    base.get("dispatch") == pgo.get("dispatch")
    and abs(base["checksum"] - pgo["checksum"]) < 1e-3
)

if not correct:
    gate = "CITEABLE=no_correctness"
elif improve_pgo_pct >= 3.0:
    gate = "CITEABLE=yes_proxy_pgo"
elif improve_pgo_pct > 0.0:
    gate = "CITEABLE=yes_proxy_measured_small"
elif improve_pgo_pct > -2.0:
    gate = "CITEABLE=yes_proxy_measured_neutral"
else:
    gate = "CITEABLE=yes_proxy_measured_regression"

lines = []
lines.append("=" * 72)
lines.append("SUMMARY — AutoFDO/PGO for PD/signoff-shaped runtime (proxy)")
lines.append("=" * 72)
lines.append("")
lines.append("IMPORTANT SCOPE")
lines.append("  - Measured binary: signoff_proxy (open microbench), NOT Fusion Compiler.")
lines.append("  - Vendor EDA binaries cannot be AutoFDO-rebuilt without source.")
lines.append("  - Kernel AutoFDO (~10% latency in published Neper/tcp_rr) is a FARM host")
lines.append("    methodology — see farm/KERNEL_AUTOFDO.md and WHITEPAPER.md.")
lines.append("")
lines.append("1) Wall time (median of repeats)")
lines.append(f"   baseline     {b:10.3f} ms")
lines.append(f"   pgo (instr)  {p:10.3f} ms   speedup {speedup_pgo:.3f}x   improve {improve_pgo_pct:+.2f}%")
if afdo_ok and not afdo.get("skipped"):
    a = afdo["wall_ms_median"]
    sp = b / a if a > 0 else float("nan")
    imp = (b - a) / b * 100.0 if b > 0 else float("nan")
    lines.append(f"   autofdo(smpl){a:10.3f} ms   speedup {sp:.3f}x   improve {imp:+.2f}%")
else:
    lines.append("   autofdo(smpl)     SKIP")
lines.append("")
lines.append("2) Correctness (same seed)")
lines.append(f"   dispatch  baseline={base.get('dispatch')} pgo={pgo.get('dispatch')}  "
             f"{'MATCH' if base.get('dispatch')==pgo.get('dispatch') else 'DIFF'}")
lines.append(f"   checksum  baseline={base['checksum']:.6g} pgo={pgo['checksum']:.6g}  "
             f"{'MATCH' if abs(base['checksum']-pgo['checksum'])<1e-3 else 'DIFF'}")
lines.append("")
lines.append("3) How this maps to Fusion Compiler / signoff farms")
lines.append("   A) User-space PGO/AutoFDO  → your CAD helpers, log tools, in-house engines")
lines.append("   B) Kernel AutoFDO          → farm Linux (published ~10% kernel latency)")
lines.append("   C) Vendor FC/ICC2/PT       → ask vendor for PGO builds; you cannot rebuild")
lines.append("")
lines.append("4) Claim gate")
lines.append(f"   {gate}")
lines.append("   NEVER cite proxy numbers as 'Fusion Compiler got X% faster'.")
lines.append("   Kernel 10% figure: cite Google/Meta/LPC papers, not this microbench.")
lines.append("=" * 72)

text = "\n".join(lines) + "\n"
print(text, end="")
(out / "CLAIM_GATE.txt").write_text(gate + "\n")
(out / "summary.json").write_text(json.dumps({
    "baseline_ms": b,
    "pgo_ms": p,
    "speedup_pgo": speedup_pgo,
    "improve_pgo_pct": improve_pgo_pct,
    "correct": correct,
    "claim_gate": gate,
    "afdo_ok": afdo_ok,
}, indent=2))
PY

echo
echo "Artifacts: $OUT/SUMMARY.txt  $OUT/CLAIM_GATE.txt  $OUT/*.json"
