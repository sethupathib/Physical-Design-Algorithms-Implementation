# NUMA Memory Policy for Fusion Compiler–Class Physical Design Jobs

**A design and operations white paper for the `NUMA-EDA-Bench` project**

**Authors:** Project notes distilled from implementation and experiments in
`Physical-Design-Algorithms-Implementation`  
**Scope:** Job-local DRAM / NUMA placement for ASIC/SoC PD workloads on
multi-socket Linux compute farms  
**Companion code:** `NUMA-EDA-Bench/` (microbench, before/after harness,
production wrapper, LinkedIn demo)  
**Sibling project:** `PD Job Acceleration/` (tmpfs + rsync for filesystem
placement)

---

## Abstract

Physical-design (PD) tools such as Synopsys Fusion Compiler, Cadence Innovus,
and large-scale STA/extraction engines are routinely described as CPU-bound.
On dual- and quad-socket farm nodes, a large fraction of wall-clock time can
instead be spent waiting on **remote DRAM**: cores on one NUMA node touching
pages that live on another. The interconnect (Intel UPI/QPI, AMD Infinity
Fabric) adds latency and steals bandwidth under load. `top` still shows 100%
CPU; turnaround does not improve with “more cores.”

This white paper presents a practical, license-preserving acceleration pattern:

1. Discover NUMA topology (`numactl -H`, sysfs).
2. For one fat PD job that **fits in one node’s free RAM**, pin CPUs and bind
   memory to the **same** node:
   `numactl --cpunodebind=N --membind=N <tool> …`
3. Measure before/after with a STREAM + pointer-chase + graph-walk microbench
   (and, on real silicon, with `numastat` / wall time of a real stage).
4. Refuse hard `membind` when free memory is insufficient; fall back to
   `--preferred` or resize the job/machine.

We describe the Linux first-touch model, failure modes, a before/after harness
modeled on the repository’s tmpfs+rsync experiments (including an **emulated
remote DRAM tax** for single-node hosts), and how to defend the approach in
design reviews and interviews. The central claim is not a new PD algorithm; it
is that **memory placement is part of turnaround**, and that this can be made
explicit, measurable, and operationally safe.

---

## Table of contents

