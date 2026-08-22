# numa-fc-bind

**Bind Fusion Compiler–class jobs to one NUMA node — correctly.**

Working farm toolkit + mechanism GIF + white paper.  
No invented speedups on single-socket machines.

| Deliverable | Path |
|---|---|
| Working code | `scripts/`, `src/`, `examples/`, `tools/` |
| Detailed README | this file |
| White paper | [`WHITEPAPER.md`](./WHITEPAPER.md) · [`docs/numa_fc_whitepaper.pdf`](./docs/numa_fc_whitepaper.pdf) |
| Working GIF | [`demo/numa_fc_bind.gif`](./demo/numa_fc_bind.gif) |

---

## The problem (one paragraph)

On a dual-socket server each socket owns its own DRAM. If `fc_shell` runs on
node 0 but the working set was first-touched on node 1, every miss crosses
UPI / Infinity Fabric. CPUs look busy in `top`; wall time still suffers. When
peak RSS **fits** one node’s free RAM, pin cores and memory to that node:

```bash
numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

---

## Quick start (this machine)

```bash
cd numa-fc-bind

# Topology
./scripts/numa_report.sh

# Build + smoke microbench (works on 1-node; does not prove NUMA wins)
make -j
make smoke

# Mechanism GIF (regenerate anytime)
make gif
# → demo/numa_fc_bind.gif

# White paper PDF
make pdf

# Hardware remote vs local — requires ≥2 NUMA nodes (exits 2 otherwise)
./examples/compare_numa.sh
```

Vendored (no root install): `tools/numactl-root/usr/bin/{numactl,numastat}`.

---

## Production wrap (farm)

```bash
./scripts/run_with_numactl.sh 0 fc_shell -f run.tcl

# Soft bind when peak RSS is uncertain:
POLICY=preferred ./scripts/run_with_numactl.sh 0 fc_shell -f run.tcl

# Override MemFree floor only if you mean it:
FORCE=1 MIN_MEMFREE_GIB=4 ./scripts/run_with_numactl.sh 0 …
```

Safety defaults:

- Refuses hard `membind` if node `MemFree` < `MIN_MEMFREE_GIB` (default **8**)
- Logs `numactl -H`, node MemTotal/MemFree, host, timestamp
- Warns on single-node hosts (binding will not change DRAM locality)

During a live run:

```bash
numastat -p $(pgrep -n fc_shell)
```

---

## Hardware before / after (citeable microbench only)

On a **≥2 NUMA node** host:

```bash
TRIALS=5 BYTES=1G THREADS=$(nproc) ./examples/compare_numa.sh
cat examples/compare_results/SUMMARY.txt
cat examples/compare_results/CLAIM_GATE.txt   # must be CITEABLE=yes
```

| Metric | Meaning | Better |
|---|---|---|
| `triad_gib_s` | STREAM triad bandwidth | higher |
| `chase_ns` | pointer-chase latency | lower |

Median of `TRIALS` with printed spreads.  
**This is not Fusion Compiler wall time.** Pair with stage wall clock + `numastat`
for a farm claim.

On **1-node** hosts (including many cloud VMs) the compare script **exits 2** and
refuses to write a fake SUMMARY. That is intentional.

---

## GIF

`demo/numa_fc_bind.gif` — mechanism story:

1. Dual-socket topology  
2. Unbound failure mode (remote fills)  
3. Types the `numactl` policy  
4. Bound / local  
5. Takeaway (measure on real 2S/4S silicon)

Badge on every frame: **mechanism · not a benchmark**.  
No fake percentage meters.

```bash
make gif
```

---

## Metrics glossary

| Name | What it is | What it is not |
|---|---|---|
| triad | STREAM `a[i]=b[i]+s*c[i]` through a large array | FC runtime |
| chase | Random pointer-chase over a shuffled cycle | QoR / timing |
| CLAIM_GATE | `CITEABLE=yes` only after hardware compare | Permission to invent numbers |

---

## Layout

```
numa-fc-bind/
├── README.md
├── WHITEPAPER.md
├── Makefile
├── src/numa_mem_bench.cpp
├── scripts/numa_report.sh
├── scripts/run_with_numactl.sh
├── examples/compare_numa.sh
├── demo/gen_gif.py
├── demo/numa_fc_bind.gif
├── docs/build_whitepaper_pdf.py
├── docs/numa_fc_whitepaper.pdf
└── tools/numactl-root/usr/bin/{numactl,numastat}
```

---

## Claims policy

| Allowed | Not allowed |
|---|---|
| Hardware compare on ≥2 nodes (`CLAIM_GATE=CITEABLE=yes`) labeled as microbench | “X× faster” from a 1-node / cloud VM |
| Real FC stage wall time + `numastat` | Treating the GIF as measured performance |
| Explaining the `numactl` recipe + safety rules | Hard `membind` into a node that cannot hold peak RSS |

---

## Sibling pattern

Filesystem locality: tmpfs + rsync (`PD Job Acceleration`).  
DRAM locality: this project (`numactl` bind).  
Different bottlenecks; both are placement, not PD algorithms.
