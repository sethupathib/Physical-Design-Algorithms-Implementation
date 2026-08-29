"""Query + ChipMind-inspired adaptive retrieval over PDKG."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .graph import Edge, PDKnowledgeGraph


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def bow_vec(tokens: list[str]) -> Counter:
    return Counter(tokens)


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class RetrievalHit:
    edge: Edge
    score: float
    text: str


class PDKGRetriever:
    """
    Adaptive Top-K inspired by ChipMind MIG (arXiv:2512.05371 §3.3).
    Proxy: expand candidates while bag-of-words summary cosine gain stays above tau.
    No LLM required — accurate enough for offline demos.
    """

    def __init__(self, g: PDKnowledgeGraph) -> None:
        self.g = g
        self.corpus: list[RetrievalHit] = []
        for e in g.edges:
            text = f"{e.subject} {e.relation} {e.object} {e.provenance} {e.csa_type} {e.csa_entity}"
            self.corpus.append(RetrievalHit(edge=e, score=0.0, text=text))

    def rank(self, query: str) -> list[RetrievalHit]:
        qv = bow_vec(tokenize(query))
        scored = []
        for h in self.corpus:
            s = cosine(qv, bow_vec(tokenize(h.text)))
            scored.append(RetrievalHit(edge=h.edge, score=s, text=h.text))
        scored.sort(key=lambda x: -x.score)
        return scored

    def adaptive_retrieve(self, query: str, k0: int = 3, dk: int = 2, tau: float = 0.02, kmax: int = 20) -> list[RetrievalHit]:
        ranked = self.rank(query)
        if not ranked:
            return []
        S = ranked[:k0]
        t = 0
        while len(S) < min(kmax, len(ranked)):
            delta = ranked[len(S) : len(S) + dk]
            if not delta:
                break
            base = " ".join(h.text for h in S)
            new = base + " " + " ".join(h.text for h in delta)
            # MIG proxy: 1 - cos(emb(summary_base), emb(summary_new))
            # without LLM summaries, use the concatenated evidence text itself
            mig = 1.0 - cosine(bow_vec(tokenize(base)), bow_vec(tokenize(new)))
            if mig > tau:
                S = S + delta
                t += 1
            else:
                break
        return S

    def csa_filter(self, hits: list[RetrievalHit], csa_type: str | None, csa_entity: str | None) -> list[RetrievalHit]:
        edges = self.g.csa_filter([h.edge for h in hits], csa_type, csa_entity)
        keep = {(e.subject, e.relation, e.object) for e in edges}
        return [h for h in hits if (h.edge.subject, h.edge.relation, h.edge.object) in keep]


def answer_causal_chain(g: PDKnowledgeGraph, start: str, goal: str, max_hops: int = 4) -> dict[str, Any]:
    """Multi-hop causal path — the PD analogue of ChipMind signal-dependency tracing."""
    rels = {"causes", "mitigates", "detects", "precedes_in_flow", "typically_after", "same_as", "also_called"}
    paths = g.multihop(start, goal=goal, max_hops=max_hops, rels=rels)
    # also try via mitigates reverse etc. — BFS already bidirectional via neighbors
    pretty = []
    for p in paths[:5]:
        pretty.append(
            {
                "hops": len(p),
                "path": [f"{e.subject} -[{e.relation}/{e.triple_class}]→ {e.object}" for e in p],
                "min_confidence": min(e.confidence for e in p),
                "sources": sorted({e.source for e in p}),
            }
        )
    return {"start": start, "goal": goal, "n_paths": len(paths), "paths": pretty}


def answer_with_retrieval(g: PDKnowledgeGraph, question: str, csa_type: str | None = None, csa_entity: str | None = None) -> dict[str, Any]:
    r = PDKGRetriever(g)
    hits = r.adaptive_retrieve(question)
    if csa_type or csa_entity:
        filtered = r.csa_filter(hits, csa_type, csa_entity)
    else:
        filtered = hits
    return {
        "question": question,
        "n_adaptive": len(hits),
        "n_after_csa_filter": len(filtered),
        "evidence": [
            {
                "score": round(h.score, 3),
                "triple": [h.edge.subject, h.edge.relation, h.edge.object],
                "class": h.edge.triple_class,
                "confidence": h.edge.confidence,
                "source": h.edge.source,
                "csa": [h.edge.csa_type, h.edge.csa_entity],
            }
            for h in filtered[:10]
        ],
    }
