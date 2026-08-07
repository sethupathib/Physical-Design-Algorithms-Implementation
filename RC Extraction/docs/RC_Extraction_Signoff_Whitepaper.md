---
title: "RC Extraction for Physical Design Signoff"
subtitle: "From GDS Geometry to SPEF — Theory, Practice, and a Teaching Implementation"
author: "Physical Design Algorithms Implementation"
date: "2026"
---

# Abstract

Resistance–capacitance (RC) extraction is the bridge between finished layout geometry and timing / signal-integrity signoff. This white paper explains how interconnect parasitics are obtained from GDS-derived shapes (not from a logical netlist alone), how foundry technology files parameterize R and C, how extracted networks are emitted as SPEF for static timing analysis (STA), and how a transparent C++ teaching extractor implements the same dataflow at toy scale. The goal is deep intuition for physical-design engineers and students—not a replacement for commercial extractors such as StarRC, Quantus, or Calibre xRC.

**Keywords:** RC extraction, parasitic extraction, SPEF, GDSII, signoff, STA, Elmore delay, physical design

---

# 1. Introduction

After place-and-route, a chip exists as polygonal geometry on process layers—metals, vias, polysilicon, diffusion—streamed typically as GDSII or OASIS. Signoff timing does not consume those polygons directly. It consumes:

1. A **logical netlist** (devices and connectivity), and  
2. A **parasitic annotation** (R, C, sometimes L) that models the wires connecting those devices.

The second artifact is the output of **parasitic RC extraction**. A common confusion is to say “extract the netlist from GDS” and mean both LVS connectivity *and* parasitics. They are related but distinct:

| Step | Question answered | Primary output |
|------|-------------------|----------------|
| LVS / device extraction | Are the transistors wired as intended? | Logical netlist + connectivity |
| Parasitic RC extraction | What delay, noise, and IR drop do those wires cause? | SPEF / DSPF / SPF with R & C |

This paper focuses on interconnect RC: how geometry plus a process stack become resistors and capacitors, how those elements form π-models and trees, and how SPEF carries them into PrimeTime, Tempus, OpenSTA, and related tools.

---

# 2. Signoff Context

## 2.1 Where extraction sits in the flow

```
RTL → Synthesis → Place & Route → GDSII / OASIS
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                   LVS / DRC                  Parasitic Extraction
              (devices + nets OK?)             (R, C from geometry)
                         │                         │
                         └────────────┬────────────┘
                                      ▼
                                SPEF (+ .lib)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
                   STA          Crosstalk / SI       EM / IR
              (setup / hold)   (noise, delay)     (power grid)
```

Extraction is therefore a **signoff enabler**: without correlated parasitics, STA is guessing.

## 2.2 Corners and MCMM

Foundries provide multiple extraction corners (e.g. Cmax/Cmin, RCmax/RCmin, typical). Signoff STA runs multi-corner multi-mode (MCMM) with matching SPEF per corner. Temperature and voltage further scale resistance (and sometimes capacitance). A teaching extractor may use a single synthetic techfile; production signoff never does.

## 2.3 What “good enough” means

| Mode | Method | Role |
|------|--------|------|
| Rule-based / pattern | Foundry lookup tables | Full-chip digital, fast |
| 2.5D analytical | Formulas + tables | Transparent, medium accuracy |
| 3D field solver | Maxwell on mesh/voxels | Critical nets, highest accuracy |

Industrial tools blend these. This white paper’s companion C++ project implements **transparent 2.5D analytical** models so every term is visible.

---

# 3. Geometry: What Is in the GDS?

GDSII is a hierarchical stream of polygons on named layers (MET1, VIA1, MET2, …). For interconnect RC, the extractor cares about:

1. **Conductor shapes** — metal / poly rectangles or rectilinear polygons  
2. **Via cuts** — shapes that stitch adjacent metal layers  
3. **Layer stack** — thickness, height above reference, dielectric  
4. **Connectivity** — shapes that touch (or are via-connected) belong to one **net**

A simplified three-metal stack:

