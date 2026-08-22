# NUMA theory for Physical Design / signoff machines

## 1. What NUMA is

**NUMA** = Non-Uniform Memory Access.

On multi-socket servers, each socket (NUMA node) has:

- its own CPU cores  
- its own DRAM controllers and DIMMs  

Cores can still read the other socket’s memory, but that traffic crosses an interconnect
(Intel UPI/QPI, AMD Infinity Fabric). Cost:

- higher latency  
- lower effective bandwidth under load  
- contention with other processes’ remote traffic  

So “memory bandwidth” is not one number — it is **local vs remote**.

## 2. Why EDA cares

Fusion Compiler, Innovus, PrimeTime (large designs), extraction, etc.:

- allocate multi‑GB–TB working sets  
- stream netlists, timing graphs, routing DBs  
- spawn worker threads that touch shared heaps  

If threads run on node 0 while the heap was first touched / allocated on node 1
(or the OS scattered pages), the job becomes **interconnect-bound**.
`top` still shows 100% CPU; wall time is bad. That confuses people who only watch CPU%.

## 3. Linux placement knobs

### Topology

```bash
numactl -H
lscpu | grep NUMA
ls /sys/devices/system/node
```

### Policies (`numactl`)

| Flag | Meaning |
|---|---|
| `--cpunodebind=0` | run only on CPUs of node 0 |
| `--membind=0` | allocate only from node 0 memory |
| `--localalloc` | allocate on the node of the touching CPU |
| `--preferred=0` | prefer node 0, spill elsewhere if needed |
| `--interleave=0,1` | round-robin pages across nodes |

DeepSeek-style recipe for **one fat FC** that fits in one node’s RAM:

```bash
numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

## 4. First-touch and why binding matters

Linux often uses **first-touch**: the node of the CPU that first writes a page owns it.

Patterns that create remote access:

1. Master thread on node 0 allocates and zeros a huge array  
2. Worker threads pinned later to node 1 pound that array → remote  

Or the opposite: OS load-balances threads across sockets while heap is local to one.

`membind` + `cpunodebind` remove ambiguity for overnight runs.

## 5. When NOT to membind a single node

- Peak RSS of FC **> free memory on that node** → fail / thrash  
- Multi-die flows intentionally sized for whole machine  
- Shared license servers / NFS already dominate — fix I/O first  

Measure:

```bash
numastat -p $(pgrep -n fc_shell)
# look at node0 vs node1 memory used by the process
```

High `foreign` / remote hits in `perf c2c` / `numastat` → NUMA problem.

## 6. Related PD ops stack (same “chamber acceleration” family)

| Layer | Tool |
|---|---|
| Disk | local NVMe / `TMPDIR`, not NFS scratch |
| CPU idle | `mpstat -P ALL` |
| Parallel files | GNU `parallel` |
| **Memory locality** | **`numactl`** |
| Huge pages (advanced) | `transparent_hugepage` / explicit HUGETLB (site-specific) |

## 7. Microbench interpretation

`numa_mem_bench` in this repo reports:

- **STREAM-like triad bandwidth** (GB/s)  
- **pointer-chase latency** (ns/hop)  

On true dual-socket hardware you should see:

- `cpunodebind=0 membind=0` ≫ `cpunodebind=0 membind=1` for bandwidth  
- higher latency on remote chase  

On **1-node VMs/clouds**, numbers will be similar for all policies — still useful to
validate the wrapper and teach the workflow.

## 8. Production wrapper rules of thumb

1. Discover nodes; refuse `membind` if free mem on node < estimated peak RSS × 1.2  
2. One heavy EDA job per node when possible  
3. Log `numactl -H`, policy, host, and `numastat` snapshot into the run manifest  
4. Don’t cargo-cult — **measure** before and after on a real block  

## 9. Vortex / log-forensics aside

NUMA policy changes **tool runtime**. It does not replace log forensics.
Faster FC still emits multi‑GB logs — search/compare/score remains a separate problem.
