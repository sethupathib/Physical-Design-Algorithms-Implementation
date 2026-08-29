# DEFEND_QA — PD Knowledge Graph (ChipMind-inspired)

## 0. One sentence

**PDKG is a ChipMind-shaped knowledge graph for physical-design methodology: closed ontology, curated triples with provenance, multi-hop causal paths — without claiming ChipMind’s SpecEval 0.95 F1 as our score.**

---

## 1. Paper accuracy

**Q: Did you implement ChipMind?**  
A: We implemented the *published methodology concepts* (CSA, hierarchical triples, adaptive retrieve, atomic-fact eval) for **PD**. We did not reproduce their proprietary prompts, SpecEval corpus, or LLM-judge Atomic-ROUGE pipeline.

**Q: Can I say we got +34.59%?**  
A: **No.** That number is ChipMind vs baselines on SpecEval-QA. Cite arXiv:2512.05371 for that. Cite `results/SUMMARY.txt` for PDKG.

---

## 2. Why not dump PD PDFs into GraphRAG?

ChipMind’s own critique: generic KG-RAG loses fine IC semantics. PD has the same issue — “congestion” and “overflow” need typed links to density and setup, not summary nodes.

---

## 3. Challenge round

**Q: Only ~60 triples — is that a knowledge graph?**  
A: It’s a **validated seed ontology + gold graph**. Accuracy > dump size. Expand with provenance gates.

**Q: Auto-extract invented a junk edge?**  
A: Check `source=auto`. Don’t cite it in methodology reviews. Fix lexicon or raise `min_conf`.

**Q: Where’s the LLM?**  
A: Optional later. Offline BoW MIG keeps the demo reproducible and honest on a laptop.

---

## 4. 30-second pitch

“ChipMind taught us to build hardware KGs with semantic anchors and hierarchical triples. We applied that to physical design — curated flow and causal knowledge you can multi-hop query, with a claim gate so we never confuse our seed graph with their SpecEval score.”
