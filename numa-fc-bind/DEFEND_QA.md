# NUMA + `numactl` for Fusion Compiler — from scratch

A simple explanation you can use to **understand** and **defend** this work.
No invented speedups. Mechanism first; numbers only from real multi-socket measurement.

**Companion:** [`README.md`](./README.md) · [`WHITEPAPER.md`](./WHITEPAPER.md) · [`demo/numa_fc_bind.gif`](./demo/numa_fc_bind.gif)

---

## 0. One sentence

**On a machine with two (or more) CPU sockets, make sure Fusion Compiler’s threads and its memory live on the same socket — otherwise the chip spends time waiting on the wire between sockets.**

That is the whole idea.

---

## 1. What is a “socket” and why do we care?

A big server often has **two physical CPU packages** (sockets).

Each socket has:

- its own cores
- its own DRAM (memory DIMMs plugged “next to” that socket)

```
┌─────────────┐          ┌─────────────┐
│  Socket 0   │◄──wire──►│  Socket 1   │
│  cores      │          │  cores      │
│  DRAM 0     │          │  DRAM 1     │
└─────────────┘          └─────────────┘
```

The wire between them is called things like **UPI** (Intel) or **Infinity Fabric** (AMD).

- Reading **DRAM 0 from Socket 0** = **local** (fast path)
- Reading **DRAM 1 from Socket 0** = **remote** (slower; also congests the wire)

That “not all memory is equal” design is called **NUMA**
= **N**on-**U**niform **M**emory **A**ccess.

**Newbie translation:** the computer has two neighborhoods of RAM. Crossing the street costs time.

---

## 2. What does Fusion Compiler do that makes this hurt?

FC (and Innovus-class tools) are **memory hungry**:

- huge netlist / timing / routing databases in RAM
- many threads walking / streaming that data

So the job is often limited by **how fast memory can be fed**, not only by “how many cores.”

If threads run in neighborhood A but the data sits in neighborhood B, every miss pays the street-crossing tax.

**Important:** `top` can still show **100% CPU**.
CPU busy ≠ memory local. That is the trap.

---

## 3. How does Linux accidentally put you in the trap?

Linux often uses **first-touch**:

> The first CPU that **writes** a memory page “owns” which socket’s DRAM that page lives on.

Classic failure mode:

1. One main thread starts on socket 0 and allocates / zeros a huge heap → pages land on DRAM 0
   *(or the opposite: init on socket 1)*
2. Worker threads later run on the other socket
3. Now: hot CPUs on one side, hot data on the other → **remote fills**

The OS can sometimes migrate pages later (AutoNUMA), but for a fat overnight FC job you should not rely on “maybe the kernel fixes it.”

---

## 4. What is the fix? (`numactl`)

`numactl` tells Linux: **run here, allocate memory here.**