```
        +--------------+     M3
   =====+==============+===  VIA2
   +----+----+    +----+--+  M2
===+=========+====+=======+= VIA1
+--+--+   +--+----+--+ +--+--+ M1
+-----+   +----------+ +-----+
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ substrate / ground reference
```

**Pin annotations** (from DEF / LEF / LVS) bind logical pin names (e.g. `U1:Z`) to geometric locations so SPEF can reference the same names STA expects.

---

# 4. Connectivity Extraction (LVS-like Wiring Graph)

Before R and C are computed, geometry must be partitioned into electrical nets.

## 4.1 Rules

1. Two metal shapes on the **same layer** that abut or overlap are shorted.  
2. A via that overlaps both its lower and upper metals stitches those metals into one net.  
3. Union-Find (disjoint set) is the standard algorithmic backbone.

## 4.2 Naming

Net names preferably come from designer / LVS labels on shapes or pins. Unlabeled connected components receive auto names (`net_0`, …).

## 4.3 Important clarification

> You do **not** extract R&C from the logical Verilog netlist.  
> You extract **connectivity from geometry**, then attach R&C computed from **geometry + process parameters**, and emit a parasitic netlist that *references* logical net/pin names.

---

# 5. Resistance Extraction

## 5.1 Sheet resistance

A thin film has sheet resistance \(R_s\) (Ω/□):

\[
R_s = \frac{\rho}{t}
\]

where \(\rho\) is resistivity and \(t\) is thickness. For a Manhattan rectangle of length \(L\) and width \(W\):

\[
R = R_s \cdot \frac{L}{W}
\]

“Squares” equals \(L/W\). A wire 10 µm long and 0.2 µm wide on a layer with \(R_s = 0.08\,\Omega/\square\) is 50 squares → \(R = 4\,\Omega\).

## 5.2 Via resistance

Each cut has a nearly fixed resistance \(R_{\mathrm{via}}\) from foundry tables. Parallel cuts:

\[
R_{\mathrm{via,eq}} = \frac{R_{\mathrm{via}}}{N}
\]

## 5.3 Segmentation

Long wires are fractured into segments (at bends, vias, taps, or max length) so the RC network can model distributed delay. Each segment becomes one or more resistors in the SPEF graph.

## 5.4 Effects ignored in a teaching model

Current crowding, barrier non-uniformity, temperature coefficients, and density-dependent \(R_s\) (slotting / cheesing) are omitted for clarity; production extractors and corners include them.

---

# 6. Capacitance Extraction

Capacitance is harder: every conductor couples through the dielectric to ground and to neighbors.

## 6.1 Dominant 2.5D terms

For a wire segment on layer \(i\):

**Area (plate) capacitance to ground / substrate**

\[
C_{\mathrm{area}} = c_{\mathrm{area}} \cdot W \cdot L
\quad\text{with}\quad
c_{\mathrm{area}} \approx \varepsilon / H
\]

**Fringe capacitance** (sidewall fields), often modeled as

\[
C_{\mathrm{fringe}} \approx c_{\mathrm{fringe}} \cdot L
\]

**Same-layer coupling** between parallel neighbors

\[
C_{\mathrm{coup}} \approx k \cdot T \cdot \frac{L_{\mathrm{overlap}}}{S}
\]

where \(T\) is metal thickness, \(S\) is spacing, and \(L_{\mathrm{overlap}}\) is facing-edge overlap. Far neighbors (large \(S\)) are pruned.

## 6.2 Total C and Miller treatment

\[
C_{\mathrm{total}} = C_{\mathrm{area}} + C_{\mathrm{fringe}} + \sum C_{\mathrm{coup}}
\]

In SPEF, coupling often appears as separate `CC` elements for SI analysis. STA may ground coupling with a Miller factor or keep CC for crosstalk delay.

## 6.3 Cross-layer coupling

M1 under M2 also couples; full-chip tools use pattern matching or field solvers. A minimal teaching extractor may omit vertical coupling and still teach the dominant same-layer effects.

---

# 7. RC Network Models