1. [Motivation and industry context](#1-motivation-and-industry-context)
2. [Problem statement](#2-problem-statement)
3. [NUMA in one page](#3-numa-in-one-page)
4. [Why first-touch creates remote fills](#4-why-first-touch-creates-remote-fills)
5. [Design principles](#5-design-principles)
6. [The policy: `numactl` bind](#6-the-policy-numactl-bind)
7. [Relationship to tmpfs + rsync](#7-relationship-to-tmpfs--rsync)
8. [Experimental methodology](#8-experimental-methodology)
9. [Results](#9-results)
10. [When the pattern helps—and when it does not](#10-when-the-pattern-helpsand-when-it-does-not)
11. [Production wrapper and safety](#11-production-wrapper-and-safety)
12. [Defending the approach (review / interview)](#12-defending-the-approach-review--interview)
13. [Limitations and future work](#13-limitations-and-future-work)
14. [Conclusion](#14-conclusion)
15. [Appendix A: quick-start commands](#appendix-a-quick-start-commands)
16. [Appendix B: glossary](#appendix-b-glossary)

---

## 1. Motivation and industry context

### 1.1 The multi-socket PD farm

A modern PD host is often a **2-socket (2S)** or **4-socket** Xeon/EPYC
machine with hundreds of GB of DRAM. Each socket is a **NUMA node**: it owns
a set of cores and a set of memory controllers. Cross-node loads are legal but
not free.

Fusion Compiler–class jobs:

- allocate multi‑GB–TB working sets (netlist, timing graph, routing DB),
- stream and chase pointers through those structures,
- spawn many worker threads.

If threads run on node 0 while the hot heap sits on node 1, every miss pays
interconnect latency and contends with other jobs’ remote traffic.

### 1.2 Misdiagnosis is common

Teams respond with:

- more cores / higher thread counts,
- larger machines,
- or algorithm-level tuning,

when the binding constraint is **memory locality**. Conversely, hard-binding a
job that does not fit in one node’s free RAM produces OOM or reclaim storms
that look like “`numactl` broke my run.”

This project exists to make the correct middle path explicit, measurable, and
safe—parallel to how `PD Job Acceleration` made tmpfs+rsync explicit for I/O.

---

## 2. Problem statement

> **Given** a PD tool command on a multi-socket Linux host,  
> **accelerate wall-clock turnaround** by ensuring CPU threads and DRAM pages
> share a NUMA node,  
> **without** changing the tool binary, licenses, or functional results,  
> **while** avoiding OOM from hard `membind` on undersized nodes.

Success criteria:

1. **Functional equivalence** — same Tcl, same deliverables.  
2. **Measurable locality win** — higher STREAM-like bandwidth, lower chase /
   graph latency, lower wall time on real stages when remote was the bound.  
3. **Bounded risk** — refuse unsafe `membind`; document topology.  
4. **Operability** — one wrapper command; clear before/after harness.

---

## 3. NUMA in one page

**NUMA** = Non-Uniform Memory Access.

| Access | Typical cost |
|---|---|
| Local DRAM (same node) | baseline latency / full controller BW |
| Remote DRAM (other node) | +latency, −effective BW, interconnect contention |

Topology discovery:

```bash
numactl -H
lscpu | grep NUMA
ls /sys/devices/system/node
```

Distance matrices in `numactl -H` encode relative hop costs (lower = closer).

---

## 4. Why first-touch creates remote fills

Linux often places a newly written anonymous page on the **node of the CPU
that first touched it** (first-touch).

Canonical PD failure mode:

1. Master thread on node 0 allocates and zeros a huge array / DB arena.  
2. Or init runs on node 1 while workers later run on node 0.  
3. The OS load-balances threads across sockets while the heap stays put.

AutoNUMA / migrate-on-fault can move pages, but slowly and imperfectly for
short phases and huge stable working sets. Overnight FC with a hot heap still
suffers if policy is left to chance.

`membind` + `cpunodebind` remove ambiguity for production runs.

---

## 5. Design principles

1. **Same node for CPUs and pages** when the job fits.  
2. **Topology before policy** — 1-node machines gain nothing from bind theater.  
3. **Hard bind only with headroom** — peak RSS × safety factor < node MemFree.  
4. **Measure, don’t folklore** — before/after harness + `numastat -p`.  
5. **Separate I/O locality from DRAM locality** — tmpfs and `numactl` solve
   different bottlenecks; both can apply on the same job.

---

## 6. The policy: `numactl` bind

### 6.1 DeepSeek-style recipe (one fat FC)

```bash
numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

| Flag | Meaning |
|---|---|
| `--cpunodebind=0` | schedule only on node 0 CPUs |
| `--membind=0` | allocate only from node 0 memory |
| `--localalloc` | prefer the touching CPU’s node |
| `--preferred=0` | prefer node 0, spill if needed |
| `--interleave=all` | stripe pages (sometimes for huge shared heaps) |

### 6.2 Soft vs hard

- **`membind`** — hard; fails or stalls if the node is exhausted.  
- **`preferred`** — soft; safer when RSS is uncertain.  
- **`interleave`** — can help when the working set intentionally spans the
  machine; often hurts a single mid-size FC that would fit on one node.

---

## 7. Relationship to tmpfs + rsync

| Concern | Project | Lever |
|---|---|---|
| NFS / disk latency, tiny-file storms | `PD Job Acceleration` | tmpfs hot tier + rsync durability |
| Remote DRAM / UPI contention | `NUMA-EDA-Bench` | `numactl` CPU+mem bind |

A job can be **I/O-bound on NFS** and **NUMA-bound on DRAM** in different
phases. Profile each; apply the matching lever.

---

## 8. Experimental methodology

### 8.1 Microbench (`numa_mem_bench`)

FC-class proxy (no EDA license required):

1. **STREAM triad** — `a[i]=b[i]+s*c[i]` bandwidth (GiB/s).  
2. **Pointer chase** — random cycle over a large index array (ns/hop).  
3. **Graph walk** — degree-4 CSR-like random edges (timing/netlist proxy).  
4. **wall_proxy** — composite score (lower better).

Machine-readable:

```bash
./build/numa_mem_bench --json --bytes 512M --threads 4
```

### 8.2 Before/after harness (`examples/compare_numa.sh`)

Modeled on `PD Job Acceleration/examples/compare_accel.sh` and
`compare_pd_farm_io.sh`.

**Hardware path** (≥2 nodes):

| Leg | Command |
|---|---|
| BEFORE | `numactl --cpunodebind=0 --membind=1 ./build/numa_mem_bench …` |
| AFTER | `numactl --cpunodebind=0 --membind=0 ./build/numa_mem_bench …` |

**Emulated path** (1 node — cloud / laptop):

| Leg | Command |
|---|---|
| BEFORE | `./build/numa_mem_bench --emulate-remote --remote-bw-mult=0.55 --remote-lat-mult=1.75 …` |
| AFTER | local (optionally under `membind=0`) |

Emulation is **explicitly labeled**, analogous to `--nfs-us` in the farm I/O
suite: it lets the harness and documentation stay honest on single-node hosts
while still producing a BEFORE/AFTER artifact. Design-review claims for a farm
should cite a **hardware** run on a 2S/4S node.

### 8.3 What we do *not* claim

- Emulated ratios are not silicon measurements.  
- Microbench ≠ full Fusion Compiler wall time.  
- Functional PD QoR is unchanged by `numactl`; only resource placement changes.

---

## 9. Results

### 9.1 This repository cloud host (1 NUMA node)

Environment at measurement time:

- Host: cloud agent VM (`hostname=cursor`)
- Topology: **1 socket / 1 NUMA node / 4 CPUs**
- `numactl` vendored under `tools/numactl-root/`
- Compare mode: **emulated** (remote DRAM tax)
- Workload: `--bytes 512M --threads 4`

Command:

```bash
./examples/compare_numa.sh
```

Measured results (see also `examples/compare_results/SUMMARY.txt`):

| config | triad (GiB/s) | chase (ns) | graph (ns) | wall_proxy |
|---|---:|---:|---:|---:|
| BEFORE emulated remote (bw×0.55, lat×1.75) | 54.0 | 194.1 | 102.6 | 31.5 |
| AFTER local / `membind=0` | 68.7 | 116.9 | 13.8 | 14.5 |

| ratio | value |
|---|---:|
| AFTER/BEFORE triad | **1.27×** |
| BEFORE/AFTER chase | **1.66×** |
| BEFORE/AFTER graph | **7.4×** |
| BEFORE/AFTER wall_proxy | **2.17×** |

Interpretation: on this 1-node host the AFTER leg is native local DRAM; the
BEFORE leg applies the labeled remote tax. The harness and summary format are
what you re-run on a **2S farm** to replace these with hardware remote-vs-local
numbers. Do not cite the emulated ratios as silicon UPI measurements.

### 9.2 Expected hardware shape (2S farm)

On a real dual-socket machine, literature and field practice typically show:

| Metric | Remote vs local (order of magnitude) |
|---|---|
| STREAM-like bandwidth | remote often ~0.5–0.8× local under load |
| Pointer-chase latency | remote > local (tens of % to 2× depending on platform) |
| FC stage wall time | win when the stage was interconnect-bound and RSS fits |

Re-run `./examples/compare_numa.sh` on farm silicon and replace §9.1 numbers
in review decks.

### 9.3 How to read `SUMMARY.txt`

- **triad** — higher better  
- **chase_ns / graph_ns** — lower better  
- **wall_proxy** — lower better  
- Ratios labeled AFTER/BEFORE or BEFORE/AFTER accordingly

---

## 10. When the pattern helps—and when it does not

| Situation | Likely outcome |
|---|---|
| 2S/4S box, one FC, RSS fits one node | High — primary target |
| Already 1 NUMA node | None from bind; harness uses emulation only |
| RSS > node free RAM + hard membind | Harm — OOM / thrash |
| Bound is NFS / disk | Fix I/O first (`PD Job Acceleration`) |
| Many small jobs | Spread jobs across nodes (one job per node) |
| Intentionally machine-spanning heap | Consider interleave / preferred, not hard single-node membind |

---

## 11. Production wrapper and safety

`scripts/run_eda_numactl.sh`:

```bash
./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl
```

Behavior:

1. Verifies `numactl` and node existence.  
2. Prints node MemFree and full `numactl -H` into the log stream.  
3. Refuses `membind` if MemFree < 8 GiB unless `FORCE=1`.  
4. `exec`s `numactl --cpunodebind=N --membind=N …`.

Operational checklist:

1. `numactl -H` / free memory per node.  
2. Estimate peak RSS (prior runs, `numastat`, peak from farm accounting).  
3. Bind only with headroom.  
4. Log policy into the run manifest.  
5. Optional live check: `numastat -p $(pgrep -n fc_shell)`.

---

## 12. Defending the approach (review / interview)

**Claim:** “We improved FC turnaround with `numactl`.”

**Defense structure:**

1. **Topology** — show `numactl -H` (multi-node).  
2. **Hypothesis** — remote fills / first-touch scatter.  
3. **Measurement** — BEFORE remote vs AFTER local microbench; ideally stage
   wall times + `numastat`.  
4. **Safety** — MemFree vs peak RSS; refuse unsafe membind.  
5. **Non-claims** — not a QoR change; not a substitute for I/O tiering.  
6. **Sibling** — I/O locality handled by tmpfs+rsync project when NFS-bound.

Interview one-liner:

> Same silicon, better memory policy: pin FC CPUs and pages to one NUMA node
> when the working set fits—because remote DRAM is a tax `top` cannot see.

---

## 13. Limitations and future work

- Emulated remote tax is a model (calibrated defaults 0.55× BW / 1.75× lat).  
- No licensed FC binary in CI — microbench + wrapper only.  
- Future: cgroup/cpuset farm integration; automatic RSS vs MemFree advisor;
  `perf c2c` recipes; hugepage interaction notes.

---

## 14. Conclusion

Multi-socket PD farms hide a class of performance bugs in plain sight: **CPU
busy, memory remote**. The DeepSeek-style `numactl --cpunodebind --membind`
recipe is the correct first response when a single Fusion Compiler–class job
fits in one node’s RAM. This repository turns that recipe into a before/after
experiment, a production wrapper, a white paper, and a visual LinkedIn demo—
the DRAM-locality counterpart to tmpfs+rsync for filesystem locality.

---

## Appendix A: quick-start commands

```bash
cd NUMA-EDA-Bench
./scripts/numa_report.sh
make -j
./examples/compare_numa.sh
cat examples/compare_results/SUMMARY.txt

# Production-style wrap
./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl

# LinkedIn GIF
python3 demo/gen_numa_linkedin_gif.py

# White paper PDF
python3 docs/build_whitepaper_pdf.py
```

---

## Appendix B: glossary

| Term | Meaning |
|---|---|
| NUMA | Non-Uniform Memory Access |
| UPI / IF | Intel Ultra Path Interconnect / AMD Infinity Fabric |
| first-touch | Page placed on the node of the CPU that first writes it |
| membind | Hard memory-node binding (`numactl`) |
| cpunodebind | Restrict threads to a node’s CPUs |
| wall_proxy | Composite microbench score (lower better) |
| emulate-remote | Labeled software remote-DRAM tax for 1-node hosts |
