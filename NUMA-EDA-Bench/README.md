# NUMA binding for Fusion Compiler–class jobs

Useful farm toolkit: discover topology, wrap a tool with `numactl`, measure
**real** remote vs local DRAM on multi-socket hosts.

Nothing here invents a speedup on a single-socket machine.

## What this is for

On 2S/4S servers, FC can run with threads on one socket and pages on another
(first-touch / scheduler). That is remote DRAM across UPI/Infinity Fabric.
`top` still shows busy CPUs.

When the working set **fits one node’s free RAM**:

```bash
./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl
# ≡ numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

## Commands

```bash
cd NUMA-EDA-Bench

# 1) Topology + MemFree per node
./scripts/numa_report.sh

# 2) Production wrap (safe MemFree guard; POLICY=preferred if unsure)
./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl
POLICY=preferred ./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl

# 3) Hardware microbench — requires ≥2 NUMA nodes (exits 2 otherwise)
make -j
TRIALS=5 BYTES=1G ./examples/compare_numa.sh
cat examples/compare_results/SUMMARY.txt
cat examples/compare_results/CLAIM_GATE.txt
```

Vendored CLI (no root): `tools/numactl-root/usr/bin/{numactl,numastat}`.

## Metrics (hardware compare only)

| Metric | Meaning | Better |
|---|---|---|
| `triad_gib_s` | STREAM triad bandwidth | higher |
| `chase_ns` | pointer-chase latency | lower |

Median of `TRIALS` (default 5). Spreads are printed so you can see noise.

This is **not** Fusion Compiler wall time. For a farm claim, pair it with stage
wall time and `numastat -p <pid>`.

## What we will not claim

- Numbers from a 1-node host (compare script refuses to fake them)
- Artificial “emulated remote” taxes as UPI results
- A synthetic `wall_proxy` as tool runtime

## Docs

- [`WHITEPAPER.md`](./WHITEPAPER.md) — design / ops write-up  
- [`docs/numa_fc_whitepaper.pdf`](./docs/numa_fc_whitepaper.pdf)

## Layout

| Path | Role |
|---|---|
| `scripts/numa_report.sh` | topology |
| `scripts/run_eda_numactl.sh` | production wrapper |
| `examples/compare_numa.sh` | hardware remote vs local |
| `src/numa_mem_bench.cpp` | STREAM + chase |
| `tools/numactl-root/` | vendored numactl/numastat |
