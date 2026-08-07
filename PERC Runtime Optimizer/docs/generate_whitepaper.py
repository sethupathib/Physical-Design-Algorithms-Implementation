#!/usr/bin/env python3
"""Generate the PERC Runtime Optimizer white paper PDF."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "PERC_Runtime_Optimizer_Whitepaper.pdf"


def styles():
    base = getSampleStyleSheet()
    s = {
        "title": ParagraphStyle(
            "WPTitle",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "WPSub",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#333333"),
            spaceAfter=6,
        ),
        "meta": ParagraphStyle(
            "WPMeta",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"),
            spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "WPH1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "h2": ParagraphStyle(
            "WPH2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#222222"),
        ),
        "h3": ParagraphStyle(
            "WPH3",
            parent=base["Heading3"],
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "WPBody",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10.5,
            leading=14.5,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "WPBullet",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10.5,
            leading=14,
            leftIndent=12,
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "WPCode",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            backColor=colors.HexColor("#f4f4f4"),
            borderPadding=6,
            spaceBefore=6,
            spaceAfter=10,
        ),
        "caption": ParagraphStyle(
            "WPCap",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=12,
            textColor=colors.HexColor("#333333"),
        ),
        "toc": ParagraphStyle(
            "WPTOC",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=16,
            leftIndent=10,
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "WPFooter",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
        ),
    }
    return s


def table(data, col_widths=None):
    # Wrap cells as paragraphs for long text
    body = styles()["body"]
    cell_style = ParagraphStyle(
        "Cell",
        parent=body,
        fontSize=8.5,
        leading=11,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    header_style = ParagraphStyle(
        "CellH",
        parent=cell_style,
        fontName="Times-Bold",
        fontSize=8.5,
    )
    wrapped = []
    for r_i, row in enumerate(data):
        wrow = []
        for cell in row:
            st = header_style if r_i == 0 else cell_style
            wrow.append(Paragraph(str(cell), st))
        wrapped.append(wrow)
    t = Table(wrapped, colWidths=col_widths, hAlign="CENTER")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#666666")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ]
        )
    )
    return t


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(x, style), leftIndent=8, bulletColor=colors.black) for x in items],
        bulletType="bullet",
        start="•",
        leftIndent=15,
        bulletFontName="Times-Roman",
        bulletFontSize=10,
    )


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Times-Roman", 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawCentredString(
        letter[0] / 2,
        0.55 * inch,
        f"PERC Runtime Optimizer White Paper  |  Page {doc.page}",
    )
    canvas.restoreState()


def build():
    s = styles()
    story = []

    # ----- Title page -----
    story.append(Spacer(1, 1.6 * inch))
    story.append(Paragraph("Accelerating Programmable Electrical<br/>Rules Checking (PERC) in Physical Design", s["title"]))
    story.append(Spacer(1, 0.25 * inch))
    story.append(
        Paragraph(
            "A White Paper on Reliability Signoff Bottlenecks,<br/>Synthetic Modeling, and Runtime Optimization Strategies",
            s["subtitle"],
        )
    )
    story.append(Spacer(1, 0.45 * inch))
    story.append(Paragraph("Physical Design Algorithms Implementation", s["meta"]))
    story.append(Paragraph("Companion artifact: C++17 <i>PERC Runtime Optimizer</i> project", s["meta"]))
    story.append(Paragraph("August 2026", s["meta"]))
    story.append(Spacer(1, 0.6 * inch))
    story.append(
        Paragraph(
            "<b>Abstract.</b> Programmable Electrical Rules Checking (PERC) verifies "
            "integrated-circuit reliability constraints—especially electrostatic discharge (ESD) "
            "related rules—that neither design-rule checking (DRC) nor layout-versus-schematic (LVS) "
            "can fully express. In modern SoC signoff, PERC wall-clock time is dominated less by "
            "topology identification itself than by parasitic resistance extraction and subsequent "
            "point-to-point (P2P) resistance and current-density (CD) analysis, often repeated after "
            "every engineering change order (ECO). This white paper explains the industrial PERC "
            "flow, clarifies cost centers (including metal fill and RC extraction upstream of PERC), "
            "and presents an educational C++17 framework that models netlist-level PERC checks and "
            "graph-based P2P/CD solves on synthetic hierarchical designs. We evaluate baseline, "
            "region-of-interest (ROI), hierarchical, parallel, incremental, and combined optimized "
            "engines, and discuss how the measured levers map to production reliability platforms "
            "such as Siemens Calibre PERC and Synopsys IC Validator PERC.",
            s["body"],
        )
    )
    story.append(PageBreak())

    # ----- TOC -----
    story.append(Paragraph("Contents", s["h1"]))
    toc_items = [
        "1. Introduction",
        "2. Background: PERC in the Physical Verification Stack",
        "3. Anatomy of an ESD-Oriented PERC Flow",
        "4. Where Runtime Actually Goes",
        "5. Upstream Cost Centers: Metal Fill and RC Extraction",
        "6. The PERC Runtime Optimizer Project",
        "7. Synthetic Data Model (What It Is — and Is Not)",
        "8. Implemented Checks and Engines",
        "9. Experimental Methodology and Results",
        "10. Interpretation and Guidance for Practitioners",
        "11. Limitations and Threats to Validity",
        "12. Future Work",
        "13. Conclusion",
        "References",
        "Appendix A. Repository Layout and Reproducibility",
    ]
    for item in toc_items:
        story.append(Paragraph(item, s["toc"]))
    story.append(PageBreak())

    # ----- 1 -----
    story.append(Paragraph("1. Introduction", s["h1"]))
    story.append(
        Paragraph(
            "As process nodes advance and SoC integration grows, electrical reliability constraints "
            "have become first-class signoff requirements alongside timing, power, and geometric DRC. "
            "Foundries and design houses encode ESD, electrical overstress (EOS), multi-domain voltage "
            "rules, and related methodology checks in programmable rule decks. The resulting verification "
            "class is widely known as <b>Programmable Electrical Rules Checking (PERC)</b>.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "Unlike classical DRC (geometry-centric) and LVS (device/net correspondence), PERC combines "
            "<i>connectivity intent</i> with, for several check families, <i>layout parasitics</i>. That "
            "hybrid nature makes PERC powerful—and expensive. Design teams routinely report multi-hour "
            "to multi-day turnaround for full-chip reliability regressions, especially when ECOs force "
            "repeated extraction and rechecking.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "This white paper has three goals:",
            s["body"],
        )
    )
    story.append(
        bullets(
            [
                "<b>Explain</b> PERC’s role, check families, and industrial data flow in precise terms.",
                "<b>Disambiguate</b> expensive operations: ESD path identification versus P2P/CD, and "
                "upstream metal-fill / RC-extraction costs that are often conflated with “PERC runtime.”",
                "<b>Document</b> an open C++17 educational project that implements PERC-like checks and "
                "runtime optimizations on synthetic netlists, with measured results and clear limitations.",
            ],
            s["bullet"],
        )
    )

    # ----- 2 -----
    story.append(Paragraph("2. Background: PERC in the Physical Verification Stack", s["h1"]))
    story.append(Paragraph("2.1 What PERC is", s["h2"]))
    story.append(
        Paragraph(
            "PERC is a method for checking reliability issues of IC designs that cannot be checked with "
            "DRC or LVS alone. Rules involve connectivity and netlist information and must be "
            "customizable from design to design—hence <i>programmable</i>. Commercial platforms include "
            "Siemens Calibre PERC and Synopsys IC Validator PERC.",
            s["body"],
        )
    )
    story.append(Paragraph("2.2 The four check families", s["h2"]))
    story.append(
        table(
            [
                ["Family", "Primary inputs", "Typical intent", "Dominant cost"],
                [
                    "Netlist checks",
                    "Schematic or LVS-extracted netlist",
                    "Clamp presence, floating gates, EOS / level-shifter topology, domain rules",
                    "Graph traversal / rule evaluation over large netlists",
                ],
                [
                    "Netlist-driven layout (LDL/NDL)",
                    "Netlist + GDS/OASIS",
                    "Voltage-aware spacing and geometry on connectivity-selected regions",
                    "ROI identification + geometry operations",
                ],
                [
                    "Current density (CD)",
                    "Layout + R-extraction + assumed ESD current",
                    "Metal can carry discharge current without EM / thermal failure",
                    "Parasitic R mesh construction and path/current analysis",
                ],
                [
                    "Point-to-point (P2P) resistance",
                    "Layout + R-extraction",
                    "Discharge path resistance low enough that current prefers the clamp path",
                    "Many source→sink resistance queries on resistor networks",
                ],
            ],
            col_widths=[1.15 * inch, 1.45 * inch, 2.1 * inch, 1.9 * inch],
        )
    )
    story.append(Paragraph("Table 1. PERC check families and primary cost drivers.", s["caption"]))

    story.append(Paragraph("2.3 Placement in the signoff timeline", s["h2"]))
    story.append(
        Paragraph(
            "PERC typically runs after the design is LVS-clean (for layout-aware checks), though "
            "schematic-only netlist checks can start earlier. It sits alongside DRC, LVS, fill, "
            "extraction, timing, and IR/EM signoff. Because reliability failures can escape functional "
            "test patterns, PERC is treated as a gate for tapeout on many products (especially "
            "automotive, industrial, and high-reliability segments).",
            s["body"],
        )
    )

    # ----- 3 -----
    story.append(Paragraph("3. Anatomy of an ESD-Oriented PERC Flow", s["h1"]))
    story.append(
        Paragraph(
            "ESD applications exercise all four check families. A representative flow is:",
            s["body"],
        )
    )
    flow = """Netlist / LVS extract
        │
        ▼
 Netlist analysis engine  ──► clamp / diode / rail topology errors
        │
        ▼
 Identify ESD paths & ROIs (pad → clamp → rail / ground)
        │
        ▼
 R-extract (ideally only) marked nets / polygons
        │
        ├──► P2P resistance (pad–clamp, clamp–rail, …)
        └──► Current-density along discharge path"""
    story.append(Preformatted(flow, s["code"]))
    story.append(
        Paragraph(
            "The netlist analysis engine is the programmable core: it decides which structures exist, "
            "which paths are critical, and which layout regions must be examined. Layout-heavy checks "
            "then depend on parasitic resistance models of those regions.",
            s["body"],
        )
    )

    # ----- 4 -----
    story.append(Paragraph("4. Where Runtime Actually Goes", s["h1"]))
    story.append(Paragraph("4.1 The common misconception", s["h2"]))
    story.append(
        Paragraph(
            "A frequent question is whether <b>ESD path identification</b> or <b>P2P/CD checking</b> "
            "dominates runtime. In production flows, path identification is usually a comparatively "
            "cheap connectivity/graph analysis step. The expensive work is almost always:",
            s["body"],
        )
    )
    story.append(
        bullets(
            [
                "Building or updating a parasitic <b>R</b> (and often C) network for relevant metals, and",
                "Solving many <b>P2P</b> queries and <b>CD</b> path/current analyses on that network.",
            ],
            s["bullet"],
        )
    )
    story.append(
        Paragraph(
            "Path identification still matters enormously for <i>scoping</i>: a poor ROI causes "
            "over-extraction and over-checking; a correct ROI is what makes LDL-style acceleration possible.",
            s["body"],
        )
    )

    story.append(Paragraph("4.2 Scaling pressures at SoC size", s["h2"]))
    story.append(
        bullets(
            [
                "Millions to billions of devices/nets in the connectivity graph.",
                "Hundreds to thousands of IO pads, each inducing multiple path endpoints.",
                "Naïve flows that flatten hierarchy and re-extract the full chip after every ECO.",
                "Deep, context-aware rule decks (voltage propagation, multi-power domains).",
            ],
            s["bullet"],
        )
    )

    # ----- 5 -----
    story.append(Paragraph("5. Upstream Cost Centers: Metal Fill and RC Extraction", s["h1"]))
    story.append(
        Paragraph(
            "When engineers say “PERC is slow,” they often measure an umbrella regression that includes "
            "steps that are logically upstream of the PERC rule engine. Two of the most important are "
            "metal fill and parasitic extraction.",
            s["body"],
        )
    )
    story.append(Paragraph("5.1 Metal fill (dummy metal)", s["h2"]))
    story.append(
        Paragraph(
            "Dummy metal fill is inserted to satisfy density and manufacturing rules. It is "
            "geometry-heavy: large numbers of fill shapes are created, legalized, and verified. Fill "
            "can dominate physical-verification runtime on its own and also <b>changes parasitics</b>, "
            "so extraction and P2P/CD results are fill-dependent. Fill is therefore both a direct "
            "runtime cost and an indirect multiplier on PERC-related extract/check cost.",
            s["body"],
        )
    )
    story.append(Paragraph("5.2 R and C extraction", s["h2"]))
    story.append(
        Paragraph(
            "Tools such as StarRC (and equivalents) build resistive (and capacitive) models of "
            "interconnect from layout. For ESD P2P/CD, resistance accuracy on discharge paths is "
            "critical. Full-chip extract is often one of the largest wall-clock components in the "
            "reliability loop. Best practice is netlist-driven / ROI extract: mark ESD-critical nets "
            "and extract only what P2P/CD need—subject to accuracy requirements.",
            s["body"],
        )
    )
    story.append(Paragraph("5.3 How this paper’s artifact relates", s["h2"]))
    story.append(
        Paragraph(
            "<b>Important clarification:</b> the companion C++ project does <i>not</i> implement metal "
            "fill or a layout extractor. It assumes an already-available resistive model (an abstract "
            "graph) and focuses on check/solve and reuse strategies. Section 7 details the synthetic "
            "data model so this boundary is unambiguous.",
            s["body"],
        )
    )

    story.append(
        table(
            [
                ["Industrial step", "Modeled in C++ project?", "Notes"],
                ["GDS/OASIS layout", "No", "No polygons, layers, or fill geometries"],
                ["Metal fill insertion", "No", "Acknowledged as major real-world cost"],
                ["RC extraction (StarRC-class)", "Abstracted", "Pre-baked weighted RGraph edges"],
                ["Netlist PERC rules", "Yes", "Clamps, floating gates, etc."],
                ["P2P / CD solves", "Yes (graph)", "Dijkstra / path walks on RGraph"],
                ["Incremental metadata reuse", "Yes", "Scope fingerprints + ECO fast path"],
            ],
            col_widths=[2.0 * inch, 1.5 * inch, 3.1 * inch],
        )
    )
    story.append(Paragraph("Table 2. Industrial steps versus project coverage.", s["caption"]))

    # ----- 6 -----
    story.append(Paragraph("6. The PERC Runtime Optimizer Project", s["h1"]))
    story.append(
        Paragraph(
            "The repository project <b>PERC Runtime Optimizer</b> is a C++17 educational framework. "
            "Its purpose is not to replace Calibre or IC Validator, but to make PERC’s algorithmic "
            "bottlenecks tangible: one can generate a hierarchical synthetic design, run baseline "
            "checks, and compare optimized engines with wall-clock measurements.",
            s["body"],
        )
    )
    story.append(Paragraph("6.1 Design goals", s["h2"]))
    story.append(
        bullets(
            [
                "Faithful <i>structure</i> of PERC stages (netlist analysis → ROI → P2P/CD).",
                "Measurable optimization levers used in industry: ROI pruning, hierarchy, parallelism, incremental reuse.",
                "Zero dependency on proprietary runsets or licensed layout databases.",
                "Reproducible CLI benchmarks and a small unit-test suite.",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("6.2 Non-goals", s["h2"]))
    story.append(
        bullets(
            [
                "Foundry signoff accuracy or rule-deck compatibility.",
                "GDS parsing, DRC, LVS, or fill engines.",
                "Full field-solver or SPEF/DSPF-quality extraction.",
            ],
            s["bullet"],
        )
    )

    # ----- 7 -----
    story.append(Paragraph("7. Synthetic Data Model (What It Is — and Is Not)", s["h1"]))
    story.append(Paragraph("7.1 Not a GDS", s["h2"]))
    story.append(
        Paragraph(
            "The synthetic stimulus is <b>not</b> a GDS or OASIS file. There is no dummy-metal-filled "
            "layout. Instead, <font face='Courier'>generate_design()</font> constructs:",
            s["body"],
        )
    )
    story.append(
        bullets(
            [
                "<b>A hierarchical netlist:</b> IO pads, optional ESD clamps (some intentionally missing), "
                "MOSFETs/diodes per block, local and global supplies, and interface buffers.",
                "<b>An abstract resistor graph (<font face='Courier'>RGraph</font>):</b> undirected weighted "
                "edges among nets that stand in for interconnect parasitics that a real extractor would produce.",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("7.2 Why this abstraction", s["h2"]))
    story.append(
        Paragraph(
            "P2P and CD in industry consume extracted R networks. By generating a resistor graph "
            "directly, the project isolates the <i>query/solve</i> and <i>reuse</i> problems without "
            "requiring a layout database. This is appropriate for algorithm study; it is insufficient "
            "for predicting absolute industrial runtimes, where fill + extract often dominate.",
            s["body"],
        )
    )
    story.append(Paragraph("7.3 ECO mutation", s["h2"]))
    story.append(
        Paragraph(
            "To study incremental checking, <font face='Courier'>mutate_eco()</font> touches MOSFET drain "
            "nets inside a limited number of blocks (default: one block). Untouched blocks keep stable "
            "fingerprints, enabling metadata hits—analogous to commercial metadata reuse across ECO cycles.",
            s["body"],
        )
    )

    # ----- 8 -----
    story.append(Paragraph("8. Implemented Checks and Engines", s["h1"]))
    story.append(Paragraph("8.1 Checks", s["h2"]))
    story.append(
        table(
            [
                ["Check", "Rule ID(s)", "Method sketch"],
                [
                    "ESD clamp presence",
                    "ESD_CLAMP_MISSING",
                    "Every pad net must attach to an EsdClamp device",
                ],
                [
                    "Floating gates",
                    "FLOATING_GATE",
                    "MOSFET gates with zero non-gate drivers (indexed writer map)",
                ],
                [
                    "P2P resistance",
                    "P2P_RESISTANCE_HIGH / P2P_PATH_MISSING",
                    "Dijkstra shortest resistive path pad→VSS and pad→VDD vs limit",
                ],
                [
                    "Current density (simplified)",
                    "CURRENT_DENSITY",
                    "Along pad→VSS shortest path, flag high I·R edge stress proxy",
                ],
            ],
            col_widths=[1.5 * inch, 2.2 * inch, 2.9 * inch],
        )
    )
    story.append(Paragraph("Table 3. Implemented PERC-like checks.", s["caption"]))

    story.append(Paragraph("8.2 Engines", s["h2"]))
    story.append(
        table(
            [
                ["Engine", "Strategy"],
                ["baseline", "Full-chip: all rules, every time"],
                ["roi", "Prune floating-gate scope toward ESD-relevant devices"],
                ["hierarchical", "Chip-level ESD/P2P/CD; per-block FG with shared writer index"],
                ["parallel", "std::async workers over pad-pair P2P/CD slices"],
                ["incremental", "MetadataStore keyed by scope fingerprint; ECO skips untouched blocks"],
                ["optimized", "ESD-stable chip cache + parallel P2P/CD + hierarchical FG reuse"],
            ],
            col_widths=[1.4 * inch, 5.2 * inch],
        )
    )
    story.append(Paragraph("Table 4. Runtime engines.", s["caption"]))

    story.append(Paragraph("8.3 Metadata and fingerprints", s["h2"]))
    story.append(
        Paragraph(
            "Incremental reuse stores per-scope results keyed by a structural fingerprint. Chip-level "
            "ESD/P2P/CD uses an <b>ESD-stable fingerprint</b> (pads, rails, clamp/IO devices and pad–rail "
            "R edges) so core-logic ECOs do not spuriously invalidate chip ESD results. Block scopes "
            "fingerprint local nets/devices. When <font face='Courier'>touched_blocks</font> is known, "
            "untouched blocks reuse the latest cached result without re-hashing.",
            s["body"],
        )
    )

    # ----- 9 -----
    story.append(Paragraph("9. Experimental Methodology and Results", s["h1"]))
    story.append(Paragraph("9.1 Setup", s["h2"]))
    story.append(
        Paragraph(
            "Measurements below were taken from the project CLI on a Linux environment using the "
            "default <font face='Courier'>--bench</font> configuration unless noted: 256 pads, 16 "
            "blocks, 500 devices/block (~8.8k devices, ~16.7k nets, ~22.8k R-edges), compiled with "
            "<font face='Courier'>g++ -O2 -pthread</font>. Absolute times are machine-specific; "
            "ratios are the intended takeaway.",
            s["body"],
        )
    )

    story.append(Paragraph("9.2 Stage-level profile (baseline internals)", s["h2"]))
    story.append(
        Paragraph(
            "Instrumenting individual checks on the bench design (averaged) yields the approximate "
            "breakdown in Table 5. In this <i>extract-free</i> model, netlist floating-gate scanning "
            "and graph P2P/CD are both visible; ESD ROI identification remains a minority cost—consistent "
            "with the industrial claim that path ID is not the primary bottleneck once extraction exists.",
            s["body"],
        )
    )
    story.append(
        table(
            [
                ["Stage", "Avg time (s)", "Share"],
                ["ESD ROI / path ID (net scan)", "0.0010", "~9%"],
                ["ESD clamp netlist check", "0.0001", "~1%"],
                ["Floating-gate netlist check", "0.0056", "~47%"],
                ["P2P resistance (Dijkstra)", "0.0032", "~27%"],
                ["Current-density path walks", "0.0018", "~15%"],
                ["Total (sum of stages)", "0.0118", "100%"],
            ],
            col_widths=[2.6 * inch, 1.5 * inch, 1.2 * inch],
        )
    )
    story.append(Paragraph("Table 5. Stage profile on synthetic bench design (no layout extract).", s["caption"]))
    story.append(
        Paragraph(
            "Note: floating-gate share is inflated by the synthetic stimulus, which intentionally "
            "leaves many gate nets without drivers to stress the checker. In real netlists, FG cost "
            "is typically smaller relative to extract+P2P/CD.",
            s["body"],
        )
    )

    story.append(Paragraph("9.3 Engine comparison", s["h2"]))
    story.append(
        table(
            [
                ["Engine", "Time (s)", "Observations"],
                ["baseline", "0.0120", "Full recompute reference"],
                ["roi", "0.0141", "Similar quality; prune overhead can outweigh savings at this size"],
                ["hierarchical", "0.0116", "Shared FG index; comparable to baseline cold"],
                ["parallel", "0.0079", "~1.5× vs baseline on pad-pair heavy work (4 workers)"],
                ["incremental (cold)", "0.0746", "Fingerprint+populate cache costs more when cold"],
                ["incremental (warm)", "0.0007", "~100× vs cold incremental; much faster than baseline when unchanged"],
                ["optimized (warm)", "0.0007", "Same warm-cache benefit"],
            ],
            col_widths=[1.7 * inch, 1.1 * inch, 3.8 * inch],
        )
    )
    story.append(Paragraph("Table 6. Engine wall-clock on unchanged design (bench config).", s["caption"]))

    story.append(Paragraph("9.4 ECO incremental recheck", s["h2"]))
    story.append(
        Paragraph(
            "After a 5% MOSFET-drain ECO confined to a single block:",
            s["body"],
        )
    )
    story.append(
        table(
            [
                ["Engine", "Time (s)", "Cache behavior"],
                ["baseline", "0.0104", "Full recompute"],
                ["incremental", "0.0034", "16 hits / 1 miss (recheck touched block only)"],
                ["optimized", "0.0031", "Same reuse pattern + parallel chip path when needed"],
            ],
            col_widths=[1.5 * inch, 1.2 * inch, 3.9 * inch],
        )
    )
    story.append(Paragraph("Table 7. Post-ECO recheck (one touched block).", s["caption"]))
    story.append(
        Paragraph(
            "Violation counts matched between baseline and incremental/optimized after ECO "
            "(7449 total), indicating the fast path did not drop the newly introduced floating-gate "
            "effect in the touched block.",
            s["body"],
        )
    )

    # ----- 10 -----
    story.append(Paragraph("10. Interpretation and Guidance for Practitioners", s["h1"]))
    story.append(
        Paragraph(
            "Even though absolute times in the toy model are milliseconds, the <b>shape</b> of the "
            "results matches industrial practice:",
            s["body"],
        )
    )
    story.append(
        bullets(
            [
                "<b>Do not over-invest in speeding path ID alone</b> if extract+P2P/CD dominate your traces.",
                "<b>Invest in ROI / LDL:</b> mark ESD nets early; extract and check only what those paths need.",
                "<b>Treat ECO as the common case:</b> metadata reuse and hierarchical invalidation beat heroic cold-run constant-factor tuning.",
                "<b>Parallelize embarrassingly partitioned P2P pairs</b> across pads/domains once the R model exists.",
                "<b>Account for fill and extract in program plans:</b> a “PERC project” that ignores them will miss the real critical path.",
            ],
            s["bullet"],
        )
    )
    story.append(
        Paragraph(
            "For teams building internal accelerators or research prototypes, a useful layering is: "
            "(1) connectivity/ROI engine, (2) extract subset manager, (3) P2P/CD solver farm, "
            "(4) persistent metadata store keyed by hierarchical scopes.",
            s["body"],
        )
    )

    # ----- 11 -----
    story.append(Paragraph("11. Limitations and Threats to Validity", s["h1"]))
    story.append(
        bullets(
            [
                "<b>No layout database:</b> cannot reproduce geometry-limited LDL or fill interactions.",
                "<b>No real extractor:</b> RGraph edges are synthetic; Dijkstra on a modest mesh understates industrial solve cost.",
                "<b>Simplified CD:</b> I·R proxy is pedagogical, not a current-density field model.",
                "<b>Synthetic FG population:</b> skews stage profiles versus production netlists.",
                "<b>Single-machine pthread scaling:</b> does not model distributed farm / license / disk bottlenecks.",
                "<b>Not signoff-equivalent:</b> results must not be used as reliability certification evidence.",
            ],
            s["bullet"],
        )
    )

    # ----- 12 -----
    story.append(Paragraph("12. Future Work", s["h1"]))
    story.append(
        bullets(
            [
                "<b>Synthetic layout + fill model:</b> tile-based metals with dummy fill insertion timed separately from checks.",
                "<b>Extract emulator:</b> build R (and C) from the synthetic layout with configurable accuracy/runtime tradeoffs.",
                "<b>Richer ESD topologies:</b> secondary clamps, rail clamps, diode chains, multi-domain crossers.",
                "<b>Voltage-aware LDL checks:</b> propagate domain voltages and trigger geometry queries on ROIs.",
                "<b>Persistent on-disk metadata</b> and hierarchical invalidation integrated with a mock P&amp;R ECO stream.",
                "<b>GPU/batch shortest paths</b> for large pad-pair sets on huge resistor meshes.",
            ],
            s["bullet"],
        )
    )

    # ----- 13 -----
    story.append(Paragraph("13. Conclusion", s["h1"]))
    story.append(
        Paragraph(
            "PERC is essential for catching ESD/EOS-class reliability issues outside the reach of DRC "
            "and LVS. Its runtime pain is real, but it is easy to mis-attribute. ESD path identification "
            "is necessary scaffolding; the dominant costs in production are typically parasitic "
            "extraction and P2P/CD analysis—often amplified by metal fill and by full-chip redo after ECO.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "The C++17 PERC Runtime Optimizer makes these ideas concrete with synthetic hierarchical "
            "netlists, graph-based P2P/CD, and engines that demonstrate ROI pruning, hierarchy, "
            "parallelism, and incremental metadata reuse. Warm-cache and ECO-local recheck show order-of-magnitude "
            "or multi-fold speedups in the model, mirroring the strategic importance of reuse in commercial "
            "reliability platforms. Extending the artifact toward fill and extraction would close the "
            "largest remaining gap between educational measurement and industrial wall-clock reality.",
            s["body"],
        )
    )

    # ----- References -----
    story.append(Paragraph("References", s["h1"]))
    refs = [
        "[1] Synopsys, “What is PERC (Programmable Electrical Rules Checking)?” Synopsys Glossary. "
        "https://www.synopsys.com/glossary/what-is-programmable-electrical-rules-checking.html",
        "[2] Synopsys, IC Validator Physical Verification Datasheet (PERC / NDC / MMC / CD / P2P capabilities).",
        "[3] Siemens EDA, “Advanced electrical rule checking in IC reliability verification,” Calibre PERC technical paper.",
        "[4] Siemens EDA, “Increase productivity by reusing metadata for signoff &amp; ECOs,” Calibre PERC metadata reuse paper.",
        "[5] eInfochips, “Understanding PERC: Definition and Applications for Reliable Design” (ESD, P2P, CD overview).",
        "[6] Industry practice notes on logic-driven layout (LDL), StarRC-class R-extraction for ESD paths, and dummy metal fill density flows "
        "(foundry design manuals; tool-specific user guides).",
    ]
    for r in refs:
        story.append(Paragraph(r, s["body"]))

    # ----- Appendix -----
    story.append(Paragraph("Appendix A. Repository Layout and Reproducibility", s["h1"]))
    story.append(
        Paragraph(
            "The project lives under <font face='Courier'>PERC Runtime Optimizer/</font> with headers in "
            "<font face='Courier'>include/</font>, sources in <font face='Courier'>src/</font>, tests in "
            "<font face='Courier'>tests/</font>, and concept notes in <font face='Courier'>docs/</font>.",
            s["body"],
        )
    )
    story.append(
        Preformatted(
            "cd \"PERC Runtime Optimizer\"\n"
            "make -j\n"
            "make test\n"
            "./perc_optimizer --bench --eco --workers $(nproc)\n"
            "# regenerate this PDF:\n"
            "python3 docs/generate_whitepaper.py",
            s["code"],
        )
    )
    story.append(
        Paragraph(
            "Primary sources: <font face='Courier'>design.*</font> (netlist/RGraph), "
            "<font face='Courier'>generator.*</font> (synthetic design + ECO), "
            "<font face='Courier'>checks.*</font> (rules), <font face='Courier'>engine.*</font> "
            "(baseline/optimized runners), <font face='Courier'>metadata.*</font> (cache).",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "This white paper is intended as an educational and engineering companion document for the "
            "open repository. It is not a foundry signoff guide.",
            s["body"],
        )
    )

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Accelerating PERC in Physical Design",
        author="Physical Design Algorithms Implementation",
        subject="PERC Runtime Optimizer White Paper",
    )
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
