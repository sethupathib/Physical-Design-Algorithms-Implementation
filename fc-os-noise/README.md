# fc-os-noise — Isolate Fusion Compiler–class jobs from OS noise

**Working code + white paper + farm playbook.**  
Soft-isolation demo runs instantly (no reboot). Full `isolcpus` / `nohz_full` / `rcu_nocbs` documented for farm nodes.

| Deliverable | Path |
|---|---|
| Bench + scripts | `src/`, `scripts/`, `examples/` |
| White paper | [`WHITEOBER.md`](./WHITEOBER.md) |
| Defense Q&A | [`DEFEND_QA.md`](./DEFEND_QA.md) |
| LinkedIn draft | [`LINKEDIN_DRAFT.md`](./LINKEDIN_DRAFT.md) |
| Measured SUMMARY | [`results/SUMMARY.txt`](./results/SUMMARY.txt) |
| CLAIM_GATE | [`results/CLAIM_GATE.txt`](./results/CLAIM_GATE.txt) |

---

## The problem (one paragraph)

Fusion Compiler place / CTS / route are multi-threaded and barrier-heavy. On a shared farm node, unrelated processes, timer ticks, and RCU callbacks steal cycles from those threads. Wall time stretches even when `top` looks “busy.” HPC practice isolates CPUs:

```text
isolcpus=8-15 nohz_full=8-15 rcu_nocbs=8-15
taskset -c 8-15 fc_shell -f run.tcl
```

This repo lets you **measure the pinning half today** (taskset split under synthetic noise) and **apply the full boot recipe** on a real farm node after one reboot.

---

## Quick start (instant)

```bash
cd fc-os-noise
make
./scripts/probe_isolation.sh
./examples/compare_all.sh
cat results/SUMMARY.txt results/CLAIM_GATE.txt
```

### Measured on this host (4 CPUs, no `isolcpus` in cmdline)

| policy | wall_s | round p99 (µs) |
|---|---:|---:|
| flat_quiet (no noise) | 0.81 | 2163 |
| pin_only (no noise) | 0.81 | 2126 |
| **flat_contend** (noise shares all CPUs) | **1.53** | **4099** |
| **pin_split** (job 2–3, noise 0–1) | **0.82** | **2195** |

`CLAIM_GATE`: **PASS** — `pin_split` ≈ **0.54×** wall and p99 vs `flat_contend` (`POSTABLE_SOFT_ISOLATION=yes`).

---

## Farm playbook (real FC)

```bash
# 1) Print recommended cmdline (housekeeping 0-7, job 8-15)
./scripts/print_boot_cmdline.sh 8-15 0-7

# 2) Add to GRUB_CMDLINE_LINUX, update-grub, reboot
# 3) Verify
cat /sys/devices/system/cpu/isolated
# 4) Steer IRQs (see configs/irq_affinity.example)
# 5) Run FC on the quiet set — match thread count to width
./scripts/run_fc_isolated.sh 8-15 fc_shell -f run.tcl
```

---

## Policies (demo)

| Name | Meaning |
|---|---|
| `flat_quiet` | FC-proxy alone on all CPUs |
| `pin_only` | FC-proxy pinned, no noise |
| `flat_contend` | FC-proxy + noise share all CPUs |
| `pin_split` | FC-proxy on `JOB_CPUS`, noise on `NOISE_CPUS` |

---

## Non-claims

- Did not reboot this host with `isolcpus` / `nohz_full` / `rcu_nocbs`.
- Did not modify Synopsys Fusion Compiler.
- Did not prove wins on I/O-bound or license-bound phases.
- Soft `taskset` ≠ full dyntick isolation — it proves the **partition** effect under contention.

---

## Layout

```
fc-os-noise/
├── src/fc_noise_bench.c
├── scripts/{probe_isolation,run_one_policy,compare_all,
│            run_fc_isolated,print_boot_cmdline}.sh
├── configs/irq_affinity.example
├── examples/compare_all.sh
├── results/
├── README.md
├── WHITEOBER.md
├── DEFEND_QA.md
└── LINKEDIN_DRAFT.md
```
