# PERC in Physical Design — Concepts & Why It Is Slow

## What is PERC?

**PERC (Programmable Electrical Rules Checking)** verifies IC reliability issues that **DRC** and **LVS** cannot catch. Rules are programmable because foundries and design houses customize ESD/EOS/ERC methodology per process and product.

Industry tools: **Calibre PERC** (Siemens), **IC Validator PERC** (Synopsys).

PERC sits in **physical verification / reliability signoff**, typically after LVS-clean layout (or on schematic netlists for early checks).

---

## The Four Check Families

| Family | Inputs | What it verifies | Cost driver |
|--------|--------|------------------|-------------|
| **Netlist checks** | Schematic or extracted netlist | ESD clamp presence, floating gates, EOS/level-shifter topology, multi-power-domain rules | Graph traversal over huge netlists |
| **Netlist-driven layout (LDL / NDL)** | Netlist + GDS | Voltage-aware spacing, geometry on *regions of interest* identified from connectivity | Finding ROI + geometry ops |
| **Current density (CD)** | Layout + R-extraction + ESD path current | Metal can carry ESD current without melting / EM fail | Parasitic R mesh + current solve |
| **Point-to-point (P2P) resistance** | Layout + R-extraction | ESD discharge path R is below limit so current takes the clamp path | Many source→sink R queries on resistor networks |

All flows start with a **Netlist Analysis Engine** (the “programmable” core). Layout-heavy checks then call extraction (e.g. StarRC) on selected nets/paths.

---

## Typical ESD Flow (why wall-clock explodes)

```
Netlist / LVS extract
        │
        ▼
 Netlist analysis  ──► clamp / diode / rail topology errors
        │
        ▼
 Identify ESD paths & ROIs (pad → clamp → rail / ground)
        │
        ▼
 R-extract only (ideally) those nets / polygons
        │
        ├──► P2P resistance checks (pad to clamp, clamp to rail, …)
        └──► Current-density checks along discharge path
```

At full-chip SoC scale:

- Millions–billions of devices/nets in the connectivity graph
- Thousands of IO pads × many path endpoints → combinatorial P2P queries
- Naïve flows **flatten** hierarchy and **re-extract** everything every ECO
- Rule decks are deep (context-aware voltage propagation, multi-domain)

That combination makes PERC one of the longest reliability signoff steps.

---

## Where Runtime Goes (and how to cut it)

| Bottleneck | Optimization idea | What this C++ project models |
|------------|-------------------|------------------------------|
| Full-chip netlist walk every rule | Rule-aware **ROI pruning** | `run_roi` |
| Re-running unchanged blocks after ECO | **Incremental metadata reuse** | `run_incremental` / `MetadataStore` |
| Flat chip analysis | **Hierarchical partition** | `run_hierarchical` |
| Sequential pad-pair P2P | **Parallel path queries** | `run_parallel` (`std::async`) |
| Extracting entire design for CD/P2P | Extract **only marked ESD nets** (LDL) | ROI net set + pad-scoped Dijkstra |

Commercial tools also use distributed multi-CPU scaling and foundry-tuned rule decks; those are orthogonal to the algorithmic wins above.

---

## What This Project Is (and Is Not)

**Is:** A C++17 stand-in for PERC’s expensive cores — netlist topology checks + graph-based P2P resistance — with measurable baseline vs optimized runtimes on synthetic circuits.

**Is not:** A replacement for Calibre / ICV, a foundry runset, or a full parasitic extractor. Geometry and StarRC-class extraction are abstracted as a weighted resistor graph (`RGraph` + Dijkstra).
