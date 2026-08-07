# RC Extraction Theory (Physical Design Signoff)

This document explains **how resistance (R) and capacitance (C) are extracted from layout geometry** that ultimately comes from GDS — the same physics commercial tools (StarRC, Quantus, Calibre xRC, Rapid3D, …) approximate at industrial scale.

---

## 1. Where RC extraction sits in the signoff flow

```
RTL → Synthesis → PnR → GDSII (mask layout)
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Layout vs Schematic │  (LVS: connectivity correct?)
                    │  Device recognition  │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  Parasitic Extraction│  ← YOU ARE HERE
                    │  (R, C, sometimes L) │
                    └──────────┬──────────┘
                               ▼
                         SPEF / DSPF / SPF
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
              Static Timing (STA)    Signal Integrity / IR-drop
              with annotated delay   (coupled C, noise, EM)
```

**Important distinction:**

| Step | Input | Output | Question answered |
|------|-------|--------|-------------------|
| LVS / netlist extraction | GDS polygons + schematic | Flat/hierarchical **logical** netlist | “Are the transistors wired as intended?” |
| Parasitic RC extraction | Same GDS polygons + **process techfile** | Annotated netlist / **SPEF** with R & C | “What delays, noise, and IR drop do those wires cause?” |

People often say “extract the netlist from GDS.” That usually means LVS device+connectivity extraction. **RC extraction is a second pass** over the *same geometry*, using foundry electrical rules (ITF / ICT / QRC techfile) to attach parasitics to those nets.

---

## 2. What is in the GDS?

GDSII is a stream of **polygons on named layers** (MET1, VIA1, MET2, POLY, DIFF, …), plus cell hierarchy.

For interconnect RC, the extractor cares about:

1. **Conductor shapes** — metal / poly rectangles (or rectilinear polygons)
2. **Via shapes** — cuts that connect adjacent metal layers
3. **Layer stack** — which layer is above which, thickness, dielectric
4. **Connectivity** — shapes that touch (or are connected by vias) belong to the same **net**

A simplified 3-metal stack:

```
        ┌──────────────┐  M3  (top metal)
        │              │
   ═════╪══════════════╪════  VIA2
        │              │
   ┌────┴────┐    ┌────┴────┐  M2
   │         │    │         │
═══╪═════════╪════╪═════════╪═  VIA1
   │         │    │         │
┌──┴──┐   ┌──┴────┴──┐   ┌──┴──┐  M1
│     │   │          │   │     │
└─────┘   └──────────┘   └─────┘
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  substrate / ground plane
```

---

## 3. Resistance extraction

### 3.1 Sheet resistance

A thin metal film has **sheet resistance** \(R_s\) (Ω/□):

\[
R_s = \frac{\rho}{t}
\]

where \(\rho\) is resistivity and \(t\) is thickness.

For a rectangular wire of length \(L\) and width \(W\):

\[
R = R_s \cdot \frac{L}{W}
\]

“Squares” = \(L/W\). A wire 10 µm long and 1 µm wide is **10 squares**.

### 3.2 Via resistance

Each via has a nearly-fixed resistance \(R_{via}\) (from foundry tables; depends on size, barrier, landing). Parallel vias:

\[
R_{via,eq} = \frac{R_{via}}{N}
\]

### 3.3 Segmentation

Extractors chop long wires into **segments** (at bends, vias, taps, or fixed max length) so the RC network can model distributed delay. Each segment becomes one resistor (or a chain of resistors in distributed models).

### 3.4 What we ignore in this teaching project

- Current crowding / current density maps
- Barrier/liner non-uniformity
- Temperature coefficients (real signoff uses corner temps)
- Slotting / cheesing density rules affecting effective \(R_s\)

---

## 4. Capacitance extraction

Capacitance is harder: every conductor couples to every nearby conductor through the dielectric.

### 4.1 Three dominant terms (2.5D analytical model)

For a wire on layer \(i\):

1. **Area (plate) capacitance to ground / substrate**
   \[
   C_{area} = \varepsilon_{ox} \cdot \frac{W \cdot L}{H}
   \]
   \(H\) = dielectric thickness under the metal.

2. **Fringe capacitance** — field lines from the sidewalls to ground
   \[
   C_{fringe} \approx \varepsilon \cdot L \cdot f(T, H, W)
   \]
   Often tabulated or fit as \(c_f \cdot L\) (fF/µm).

3. **Coupling capacitance** between parallel neighbors on the same layer
   \[
   C_{coup} \approx \varepsilon \cdot \frac{T \cdot L_{overlap}}{S}
   \]
   \(T\) = metal thickness, \(S\) = spacing. More accurate models use conformal-mapping / foundry tables vs \(S\).