## 7.1 Lumped C (too crude for long nets)

```
Driver ── R_total ──●── Receiver
                    │
                 C_total
                    │
                   GND
```

## 7.2 π-model (common SPEF segment)

```
Driver ── R/2 ──●── R/2 ── Receiver
                │
               C
                │
               GND
```

(Equivalent educational form: full \(R\) between ends with \(C\) at the midpoint node.)

## 7.3 Distributed ladder

```
── R/n ──●── R/n ──●── … ──●──
         │         │         │
        C/n       C/n       C/n
```

## 7.4 Elmore delay

For an RC tree rooted at the driver:

\[
T_D(i) = \sum_{k \in \mathrm{path}(s \to i)} R_k \cdot C_{\mathrm{downstream}}(k)
\]

With \(R\) in ohms and \(C\) in fF, \(R\cdot C\) yields \(10^{-15}\) s = 0.001 ps. Elmore is a teaching stand-in for full STA; production timers use more accurate delay models driven by the same SPEF.

---

# 8. SPEF — What Signoff Tools Consume

**SPEF** (Standard Parasitic Exchange Format, IEEE 1481) annotates parasitics onto a netlist.

Minimal conceptual net:

```
*D_NET net_a 12.5
*CONN
*I inst1:Z O
*I inst2:A I
*CAP
1 net_a:1 0.006
2 net_a:2 0.006
*RES
1 net_a:1 net_a:2 25.0
*END
```

Coupling:

```
*CAP
3 net_a:1 net_b:1 0.002
```

Units (`*C_UNIT`, `*R_UNIT`, `*T_UNIT`) must match what STA expects. Name maps (`*NAME_MAP`) compress hierarchical names on large designs.

---

# 9. End-to-End Mental Model (GDS → SPEF)

```
GDS polygons
    │
    ├─1─ Flatten / expand hierarchy (or extract hierarchical)
    │
    ├─2─ Layer map: GDS layer/datatype → conductor / via / device
    │
    ├─3─ Geometric connectivity → NET IDs
    │
    ├─4─ Fracture nets into wire segments + via instances
    │
    ├─5─ R = Rs·L/W ; collect via R
    │
    ├─6─ Carea, Cfringe; neighbor search → Ccoup
    │
    ├─7─ Build RC graph (nodes at pins, vias, bends)
    │
    └─8─ Write SPEF → STA / SI / EM-IR
```

---

# 10. Teaching Implementation (C++ Companion Project)

The repository directory `RC Extraction/` contains a strict C++17 teaching extractor that mirrors the above dataflow without a full GDS parser or 3D field solver.

## 10.1 Pipeline modules

| Module | Role |
|--------|------|
| `techfile` | Synthetic 3-metal stack (\(R_s\), via R, \(c_{\mathrm{area}}\), fringe, coupling \(k\)) |
| `layout` | `.lay` format: METAL / VIA / PIN records (GDS stand-in) |
| `connectivity` | Union-Find abutment + via stitch |
| `resistance` | \(R_s L/W\), via \(R/N\) |
| `capacitance` | Area, fringe, same-layer coupling |
| `rc_network` | π-model, geometric node merge |
| `spef_writer` | IEEE-1481 subset |
| `elmore` | Mini timing on extracted trees |
| `extract` | Full pipeline driver |

## 10.2 Layout format (`.lay`)

```
NAME design
METAL <layer> <net> <name> <x0> <y0> <x1> <y1>
VIA   <layer> <net> <name> <x0> <y0> <x1> <y1>
PIN   <pin> <net> <layer> <I|O|B> <x> <y>
```

Coordinates are in micrometers.

## 10.3 Example results (via_stack)

A multi-layer route M1→VIA1→M2→VIA2→M3 yields:

- One electrically connected net after via stitching  
- Wire resistors from sheet resistance × squares  
- Via resistors (e.g. 5 Ω and 4 Ω single cuts)  
- Grounded area + fringe capacitance per metal rectangle  
- π-model network → SPEF `*D_NET` / `*RES` / `*CAP`  
- Elmore delays increasing along the path from driver to load  

