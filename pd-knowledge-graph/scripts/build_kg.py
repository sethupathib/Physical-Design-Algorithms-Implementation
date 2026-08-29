#!/usr/bin/env python3
"""Build PDKG from gold triples + ChipMind-style auto-extraction over corpus."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdkg.construct import extract_document
from pdkg.graph import load_gold, merge_auto, validate_against_schema


def load_corpus(path: Path) -> list[dict]:
    docs = []
    for block in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if block:
            docs.append(block)
    return docs


def main() -> int:
    out = ROOT / "kg"
    out.mkdir(parents=True, exist_ok=True)
    g = load_gold(ROOT / "kg" / "gold_triples.yaml")
    issues = validate_against_schema(g, ROOT / "ontology" / "pdkg_schema.yaml")

    auto_all = []
    for doc in load_corpus(ROOT / "corpus" / "pd_methodology.yaml"):
        extracted = extract_document(doc["sentences"], doc["id"])
        auto_all.append(extracted)
        merge_auto(g, extracted["triples"], min_conf=0.55)

    payload = g.to_jsonld()
    payload["validation_issues"] = issues
    payload["auto_docs"] = [{"doc_id": d["doc_id"], "n_irs": len(d["irs"]), "n_triples": len(d["triples"])} for d in auto_all]
    (out / "pdkg.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # GraphML-ish simple edge list
    lines = ["source,relation,target,triple_class,confidence,source_tag"]
    for e in g.edges:
        lines.append(
            f"{e.subject},{e.relation},{e.object},{e.triple_class},{e.confidence},{e.source}"
        )
    (out / "pdkg_edges.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # IR dump for inspection
    (out / "auto_extraction.json").write_text(json.dumps(auto_all, indent=2), encoding="utf-8")

    stats = g.stats()
    print(json.dumps({"wrote": str(out / "pdkg.json"), "stats": stats, "issues": issues}, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
