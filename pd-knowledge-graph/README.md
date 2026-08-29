# Physical Design Knowledge Graph (PDKG)

**ChipMind-inspired** ([arXiv:2512.05371](https://arxiv.org/abs/2512.05371)) knowledge graph — adapted from IC *specifications* to **physical-design methodology**, with an accuracy-first curation policy.

| Artifact | Path |
|---|---|
| Ontology (closed types/relations) | [`ontology/pdkg_schema.yaml`](./ontology/pdkg_schema.yaml) |
| Curated gold triples | [`kg/gold_triples.yaml`](./kg/gold_triples.yaml) |
| ChipMind-style constructor | [`src/pdkg/construct.py`](./src/pdkg/construct.py) |
| Graph + multi-hop query | [`src/pdkg/graph.py`](./src/pdkg/graph.py), [`query.py`](./src/pdkg/query.py) |
| Eval QA (atomic facts) | [`queries/pd_eval_qa.yaml`](./queries/pd_eval_qa.yaml) |
| White paper | [`WHITEPAPER.md`](./WHITEPAPER.md) |
| Defend Q&A | [`DEFEND_QA.md`](./DEFEND_QA.md) |

---

## What ChipMind is (so we stay accurate)

**ChipMind** builds **ChipKG** from long **circuit design specifications** (registers, FSMs, signal dependencies) using:

1. **Circuit Semantic Anchors (CSA)** — `(type, entity)` intent tags  
2. **Hierarchical triples** — backbone \(T_B\), auxiliary \(T_A\), linking \(T_L\), normalization \(T_N\)  
3. **Adaptive Top-K** via Marginal Information Gain + CSA filtering  
4. **SpecEval-QA** + Atomic-ROUGE (paper reports mean F1 **0.95**, +34.59% vs baselines)

**PDKG is not a re-run of SpecEval.** It reuses the *methodology* for **PD flow / constraints / failures / mitigations**.

---

## Accuracy policy (non-negotiable)

1. **Closed ontology** — entity types and relations are enumerated; free-form inventing is rejected by the validator.  
2. **Gold triples** carry `confidence` + `provenance` (methodology facts, not vendor QoR claims).  
3. **Auto-extract** from corpus is tagged `source=auto` and never sold as gold.  
4. **CLAIM_GATE** — do **not** cite ChipMind’s 0.95 F1 / +34.59% as this repo’s score.  
5. Vendor-neutral tool *classes* only (Implementation / STA / Extraction / PV) — no fake Synopsys APIs.

---

## Quick start

```bash
cd pd-knowledge-graph
pip install pyyaml

PYTHONPATH=src python3 tests/test_pdkg.py
./examples/compare_all.sh
cat results/SUMMARY.txt

# inspect graph
python3 -c "import json; print(json.load(open('kg/pdkg.json'))['stats'])"

# multi-hop demo
PYTHONPATH=src python3 - <<'PY'
from pdkg.graph import load_gold
from pdkg.query import answer_causal_chain
g = load_gold('kg/gold_triples.yaml')
print(answer_causal_chain(g, 'High_Placement_Density', 'Setup_Violation'))
PY
```

---

## Headline numbers (this build)

| Metric | Value |
|---|---|
| Gold curated triples | 62 |
| Graph after auto-merge | ~76 nodes / ~73 edges |
| Triple classes | backbone / aux / linking / normalization |
| Offline Atomic-F1 proxy (6 PD Qs) | **1.0** on gold facts |
| Multi-hop density→setup path | **found** |

---

## Example multi-hop (gold)

`High_Placement_Density → Routing_Congestion → Detour_Wirelength → Setup_Violation`

That is the PD analogue of ChipMind’s **signal-dependency tracing** — causal methodology instead of RTL signal chains.

---

## Layout

```
pd-knowledge-graph/
├── ontology/pdkg_schema.yaml
├── kg/gold_triples.yaml      # curated
├── kg/pdkg.json              # built artifact
├── corpus/pd_methodology.yaml
├── src/pdkg/                 # construct, graph, query
├── queries/pd_eval_qa.yaml
├── scripts/build_kg.py
├── scripts/eval_qa.py
├── examples/compare_all.sh
└── results/
```

---

## Extend accurately

1. Add a triple only with provenance + confidence in `gold_triples.yaml`.  
2. Run `validate_against_schema` (via `build_kg.py`) — unknown relations fail the build.  
3. Add an atomic-fact question in `queries/pd_eval_qa.yaml`.  
4. Re-run `./examples/compare_all.sh` and check CLAIM_GATE.