Coupled parallel wires additionally emit `Cc` between victim and aggressor.

## 10.4 Build and run

```bash
cd "RC Extraction"
make && make test && make demos
./rcx_extract examples/via_stack.lay --elmore netx DRV:Z
```

---

# 11. What This Is Not

| Topic | Status in teaching project |
|-------|----------------------------|
| Full GDSII / OASIS parser | Not included (use `.lay`) |
| Device (transistor) extraction | Not included |
| 3D field solver | Not included |
| Temperature / density corners | Single synthetic tech |
| Inductance | Not modeled |
| Commercial correlation | Educational only |

The physics and dataflow are the same class of ideas used in StarRC, Quantus, and Calibre xRC; the scale, pattern libraries, and signoff correlation are not.

---

# 12. Practical Signoff Takeaways

1. **Geometry + techfile = parasitics.** The logical netlist alone cannot yield accurate interconnect delay.  
2. **LVS connectivity ≠ RC extraction**, but they share the geometric connectivity graph.  
3. **R is local; C is environmental.** Resistance is mostly the wire’s own \(L/W\); capacitance depends on neighbors and dielectrics.  
4. **SPEF is the contract** between extraction and STA/SI.  
5. **Corners matter.** One SPEF is never enough for modern signoff.  
6. **Selection beats volume.** More P&R trials without scored parasitics / QoR only amplify debug noise—extraction quality and interpretable reports reduce pain.

---

# 13. Conclusion

RC extraction translates mask-ready geometry into the electrical reality that timing signoff must believe. Understanding sheet resistance, via arrays, area/fringe/coupling capacitance, π-models, and SPEF is foundational for anyone closing chips or building methodology around PD/STA/signoff logs.

The companion C++ project in this repository is intentionally small: every formula is readable, every stage is separable, and every example can be re-run in seconds. Use it to build intuition; use foundry-correlated commercial extractors for tapeout.

---

# References & Further Reading

1. IEEE Std 1481 — SPEF (Standard Parasitic Exchange Format).  
2. Foundry interconnect technology files (ITF / ICT / QRC tech) — sheet R, via R, capacitance tables.  
3. Commercial extractors: Synopsys StarRC, Cadence Quantus, Siemens Calibre xRC / Rapid3D.  
4. Elmore, W. C. — “The Transient Response of Damped Linear Networks with Particular Regard to Wideband Amplifiers,” 1948.  
5. Physical design coursework (e.g. Prof. Yao-Wen Chang) — placement, routing, and timing context for parasitics.  
6. Companion docs in-repo: `RC Extraction/docs/THEORY.md`, `RC Extraction/docs/SIGNOFF_FLOW.md`.

---

# Appendix A — Quick Formula Sheet

| Quantity | Formula |
|----------|---------|
| Sheet resistance | \(R_s = \rho / t\) |
| Wire resistance | \(R = R_s \cdot L / W\) |
| Parallel vias | \(R_{\mathrm{eq}} = R_{\mathrm{via}} / N\) |
| Area C | \(C_a = c_a \cdot W \cdot L\) |
| Fringe C | \(C_f \approx c_f \cdot L\) |
| Coupling C | \(C_c \approx k \cdot T \cdot L_{\mathrm{ov}} / S\) |
| Elmore (tree) | \(T_D(i)=\sum R_k C_{\mathrm{down}}(k)\) |
| Unit check | \(1\,\Omega \cdot 1\,\mathrm{fF} = 0.001\,\mathrm{ps}\) |

# Appendix B — Repository Map

```
RC Extraction/
  README.md
  docs/THEORY.md
  docs/SIGNOFF_FLOW.md
  docs/RC_Extraction_Signoff_Whitepaper.pdf   ← this document
  include/   headers
  src/       C++17 implementation
  examples/  simple_net, coupled_nets, via_stack
  tests/     unit checks
  Makefile   / CMakeLists.txt
```

---

*Document version 1.0 — educational white paper accompanying the RC Extraction teaching project.*
