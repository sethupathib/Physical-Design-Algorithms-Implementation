"""
PDKG — ChipMind-inspired Circuit Semantic-Aware construction for Physical Design.

Faithful to ChipMind (arXiv:2512.05371) concepts:
  - Declarative vs Procedural sentence categorization
  - Circuit Semantic Anchors (CSA) = (type, entity)
  - Semantic IR (JSON)
  - Hierarchical triples: backbone (T_B), auxiliary (T_A), linking (T_L), normalization (T_N)

This module uses *rule-based* PD templates for reproducibility and accuracy.
It does NOT claim to reproduce ChipMind's proprietary LLM prompts or SpecEval numbers.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


DECLARATIVE_CUES = re.compile(
    r"\b(is|are|defines?|builds?|assigns?|computes?|evaluates?|runs?|detects?|means?)\b",
    re.I,
)
PROCEDURAL_CUES = re.compile(
    r"\b(if|when|causes?|then|after|before|typically|insert|upsize|mitigate[sd]?)\b",
    re.I,
)

# Lexicon: surface form → (csa_type, canonical_entity)
LEXICON: dict[str, tuple[str, str]] = {
    "floorplan": ("FlowStage", "Floorplan"),
    "power planning": ("FlowStage", "Power_Planning"),
    "power grid": ("PhysicalObject", "Power_Grid"),
    "placement": ("FlowStage", "Placement"),
    "clock tree synthesis": ("FlowStage", "Clock_Tree_Synthesis"),
    "cts": ("FlowStage", "Clock_Tree_Synthesis"),
    "routing": ("FlowStage", "Routing"),
    "rc extraction": ("FlowStage", "RC_Extraction"),
    "static timing analysis": ("FlowStage", "Static_Timing_Analysis"),
    "sta": ("FlowStage", "Static_Timing_Analysis"),
    "physical verification": ("FlowStage", "Physical_Verification"),
    "signoff": ("FlowStage", "Signoff"),
    "setup violation": ("FailureMode", "Setup_Violation"),
    "setup violations": ("FailureMode", "Setup_Violation"),
    "hold violation": ("FailureMode", "Hold_Violation"),
    "hold violations": ("FailureMode", "Hold_Violation"),
    "congestion": ("FailureMode", "Routing_Congestion"),
    "congestion overflow": ("FailureMode", "Routing_Congestion"),
    "placement density": ("FailureMode", "High_Placement_Density"),
    "detour": ("FailureMode", "Detour_Wirelength"),
    "wirelength": ("FailureMode", "Detour_Wirelength"),
    "antenna": ("FailureMode", "Antenna_Violation"),
    "antenna violations": ("FailureMode", "Antenna_Violation"),
    "antenna diode": ("Action", "Antenna_Diode_or_Layer_Hop"),
    "layer hop": ("Action", "Antenna_Diode_or_Layer_Hop"),
    "ir drop": ("FailureMode", "Excessive_IR_Drop"),
    "drc": ("Check", "Design_Rule_Check"),
    "design rule check": ("Check", "Design_Rule_Check"),
    "lvs": ("Check", "Layout_Versus_Schematic"),
    "layout versus schematic": ("Check", "Layout_Versus_Schematic"),
    "buffers": ("Action", "Buffer_Insertion_or_Upsize"),
    "insert buffers": ("Action", "Buffer_Insertion_or_Upsize"),
    "upsize cells": ("Action", "Buffer_Insertion_or_Upsize"),
    "hold buffers": ("Action", "Hold_Buffer_Insertion"),
    "widening straps": ("Action", "Widen_Straps_or_Add_Vias"),
    "adding vias": ("Action", "Widen_Straps_or_Add_Vias"),
    "sdc": ("InputArtifact", "SDC"),
    "parasitics": ("InputArtifact", "SPEF_or_RCDB"),
}


@dataclass
class CSA:
    type: str
    entity: str

    def key(self) -> tuple[str, str]:
        return (self.type, self.entity)


@dataclass
class SemanticIR:
    sentence: str
    function: str  # declarative | procedural
    csa: CSA
    entities: list[CSA] = field(default_factory=list)
    trigger: str | None = None
    condition: str | None = None
    action: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Triple:
    subject: str
    relation: str
    object: str
    triple_class: str  # backbone|auxiliary|linking|normalization
    csa: list[str]
    confidence: float
    source: str
    provenance: str = ""

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.subject, self.relation, self.object)


def classify_function(sentence: str) -> str:
    proc = bool(PROCEDURAL_CUES.search(sentence))
    decl = bool(DECLARATIVE_CUES.search(sentence))
    if proc and not decl:
        return "procedural"
    if "if " in sentence.lower() or "when " in sentence.lower() or "causes" in sentence.lower():
        return "procedural"
    return "declarative"


def find_entities(sentence: str) -> list[CSA]:
    s = sentence.lower()
    found: list[CSA] = []
    # longer phrases first
    for phrase, (t, e) in sorted(LEXICON.items(), key=lambda kv: -len(kv[0])):
        if phrase in s:
            csa = CSA(t, e)
            if csa not in found:
                found.append(csa)
    return found


def to_ir(sentence: str) -> SemanticIR:
    func = classify_function(sentence)
    ents = find_entities(sentence)
    primary = ents[0] if ents else CSA("FlowStage", "Unknown")
    ir = SemanticIR(sentence=sentence, function=func, csa=primary, entities=ents)
    low = sentence.lower()
    if func == "procedural":
        if "if " in low:
            ir.condition = sentence
        if "cause" in low:
            ir.trigger = "causal"
        if any(a in low for a in ("insert", "upsize", "mitigate", "widen", "adding")):
            ir.action = sentence
    else:
        ir.attributes["definitional"] = True
    return ir


def hierarchical_extract(ir: SemanticIR, source: str = "auto") -> list[Triple]:
    """Map IR → T_B / T_A / T_L / T_N following ChipMind's four-class schema."""
    triples: list[Triple] = []
    ents = ir.entities
    csa_list = [ir.csa.type, ir.csa.entity]
    s_low = ir.sentence.lower()

    def add(subj: str, rel: str, obj: str, cls: str, conf: float = 0.7) -> None:
        triples.append(
            Triple(
                subject=subj,
                relation=rel,
                object=obj,
                triple_class=cls,
                csa=csa_list,
                confidence=conf,
                source=source,
                provenance=ir.sentence[:160],
            )
        )

    # Normalization: abbreviations already in lexicon share canonical forms
    for e in ents:
        if e.entity == "Clock_Tree_Synthesis" and "cts" in s_low:
            add("CTS", "same_as", "Clock_Tree_Synthesis", "normalization", 0.95)

    # Causal backbone: A causes B
    if "cause" in s_low and len(ents) >= 2:
        add(ents[0].entity, "causes", ents[1].entity, "backbone", 0.75)
        # auxiliary qualifier
        add(ents[0].entity, "when", ents[1].entity, "auxiliary", 0.6)
        add(ents[0].entity, "qualified_by", ents[1].entity, "linking", 0.6)

    # Detects
    if "detect" in s_low and len(ents) >= 2:
        add(ents[0].entity, "detects", ents[1].entity, "backbone", 0.8)

    # Mitigates
    if "mitigate" in s_low and len(ents) >= 2:
        add(ents[0].entity, "mitigates", ents[1].entity, "backbone", 0.8)

    # Flow precedes (declarative sequence words)
    if any(w in s_low for w in ("before", "after", "then")) and len(ents) >= 2:
        if "before" in s_low:
            add(ents[0].entity, "typically_before", ents[1].entity, "auxiliary", 0.65)
        if "after" in s_low:
            add(ents[0].entity, "typically_after", ents[1].entity, "auxiliary", 0.65)

    # Action mitigations for setup/hold language
    if "setup" in s_low and ("buffer" in s_low or "upsize" in s_low):
        add("Buffer_Insertion_or_Upsize", "mitigates", "Setup_Violation", "backbone", 0.8)
    if "hold" in s_low and "buffer" in s_low:
        add("Hold_Buffer_Insertion", "mitigates", "Hold_Violation", "backbone", 0.8)

    # Soft causal: "too high ... reports congestion"
    if "congestion" in s_low and "density" in s_low and len(ents) >= 2:
        dens = next((e for e in ents if "Density" in e.entity), None)
        cong = next((e for e in ents if "Congestion" in e.entity), None)
        if dens and cong:
            add(dens.entity, "causes", cong.entity, "backbone", 0.7)

    return triples


def extract_document(sentences: list[str], doc_id: str) -> dict[str, Any]:
    irs = [to_ir(s) for s in sentences]
    triples: list[Triple] = []
    for ir in irs:
        triples.extend(hierarchical_extract(ir, source=f"auto:{doc_id}"))
    return {
        "doc_id": doc_id,
        "irs": [asdict(ir) for ir in irs],
        "triples": [asdict(t) for t in triples],
    }
