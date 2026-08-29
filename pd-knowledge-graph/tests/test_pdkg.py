#!/usr/bin/env python3
"""Unit tests for PDKG accuracy gates."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdkg.construct import to_ir, hierarchical_extract
from pdkg.graph import load_gold, validate_against_schema
from pdkg.query import answer_causal_chain


def test_schema_and_gold():
    g = load_gold(ROOT / "kg" / "gold_triples.yaml")
    issues = validate_against_schema(g, ROOT / "ontology" / "pdkg_schema.yaml")
    assert not issues, issues
    assert g.stats()["edges"] >= 50
    print("test_schema_and_gold OK", g.stats())


def test_causal_multihop():
    g = load_gold(ROOT / "kg" / "gold_triples.yaml")
    r = answer_causal_chain(g, "High_Placement_Density", "Setup_Violation", max_hops=4)
    assert r["n_paths"] >= 1, r
    print("test_causal_multihop OK", r["paths"][0]["path"])


def test_ir_classification():
    ir = to_ir("If placement density is too high, global routing reports congestion overflow in gcells.")
    assert ir.function == "procedural"
    assert any(e.entity == "High_Placement_Density" for e in ir.entities) or any(
        e.entity == "Routing_Congestion" for e in ir.entities
    )
    triples = hierarchical_extract(ir)
    assert triples
    print("test_ir_classification OK", ir.function, [t.as_tuple() for t in triples[:3]])


def test_hold_mitigation_edge():
    g = load_gold(ROOT / "kg" / "gold_triples.yaml")
    edges = {(e.subject, e.relation, e.object) for e in g.edges}
    assert ("Hold_Buffer_Insertion", "mitigates", "Hold_Violation") in edges
    print("test_hold_mitigation_edge OK")


if __name__ == "__main__":
    test_schema_and_gold()
    test_causal_multihop()
    test_ir_classification()
    test_hold_mitigation_edge()
    print("ALL PASS")