```bash
numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

| Flag | Plain English |
|---|---|
| `--cpunodebind=0` | Only use CPUs of NUMA node 0 |
| `--membind=0` | Only allocate RAM from node 0 |

**Same node for brains + memory.**

In this project:

```bash
./scripts/run_with_numactl.sh 0 fc_shell -f run.tcl
```

That is the same idea, with safety checks.

---

## 5. The one safety rule you must never forget

Hard `membind` means: **you may only use that node’s RAM.**

If Fusion Compiler needs **more RAM than that node has free**, you get:

- allocation failures, or
- brutal reclaim / thrashing

So:

> **Only hard-bind when peak RSS fits that node’s free memory (with headroom).**

If unsure:

```bash
POLICY=preferred ./scripts/run_with_numactl.sh 0 fc_shell -f run.tcl
```

`preferred` = “try this node, but spill if needed” (softer, safer when uncertain).

---

## 6. How do you know your machine even has NUMA?

```bash
cd numa-fc-bind
./scripts/numa_report.sh
# or: numactl -H
```

- **1 NUMA node** → binding cannot create a local-vs-remote contrast. (Many laptops/cloud VMs.)
- **2+ NUMA nodes** → this topic is real.

**Defense line:** “I always check topology first. I don’t cargo-cult `numactl` on single-node boxes.”

---

## 7. What can you honestly measure?

### A) Microbench (`compare_numa.sh`) — only on ≥2 nodes

We measure two simple things:

| Name | What it is | Better |
|---|---|---|
| **triad** | STREAM-like bandwidth through a big array (GiB/s) | higher |
| **chase** | random pointer-chase latency (ns) | lower |

**Local** = `membind` same node as CPUs  
**Remote** = CPUs on node 0, memory forced on node 1

On a real 2S box you expect: local triad ↑ and/or chase ↓ vs remote.

On a **1-node** box our script **refuses** to invent numbers. That is correct.

### B) Strongest farm proof (what reviewers respect)

1. Same design / same stage wall time **before vs after** policy
2. `numastat -p $(pgrep -n fc_shell)` showing memory on the bound node
3. Optional: microbench SUMMARY attached as support

**Defense line:** “Microbench shows the memory effect. FC wall time + numastat is the farm claim.”

---

## 8. What the GIF is (and is not)

`demo/numa_fc_bind.gif` teaches the **mechanism**:

- dual socket
- unbound remote fills
- the `numactl` command
- bound local

It is labeled **mechanism · not a benchmark**.
It does **not** prove “2× faster FC.”

**Defense line:** “The GIF explains the failure mode. Numbers come only from multi-socket measurement.”

---

## 9. How this relates to tmpfs + rsync

| Problem | Lever |
|---|---|
| Job slow because of **disk/NFS** (tiny files, scratch) | tmpfs + rsync |
| Job slow because of **remote DRAM** between sockets | `numactl` bind |

Different bottlenecks. Both are **placement**, not new PD algorithms. They can both apply on one job.

---

## 10. Q&A — how people will challenge you

**Q: “Isn’t this just more cores?”**  
A: No. More cores on the wrong side of remote memory can make interconnect worse. This is locality, not core count.

**Q: “Linux caches memory anyway.”**  
A: Page cache helps repeated file reads. It does not remove NUMA remote latency for a heap that already lives on the other socket.

**Q: “Show me your X× speedup.”**  
A: Only from a ≥2-node host (`CLAIM_GATE=CITEABLE=yes`) as microbench, or better from FC stage wall time + `numastat`. I will not quote single-node / emulated numbers.

**Q: “Won’t membind break big designs?”**  
A: Yes if RSS > node free RAM. That’s why we check MemFree and support `preferred`. Hard bind is for jobs that fit.

**Q: “Does this change timing QoR?”**  
A: No. Same binary, same Tcl. You’re changing where threads/pages sit, not the algorithm.

**Q: “Why not always interleave all nodes?”**  
A: Interleave can help huge machine-spanning heaps. For one mid-size FC that fits one node, single-node bind is usually the cleaner policy. Measure; don’t folklore.

**Q: “What do you ship in the repo?”**  
A: Working wrapper + report + hardware-only compare + mechanism GIF + white paper. Compare exits on 1-node hosts on purpose.

---

## 11. 30-second pitch

> Multi-socket servers have local and remote DRAM. Fusion Compiler is memory-heavy. If threads and pages sit on different sockets, you pay UPI every miss while `top` still looks busy. When the working set fits one node’s free RAM, I pin CPUs and memory to that node with `numactl`. I verify topology first, I don’t hard-bind into OOM, and I only cite numbers from real multi-socket measurements or FC wall time with `numastat`.

---

## 12. Checklist before you speak

1. Did I run `numa_report` / `numactl -H`? How many nodes?
2. Does peak RSS fit that node’s MemFree?
3. Am I claiming mechanism, microbench, or FC wall time? (Say which.)
4. Am I on a 1-node machine? → explain only; don’t invent remote-vs-local wins.