Cross-layer coupling (M1 under M2) also exists; full-chip tools use pattern matching or field solvers.

### 4.2 Total capacitance seen by STA

For a net segment:

\[
C_{total} = C_{area} + C_{fringe} + \sum C_{coup}
\]

In **SPEF**, coupling caps are often stored as separate `CC` (coupled) elements so SI tools can do aggressor/victim analysis. STA may use grounded-C (lump coupling to ground with a Miller factor) or keep CC for Crosstalk delay.

### 4.3 Extraction modes (industry)

| Mode | Method | Accuracy | Runtime |
|------|--------|----------|---------|
| Rule-based / pattern | Lookup tables from foundry | Good for digital | Fast |
| 2.5D analytical | Formulas + tables | Medium | Fast |
| 3D field solver | Solve Maxwell on voxel/mesh | Highest | Slow (used on critical nets) |

This project implements a **transparent 2.5D analytical** model so you can see every formula.

---

## 5. RC network models

Once you have segment R and C, you assemble a circuit model of the net:

### Lumped C (too crude for long nets)
```
Driver ── R_total ──●── Receiver
                    │
                   C_total
                    │
                   GND
```

### π-model (common for SPEF segments)
```
Driver ── R ──●── Receiver
              │
           C/2 C/2
              │
             GND
```

### Distributed / ladder (better for long / high-R wires)
```
── R/n ──●── R/n ──●── … ──●──
         │         │         │
        C/n       C/n       C/n
```

Elmore delay for an RC tree rooted at the driver:

\[
T_{D}(i) = \sum_{k \in path(s\to i)} R_k \cdot C_{downstream}(k)
\]

---

## 6. SPEF — what signoff tools actually consume

**SPEF** (Standard Parasitic Exchange Format, IEEE 1481) annotates parasitics onto a netlist for STA (PrimeTime, Tempus, OpenSTA, …).

Minimal conceptual SPEF for one net:

```
*D_NET net_a 12.5          // total lumped C in pF (or fF per *C_UNIT)
*CONN
*I inst1:Z O               // driver pin
*I inst2:A I               // load pin
*CAP
1 net_a:1 0.006            // grounded cap
2 net_a:2 0.006
*RES
1 net_a:1 net_a:2 25.0     // resistance between nodes
*END
```

Coupling:

```
*CAP
3 net_a:1 net_b:1 0.002    // CC between two nets
```

---

## 7. End-to-end mental model (GDS → SPEF)

```
GDS polygons
    │
    ├─1─ Flatten / expand hierarchy (or extract hierarchical)
    │
    ├─2─ Layer map: GDS layer/datatype → conductor / via / device
    │
    ├─3─ Geometric connectivity: abutting metals + vias → NET IDs
    │     (same graph LVS builds for shorts/opens)
    │
    ├─4─ Fracture nets into wire segments + via instances
    │
    ├─5─ For each segment: R = Rs·L/W ; collect via R
    │
    ├─6─ For each segment: Carea, Cfringe; for each neighbor pair: Ccoup
    │     (need neighbor search: edges, R-trees, scanline)
    │
    ├─7─ Build RC graph per net (nodes at pins, vias, bends)
    │
    └─8─ Write SPEF / DSPF / OpenRCX .spef → STA / SI / EM-IR
```

**You do not extract R&C “from the logical netlist.”**  
You extract connectivity from geometry (→ nets), then attach R&C computed from **geometry + process stack**, and emit a parasitic netlist that *references* the logical net/pin names.

---

## 8. Corners and signoff reality

Foundries provide multiple extraction corners, e.g.:

- **Cmax / Cmin** — dielectric / etch extremes for timing
- **RCmax / RCmin** — combined interconnect corners
- **Typical**

Signoff STA runs **multi-corner multi-mode (MCMM)** with matching SPEF per corner. Temperature and voltage further scale R (and sometimes C).

---

## 9. What this teaching extractor implements

| Feature | Status |
|---------|--------|
| Rectilinear metal rectangles on M1–M3 | Yes |
| Via cuts between layers | Yes |
| Connectivity / net labeling | Yes |
| Segment resistance \(R_s L/W\) | Yes |
| Via resistance | Yes |
| Area + fringe C to ground | Yes |
| Same-layer coupling C | Yes |
| π-model RC network | Yes |
| SPEF writer | Yes |
| Elmore delay demo (mini-signoff) | Yes |
| Full GDSII parser / 3D field solver | No (intentionally) |
| Device (transistor) extraction | No (focus = interconnect) |

The goal is **deep intuition**, not replacing StarRC.
