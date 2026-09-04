# White paper — OS-noise isolation for Fusion Compiler–class jobs

## Abstract

Multi-threaded physical-design tools (Fusion Compiler place / CTS / route) lose wall time to **OS noise**: timer ticks, RCU callbacks, and competing user processes on the same cores. This note documents a reproducible soft-isolation experiment (`taskset` partition under synthetic noise) and the production boot recipe (`isolcpus` + `nohz_full` + `rcu_nocbs`) used in HPC practice. On a 4-CPU cloud host without boot isolation, pinning the FC-proxy away from noise cut synchronized-round **p99** and **wall** to ~0.54× the contended baseline.

## 1. Motivation

EDA farms co-locate long parallel jobs with interactive shells, monitors, and other batch work. Barrier-heavy parallel phases amplify jitter: the team waits for the slowest thread. HPC literature treats this as **OS noise**; recent systems work (including strong Chinese HPC / cloud publications) continues to refine `isolcpus`, full dynticks, and RCU offload for quiet compute sets.

Fusion Compiler cannot be patched here. What methodology can own:

1. CPU partition (pin / cpuset / isolcpus)
2. Tick and RCU hygiene on that partition (`nohz_full`, `rcu_nocbs`)
3. IRQ steering to housekeeping CPUs
4. Thread count matched to the quiet set width

## 2. Method

### 2.1 FC-shaped proxy

`fc_noise_bench` runs `T` worker threads for `R` barrier-synchronized rounds. Each round performs a **fixed iteration count** of CPU work (calibrated to ~`burst_us` of uninterrupted time). Team round latency is the **max** thread duration that round. Fixed work is essential: a wall-clock-gated spin would hide preemption.

A separate `--mode noise` process burns CPU (optionally with sleep/yield) to emulate co-tenants.

### 2.2 Policies

| Policy | Job CPUs | Noise |
|---|---|---|
| flat_quiet | all | none |
| pin_only | job set | none |
| flat_contend | all | yes, all CPUs |
| pin_split | job set | yes, noise set only |

### 2.3 Production recipe (reboot)

```text
isolcpus=<job> nohz_full=<job> rcu_nocbs=<job>
taskset -c <job> fc_shell -f run.tcl
```

Leave housekeeping CPUs for OS, ssh, IRQs, license heartbeats. See `scripts/print_boot_cmdline.sh` and `configs/irq_affinity.example`.

## 3. Results (this host)

Host: 4 vCPUs, kernel 6.12, **no** `isolcpus` in cmdline. Demo uses soft `taskset` only.

| policy | wall_s | p99 round (µs) |
|---|---:|---:|
| flat_quiet | 0.811 | 2163 |
| pin_only | 0.809 | 2126 |
| flat_contend | 1.530 | 4099 |
| pin_split | 0.822 | 2195 |

**CLAIM_GATE PASS:** pin_split / flat_contend ≈ 0.54 on both wall and p99.

Interpretation: under contention, **keeping noise off the job CPUs** restores near-quiet behavior. Full `nohz_full` / `rcu_nocbs` are additive on a rebooted farm node and are **not** measured here.

## 4. Limitations

- Soft isolation ≠ dyntick-idle isolation.
- Proxy ≠ Synopsys FC internal thread pool.
- Wins are for CPU-bound synchronized phases; NFS / license / memory cliffs dominate elsewhere.
- Oversubscribing 32 FC threads onto 8 isolated cores reintroduces self-noise.

## 5. Reproduction

```bash
cd fc-os-noise && make && ./examples/compare_all.sh
cat results/SUMMARY.txt results/CLAIM_GATE.txt
```

## 6. Conclusion

OS-noise isolation is a legitimate, source-backed accelerator for FC-class jobs when the node is dedicated and thread width matches the quiet set. This repository makes the **pinning effect** instant to try and the **boot recipe** copy-paste ready for methodology owners.
