# LinkedIn draft — sched_ext / FC farm layers

Tone: dense, defensible. Do not paste if CLAIM_GATE is empty.

---

**Fusion Compiler farms are a CPU-layer problem long before they are a “custom scheduler” problem.**

On a contended farm node you usually have at least two runnable classes sharing cores:

1. overnight batch — long `fc_shell -f` place / CTS / route workers  
2. interactive-class — engineer debug, Vortex log forensics, heavy queries that are also CPU-bound  

`sched_ext` (upstream since Linux 6.12) is the kernel feature that lets you encode those classes as BPF schedulers — Meta’s production shape for this is `scx_layered` (match on cgroup / comm / nice, per-layer weight & preemption).

I did **not** load a BPF scheduler in this run. This host’s 6.12 kernel has `CONFIG_SCHED_EXT` off (`/sys/kernel/sched_ext` absent, no BTF). So I measured the **same policy shape** with the control plane every farm Linux already has: **cgroup v2 `cpu.weight`**.

Setup: pin both classes to 2 CPUs, 6 always-runnable batch workers + 1 interactive burn (deliberate oversubscription).

| policy | interactive CPU-eq | batch throughput vs flat |
|---|---:|---:|
| flat CFS share | 0.50 | 1.00× |
| nice −5 / +10 | 1.00 | 0.67× |
| SCHED_BATCH on batch | 0.50 | 1.00× ← null |
| **cgroup layers 5:1** | **1.00** | **0.67×** |

Reading that without marketing:

- Layer weights doubled interactive-class CPU share under FC-shaped oversubscription.  
- Batch kept ~⅔ of flat throughput because cgroup bandwidth is **work-conserving** — unused interactive entitlement flows back to batch.  
- `SCHED_BATCH` did nothing for this always-runnable mix. Negative results stay in the post.  
- Short paced wakeups are a bad demo here: CFS/EEVDF already protects them; the share experiment is the honest signal.

**Monday playbook:** put overnight FC under a `batch` cgroup (`cpu.weight=100`) and debug/Vortex under `interactive` (`cpu.weight=500`). When the farm kernel enables `sched_ext`, load `scx_layered` with the same cgroup match rules — policy stays, enforcement moves into BPF.

Repo probe + harness: `sched-ext-fc/` (CLAIM_GATE in `results/`).

#PhysicalDesign #FusionCompiler #Linux #sched_ext #EDA

---

## Why this is tighter than the io_uring draft

- One mechanism, one metric (CPU-eq under oversubscription), one null result (`SCHED_BATCH`).  
- Explicit about what was *not* loaded.  
- Farm action is a cgroup move, not a hope that a closed binary grows new syscalls.
