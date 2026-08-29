"""PDKG graph store: load gold + auto triples, validate, export, multi-hop query."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


@dataclass(frozen=True)
class Edge:
    subject: str
    relation: str
    object: str
    triple_class: str
    confidence: float
    source: str
    csa_type: str = ""
    csa_entity: str = ""
    provenance: str = ""


class PDKnowledgeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.out: dict[str, list[Edge]] = defaultdict(list)
        self.inn: dict[str, list[Edge]] = defaultdict(list)
        self.edges: list[Edge] = []
        self.aliases: dict[str, str] = {}

    def add_node(self, name: str, **attrs: Any) -> None:
        if name not in self.nodes:
            self.nodes[name] = {"name": name}
        self.nodes[name].update({k: v for k, v in attrs.items() if v is not None})

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)
        self.add_node(edge.subject, type=edge.csa_type or None)
        self.add_node(edge.object)
        self.out[edge.subject].append(edge)
        self.inn[edge.object].append(edge)
        if edge.relation in ("same_as", "also_called"):
            # normalize both directions for lookup
            self.aliases[edge.subject] = edge.object
            self.aliases[edge.object] = edge.object if edge.relation == "same_as" else edge.subject

    def canonical(self, name: str) -> str:
        seen = set()
        cur = name
        while cur in self.aliases and cur not in seen:
            seen.add(cur)
            nxt = self.aliases[cur]
            if nxt == cur:
                break
            cur = nxt
        return cur

    def neighbors(self, name: str, rels: set[str] | None = None) -> list[Edge]:
        name = self.canonical(name)
        edges = list(self.out.get(name, []))
        if rels is None:
            return edges
        return [e for e in edges if e.relation in rels]

    def multihop(
        self,
        start: str,
        goal: str | None = None,
        max_hops: int = 5,
        rels: set[str] | None = None,
    ) -> list[list[Edge]]:
        """BFS directed paths from start along outgoing edges."""
        start = self.canonical(start)
        goal_c = self.canonical(goal) if goal else None
        paths: list[list[Edge]] = []
        queue: list[tuple[str, list[Edge]]] = [(start, [])]
        # allow revisiting at deeper depth limited by hop cap
        seen_states: set[tuple[str, int]] = {(start, 0)}
        while queue:
            node, path = queue.pop(0)
            if goal_c and node == goal_c and path:
                paths.append(path)
                continue
            if len(path) >= max_hops:
                continue
            for e in self.neighbors(node, rels):
                nxt = self.canonical(e.object)
                depth = len(path) + 1
                state = (nxt, depth)
                if state in seen_states:
                    continue
                seen_states.add(state)
                new_path = path + [e]
                if goal_c is None:
                    paths.append(new_path)
                queue.append((nxt, new_path))
        if goal_c:
            return paths
        uniq = []
        seen = set()
        for p in paths:
            key = tuple((e.subject, e.relation, e.object) for e in p)
            if key not in seen:
                seen.add(key)
                uniq.append(p)
        return uniq

    def csa_filter(self, edges: Iterable[Edge], csa_type: str | None, csa_entity: str | None) -> list[Edge]:
        """ChipMind-style CSA guided filtering."""
        out = []
        for e in edges:
            if csa_type and e.csa_type and e.csa_type != csa_type:
                continue
            if csa_entity and e.csa_entity and e.csa_entity != csa_entity:
                # also allow if subject/object match entity
                if e.subject != csa_entity and e.object != csa_entity:
                    continue
            out.append(e)
        return out

    def stats(self) -> dict[str, Any]:
        by_cls = defaultdict(int)
        by_src = defaultdict(int)
        for e in self.edges:
            by_cls[e.triple_class] += 1
            by_src[e.source.split(":")[0]] += 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "by_triple_class": dict(by_cls),
            "by_source": dict(by_src),
        }

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@context": {
                "name": "https://schema.org/name",
                "relation": "https://pdkg.local/relation",
            },
            "nodes": list(self.nodes.values()),
            "edges": [
                {
                    "subject": e.subject,
                    "relation": e.relation,
                    "object": e.object,
                    "triple_class": e.triple_class,
                    "confidence": e.confidence,
                    "source": e.source,
                    "csa": [e.csa_type, e.csa_entity],
                    "provenance": e.provenance,
                }
                for e in self.edges
            ],
            "stats": self.stats(),
        }


def _parse_gold_row(row: list[Any]) -> Edge:
    s, r, o, meta = row[0], row[1], row[2], row[3]
    csa = meta.get("csa") or ["", ""]
    return Edge(
        subject=s,
        relation=r,
        object=o,
        triple_class=meta.get("triple_class", "backbone"),
        confidence=float(meta.get("confidence", 1.0)),
        source="gold",
        csa_type=csa[0] if len(csa) > 0 else meta.get("s_type", ""),
        csa_entity=csa[1] if len(csa) > 1 else s,
        provenance=meta.get("provenance", ""),
    )


def load_gold(path: Path) -> PDKnowledgeGraph:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    g = PDKnowledgeGraph()
    for row in data["triples"]:
        g.add_edge(_parse_gold_row(row))
    return g


def merge_auto(g: PDKnowledgeGraph, auto_triples: list[dict[str, Any]], min_conf: float = 0.55) -> int:
    n = 0
    existing = {(e.subject, e.relation, e.object) for e in g.edges}
    for t in auto_triples:
        if float(t.get("confidence", 0)) < min_conf:
            continue
        key = (t["subject"], t["relation"], t["object"])
        if key in existing:
            continue
        csa = t.get("csa") or ["", ""]
        g.add_edge(
            Edge(
                subject=t["subject"],
                relation=t["relation"],
                object=t["object"],
                triple_class=t.get("triple_class", "backbone"),
                confidence=float(t.get("confidence", 0.6)),
                source=t.get("source", "auto"),
                csa_type=csa[0] if csa else "",
                csa_entity=csa[1] if len(csa) > 1 else "",
                provenance=t.get("provenance", ""),
            )
        )
        existing.add(key)
        n += 1
    return n


def validate_against_schema(g: PDKnowledgeGraph, schema_path: Path) -> list[str]:
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    allowed_rels = set()
    for group in ("backbone", "auxiliary", "linking", "normalization"):
        allowed_rels.update(schema["relations"][group])
    issues = []
    for e in g.edges:
        if e.relation not in allowed_rels:
            issues.append(f"unknown relation: {e.relation} ({e.subject}->{e.object})")
        if e.source == "gold" and e.confidence < 0.5:
            issues.append(f"gold confidence too low: {e}")
    return issues
