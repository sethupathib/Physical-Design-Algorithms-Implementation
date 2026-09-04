# LinkedIn draft — OS-noise isolation for Fusion Compiler jobs

Tone: dense, farm-actionable. Cite CLAIM_GATE numbers only.

---

**Fusion Compiler doesn’t need a new binary to hate OS noise — your farm node already creates it.**

Place / CTS / route are multi-threaded and barrier-heavy. When other jobs, timer ticks, and RCU callbacks share those cores, the team waits on the slowest thread. HPC’s answer is a quiet CPU set:

```text
isolcpus=8-15 nohz_full=8-15 rcu_nocbs=8-15
taskset -c 8-15 fc_shell -f run.tcl
```

I built an instantly runnable probe (`fc-os-noise/`) that measures the **pinning half** without a reboot: FC-shaped synchronized workers vs synthetic noise.

On a 4-CPU host (no isolcpus in cmdline):

| policy | wall | round p99 |
|---|---:|---:|
| contended (noise shares all CPUs) | 1.53 s | 4099 µs |
| **pin_split** (job on 2–3, noise on 0–1) | **0.82 s** | **2195 µs** |

≈ **0.54×** wall and p99 — CLAIM_GATE PASS.

What this is **not**: a claim that `nohz_full` was measured here (it wasn’t — needs reboot). What it **is**: proof that **keeping co-tenants off the job CPUs** restores near-quiet behavior for synchronized parallel work — and a copy-paste grub recipe for the full HPC stack on a dedicated farm node.

Match FC thread count to the quiet set. Move IRQs to housekeeping CPUs. Measure the same deck before/after.

#PhysicalDesign #FusionCompiler #Linux #HPC #EDA

---
