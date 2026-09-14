# LINKEDIN_DRAFT — Accelerating EDA workloads on AMD EPYC (TuneD / epyc-eda)

**Status:** corrected rewrite (post-publication fix for inverted migration-cost thesis + profile conflation)  
**CLAIM_GATE:** no speedup % in this post — mechanism + provenance only (safe on SKIP hosts)

---

## Post body (ready to paste)

Accelerating EDA workloads on AMD EPYC —

In earlier posts, we touched on sched_ext, vm dirty ratio, NUMA bind, perf-tmpfs-rsync, and related OS levers.

This one is about **TuneD** — and specifically what the **`epyc-eda`** profile does (and does *not*) do when you run EDA on an AMD EPYC socket.

### TuneD primer

TuneD is a Linux system-tuning daemon. Instead of hand-editing a pile of sysctls, you activate a **named profile**: a blueprint that sets governors, VM knobs, scheduler parameters, and related settings for a workload class.

Vendors ship profiles for throughput, latency, HPC, cloud guests, and more. On RHEL/Alma/Rocky **8.10+**, one of those profiles is **`epyc-eda`**.

### What `epyc-eda` actually is

Primary sources (AMD 9004 HPC guide §9.4 + the shipped `tuned` package) are narrower than most LinkedIn summaries:

```text
epyc-eda  =  throughput-performance
          +  one AMD scheduler override
```

| Knob | `throughput-performance` (AMD) | `epyc-eda` |
|------|--------------------------------|------------|
| `sched_migration_cost_ns` | 5 000 000 (5 ms) | **10 000 (10 µs)** |

That is a **500×** change in how long CFS treats a task as “cache-hot” before it is willing to **migrate** it.

### What that knob means (the important bit)

- **High** migration cost → stickier threads → better locality for long, stable runs; slower packing onto **idle** cores.
- **Low** migration cost (`epyc-eda`) → CFS rebalances **more eagerly**.

AMD’s documented EDA rationale: many EDA farms look like **bursty, uneven fan-out**. The stock AMD throughput default (5 ms) can leave cores idle while work waits. Their testing preferred **10 µs** so runnable work spreads onto free cores faster.

So `epyc-eda` is **not** “pin my heavy sim thread to one CCD to protect L3.”  
It is the opposite policy bet: **don’t strand idle cores**.

(If your job is a long, cache-hot, locality-bound single thread, sticky may still win — measure.)

### What you still get from the parent profile

Because `epyc-eda` **includes** `throughput-performance`, you also inherit that baseline, including typically:

1. **CPU governor / energy preference → performance** — prefer sustained clocks over powersave dithering during short gaps.  
2. **VM writeback lean** — e.g. higher `vm.dirty_ratio`, lower swappiness than desktop defaults.  
3. **Disk readahead floor** and related throughput-oriented defaults.

### What `epyc-eda` does *not* magically do

Worth stating explicitly (we got this wrong in an earlier draft):

- It does **not** turn on **THP always** / force 1 GB pages — that pattern lives in profiles like **`hpc-compute`**, not in `epyc-eda`.
- It does **not**, by itself, disable **C3/C6** the way some latency/HPC blueprints do.
- It does **not** replace **BIOS** choices AMD calls out for EDA: SMT off, NPS (often 2), Power Determinism, Infinity Fabric P-state policy, prefer 1P or pin on 2P.
- It does **not** pick **F vs X (3D V-Cache)** SKUs for you — RTL/formal-class vs frequency-bound PD steps are still a hardware decision.

Wrong SKU or wrong NPS will dominate any TuneD delta.

### How to apply (RHEL-family)

```bash
sudo tuned-adm profile epyc-eda
tuned-adm active
tuned-adm verify
# confirm the knob landed (path varies by kernel):
#   /proc/sys/kernel/sched_migration_cost_ns
#   or /sys/kernel/debug/sched/migration_cost_ns
```

Pre-8.10: use `throughput-performance` (or equivalent) and set migration cost to **10000** manually — as AMD documents.

### Our lab notes

We mirrored the AlmaLinux `tuned` profile, wrote apply/verify/A-B scripts, and put a **CLAIM_GATE** in front of any public speedup sentence:

https://github.com/sethupathib/Physical-Design-Algorithms-Implementation/blob/cursor/epyc-eda-tuned-6f4a/epyc-eda-tuned/WHITEPAPER.md

### Thesis

Same philosophy we keep repeating (Steve Varsano’s lane): **educate hard, then let the buyer make a high-impact call**.

OS tuning is necessary hygiene. It is not a substitute for tool methodology, log forensics, or knowing whether your walltime is scheduler packing, I/O, or the engine itself — which is the problem space we build **Vortex** around.

Contact: sethu@vortexmlabs.com — product detail and PoC trials.

#silicon #EDA #EPYC #Linux #PhysicalDesign #PerformanceEngineering

---

## Sources (keep in post or first comment)

1. https://documentation.suse.com/sles/15-SP5/html/SLES-all/cha-tuning-tuned.html  
2. https://docs.amd.com/api/khub/documents/NgOfoW49HKdzztTeLBbekA/content (§9.4 EDA)  
3. https://docs.nvidia.com/dgx/dgx-el10-user-guide/modifying-tuned.html  
4. Lab WHITEPAPER (above)

---

## Suggested clarification comment (if the old post stays up)

> Correction on scheduling: `epyc-eda` **lowers** `sched_migration_cost_ns` (5 ms → 10 µs) vs AMD’s throughput default — encouraging **faster** migration onto idle cores for bursty EDA fan-out, not CCD pinning for L3. THP-always / zone-reclaim style knobs are other profiles (e.g. `hpc-compute`). Updated write-up in the WHITEAPER link.
