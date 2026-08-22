# NUMA / `numactl` for EDA (Fusion Compiler–class workloads)

Teaching project: why multi-socket memory policy matters for memory-heavy PD tools,
how to measure it, and how to wrap jobs safely with `numactl`.

## Why this exists

Fusion Compiler / Innovus / similar tools are **memory-bandwidth and capacity hogs**.
On a **2-socket (or more) server**, RAM is split into NUMA nodes. If the process runs
on socket A but touches pages sitting on socket B, every load pays **remote DRAM latency
+ contention on the QPI/UPI/Infinity Fabric link**. That can dominate wall time even
when CPUs look “busy.”

DeepSeek’s hack is directionally right:

> Pin FC to cores on **one NUMA node** and bind memory allocation to **that same node**.

This repo turns that into: theory → topology discovery → microbench → job wrappers.

## Quick start

```bash
# 1) See your machine
./scripts/numa_report.sh

# 2) Build bandwidth / latency microbench (Makefile path; needs g++)
make -j

# Optional CMake (set a full g++ toolchain if default c++ is clang without libstdc++):
#   CXX=g++ cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j

# 3) Run bench (works even on 1-node VMs; on multi-node use numactl)
./build/numa_mem_bench --threads 4 --bytes 512M
./scripts/compare_local_remote.sh   # unbound vs local vs remote when possible

numactl --cpunodebind=0 --membind=0 ./build/numa_mem_bench --threads 4 --bytes 512M
numactl --cpunodebind=0 --membind=1 ./build/numa_mem_bench --threads 4 --bytes 512M  # remote (multi-node)

# 4) Wrap a real EDA job (example)
./scripts/run_eda_numactl.sh 0 /path/to/fc_shell -f run.tcl
```

**This cloud VM:** 1 NUMA node, no `numactl` package — the bench still runs; local-vs-remote contrast needs a real multi-socket farm box.
## Mental model

```
  Socket 0                    Socket 1
 ┌─────────────┐             ┌─────────────┐
 │ cores 0..N  │             │ cores ..    │
 │   DRAM 0    │◄── UPI/QPI ►│   DRAM 1    │
 └─────────────┘             └─────────────┘
        ▲
        │  local access = fast
        │  remote access = slower + burns interconnect
```

- **`--cpunodebind=N`**: schedule threads only on node N’s CPUs  
- **`--membind=N`**: allocate new pages only from node N’s memory  
- **`--localalloc`**: prefer local node of the CPU that first touches the page  
- **`--interleave=all`**: stripe pages (sometimes good for huge shared heaps; often worse for single fat FC)

## When the hack helps

| Situation | Likely win |
|---|---|
| 2-socket box, one big FC/Innovus | High — keep CPU+RAM on one node |
| Machine already 1 NUMA node | None — measure first |
| Job bigger than one node’s RAM | Don’t membind only that node (OOM / swap death) |
| Many small jobs | Spread jobs across nodes, one job per node |

## Safety

`membind` to a node with insufficient free RAM → allocation failure or reclaim storms.
Always check `numactl -H` / `free -h` / `numastat -p <pid>` before overnight runs.

## Layout

- `docs/THEORY.md` — deeper NUMA + EDA notes  
- `docs/LINKEDIN_DRAFT.md` — post drafts you can edit  
- `src/numa_mem_bench.cpp` — STREAM-like triad + pointer-chase microbench  
- `scripts/numa_report.sh` — topology + recommendations  
- `scripts/compare_local_remote.sh` — unbound vs local vs remote contrast  
- `scripts/run_eda_numactl.sh` — production-style EDA wrapper  
- `scripts/parse_bench_out.py` — compare saved bench logs  
- `results/RESULTS_TEMPLATE.md` — fill on a real 2S/4S box  

## LinkedIn angle (ops rigor)

“FC isn’t always CPU-bound — it’s often **NUMA-bound**. `numactl --cpunodebind=0 --membind=0` is free performance on dual-socket farms when the design fits one node’s RAM.”
