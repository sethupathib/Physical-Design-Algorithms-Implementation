# WORKLOAD_SKU_MAP — EDA tool class vs EPYC lean (4th Gen examples)

Adapted from AMD EPYC 9004 HPC Tuning Guide **Table 9-2** (EDA).  
SKUs listed are **AMD’s examples**, not purchasing advice. Re-validate per process node and tool version.

| Workload class | Performance levers (AMD) | Example SKU lean |
|----------------|--------------------------|------------------|
| Analog simulation (SPICE) | FP, frequency, memory BW, L3 | 9374F, 9184X |
| RTL simulation | L3, frequency, memory latency/BW | 9184X |
| IR / EM analysis | Frequency, disk, single-thread | 9374F |
| Test pattern generation | Frequency, L3 | 9184X |
| Synthesis | Frequency, single-thread | 9374F |
| Placement & optimization | Frequency | 9374F |
| Routing | Frequency | 9374F |
| Formal equivalence | Frequency, L3 | 9184X |
| Static timing analysis | Cores, frequency, shared L3 | 9374F |
| Physical DRC (single-host) | Cores, frequency, shared L3 | 9374F |
| Physical DRC (distributed) | Total cores, frequency, network | 9374F, 9654 |

## How to use with this repo

1. Pick SKU/BIOS for the **dominant** farm workload.
2. Apply `epyc-eda` as the OS baseline.
3. Only then A/B TuneD vs parent for *your* binary — CLAIM_GATE first on the mechanism, then private tool KPI gate.

## F vs X mnemonic

- **F (frequency)** — clock-sensitive single-thread / lightly threaded PD steps.
- **X (3D V-Cache)** — cache-footprint sensitive (often RTL/formal-class).

Wrong mnemonic costs more than forgetting TuneD.
