# LinkedIn post draft — NUMA & Fusion Compiler

Use / edit freely. Keep proprietary customer scripts out; public `numactl` is fine.

---

**Option A — short**

Multi-socket servers don't make EDA tools faster by magic.

If Fusion Compiler (or Innovus) allocates DRAM on the wrong NUMA node while your threads run on another, you pay remote memory latency — every cycle, every GB of netlist/timing data.

The fix is boring and powerful:

```bash
numactl --cpunodebind=0 --membind=0 <tool> ...
```

Pin cores + memory to the **same** node. Measure with STREAM + pointer chase before you trust the flag.

I open-sourced a small lab: NUMA-EDA-Bench (in my Physical-Design-Algorithms-Implementation repo) — theory, scripts, and a STREAM-like microbench so you can see local vs remote bandwidth yourself.

Methodology > folklore.

---

**Option B — denser**

DeepSeek (and half of HPC) already know this: `numactl --cpunodebind=N --membind=N`.

PD tools are memory-bandwidth and latency hungry. On dual-socket boxes, first-touch + scheduler migration can put hot working sets on the remote node. You then "scale cores" and wonder why wall-clock barely moves.

What to do in practice:
1. `numactl -H` — know your topology
2. Pin tool + mem to one node for mid-size jobs
3. Consider `--interleave=all` only when the footprint truly exceeds one node's DRAM
4. Measure — don't cargo-cult

Repo lab: NUMA-EDA-Bench — docs + `numa_mem_bench` + compare scripts.

If your farm still runs FC unbound on 2S/4S machines, this is free performance waiting on the floor.

---

**Image idea for the post:** screenshot of `numactl -H` next to a bar chart of local vs remote STREAM triad (from your own run).
