# RC Extraction (C++)

Hands-on project: **how R & C are extracted from layout geometry** (the GDS-derived shapes used in physical-design signoff) and turned into SPEF for timing.

This is **strictly C++17**. No Python.

Deep theory: [`docs/THEORY.md`](docs/THEORY.md)

---

## What you will learn

People often say “extract the netlist from GDS.” That usually means **LVS connectivity**. **Parasitic RC extraction** is a second pass over the *same geometry* plus a **process techfile**:

```
GDS polygons  →  connectivity (nets)  →  segment R & C  →  SPEF  →  STA / SI
```

You do **not** compute R/C from a logical Verilog netlist. You compute them from **wire geometry + layer stack**, then annotate the logical nets.

This project implements a transparent **2.5D analytical extractor**:

| Step | Module | Formula / idea |
|------|--------|----------------|
| Connectivity | `connectivity.cpp` | Union-Find on abutting metals + via stitches |
| Resistance | `resistance.cpp` | \(R = R_s \cdot L/W\), via \(R_{via}/N\) |
| Capacitance | `capacitance.cpp` | area + fringe + same-layer coupling |
| RC network | `rc_network.cpp` | π-model, geometric node merge |
| SPEF | `spef_writer.cpp` | IEEE-1481 subset for signoff tools |
| Elmore | `elmore.cpp` | mini timing signoff on the extracted tree |

---

## Build

```bash
cd "RC Extraction"
make          # → rcx_extract, test_rc
make test
make demos
```

Or CMake:

```bash
cmake -S . -B build && cmake --build build
cd build && ctest --verbose
```

---

## Run

```bash
./rcx_extract examples/simple_net.lay
./rcx_extract examples/simple_net.lay --spef out.spef --elmore clk U1:Z
./rcx_extract examples/coupled_nets.lay --spef coupled.spef
./rcx_extract examples/via_stack.lay --elmore netx DRV:Z
```

### Layout format (`.lay`)

Stand-in for GDS polygons + pin annotations (no external GDS parser):

```
NAME design
METAL <layer> <net> <name> <x0> <y0> <x1> <y1>
VIA   <layer> <net> <name> <x0> <y0> <x1> <y1>
PIN   <pin> <net> <layer> <I|O|B> <x> <y>
```

Coordinates are in **µm**. Tech parameters live in `src/techfile.cpp` (`defaultTech()`).

---

## Examples

1. **`simple_net.lay`** — one M1 wire, driver→load. See sheet resistance and Elmore delay.
2. **`coupled_nets.lay`** — parallel victim/aggressor. See `Cc` coupling in SPEF.
3. **`via_stack.lay`** — M1–VIA1–M2–VIA2–M3. See multi-layer connectivity + via R.

---

## Mental model (GDS → SPEF)

```
GDS / layout shapes
        │
        ├─ layer map (METAL / VIA)
        ├─ geometric connectivity → net IDs   (same graph LVS uses)
        ├─ fracture into segments
        ├─ R = Rs·L/W , Rvia
        ├─ Carea, Cfringe, Ccoup(neighbors)
        ├─ assemble π / distributed RC graph
        └─ emit SPEF  →  PrimeTime / Tempus / OpenSTA
```

Industry tools (StarRC, Quantus, Calibre xRC) scale this with pattern tables and 3D field solvers. The physics and dataflow are the same as this toy.

---

## Source map

```
include/          public headers
src/              implementation + main
examples/         .lay layouts
tests/test_rc.cpp unit checks for R, via, coupling, pipeline
docs/THEORY.md    full signoff / extraction write-up
```
