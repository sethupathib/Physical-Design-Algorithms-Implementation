#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/results"
mkdir -p "$OUT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

pip install -q pyyaml >/dev/null 2>&1 || true

echo "==== build PDKG ===="
python3 "$ROOT/scripts/build_kg.py" | tee "$OUT/build.json"

echo "==== eval QA ===="
python3 "$ROOT/scripts/eval_qa.py" | tee "$OUT/eval_stdout.txt"

python3 - <<PY | tee "$OUT/SUMMARY.txt"
import json
from pathlib import Path
root = Path("$ROOT")
build = json.loads((root/"results"/"build.json").read_text()) if (root/"results"/"build.json").exists() else {}
# build.json from tee may be the print of build_kg — parse last
raw = (root/"results"/"build.json").read_text().strip()
try:
    build = json.loads(raw)
except Exception:
    # tee captured stdout of build
    build = json.loads(raw.splitlines()[-1]) if False else json.loads(raw)
stats = build.get("stats", build)
evalj = json.loads((root/"results"/"eval.json").read_text())
# recount gold
import yaml
gold = yaml.safe_load((root/"kg"/"gold_triples.yaml").read_text())
n_gold = len(gold["triples"])
lines = []
lines.append("=" * 72)
lines.append("SUMMARY — Physical Design Knowledge Graph (PDKG)")
lines.append("Inspired by ChipMind ChipKG (arXiv:2512.05371), adapted to PD methodology")
lines.append("=" * 72)
lines.append("")
lines.append("ACCURACY POLICY")
lines.append("  - Closed ontology + relation vocabulary")
lines.append("  - Gold triples curated with confidence + provenance")
lines.append("  - Auto-extract flagged source=auto (corpus demo)")
lines.append("  - Eval uses atomic facts grounded in gold — not ChipMind's 0.95 SpecEval F1")
lines.append("")
lines.append("1) Graph size")
if isinstance(stats, dict) and "nodes" in stats:
    lines.append(f"   nodes={stats['nodes']}  edges={stats['edges']}")
    lines.append(f"   by_class={stats.get('by_triple_class')}")
    lines.append(f"   by_source={stats.get('by_source')}")
else:
    st = stats.get("stats", stats)
    lines.append(f"   nodes={st.get('nodes')}  edges={st.get('edges')}")
    lines.append(f"   by_class={st.get('by_triple_class')}")
    lines.append(f"   by_source={st.get('by_source')}")
lines.append(f"   curated gold triples: {n_gold}")
lines.append("")
lines.append("2) Offline QA (atomic-fact proxy)")
lines.append(f"   questions: {evalj['n_questions']}")
lines.append(f"   avg Atomic-F1 proxy: {evalj['avg_atomic_f1_proxy']}")
lines.append(f"   avg entity recall:   {evalj['avg_entity_recall']}")
lines.append(f"   path checks OK:      {evalj['all_path_ok']}")
lines.append("")
lines.append("3) ChipMind mapping")
lines.append("   CSA              → PDKG csa_types (FlowStage, FailureMode, ...)")
lines.append("   Hierarchical T_* → backbone/auxiliary/linking/normalization")
lines.append("   Adaptive Top-K   → scripts use MIG proxy (BoW cosine)")
lines.append("   SpecEval-QA      → queries/pd_eval_qa.yaml (PD methodology)")
lines.append("")
lines.append("4) Claim gate")
gate = "CITEABLE=yes_pdkg_gold_eval"
if evalj["avg_atomic_f1_proxy"] < 0.99 or not evalj["all_path_ok"]:
    gate = "CITEABLE=yes_pdkg_partial"
lines.append(f"   {gate}")
lines.append("   Do NOT cite ChipMind's +34.59% / 0.95 F1 as this repo's score.")
lines.append("=" * 72)
print("\n".join(lines))
(root/"results"/"CLAIM_GATE.txt").write_text(gate+"\n")
PY

echo "Artifacts in $OUT"
