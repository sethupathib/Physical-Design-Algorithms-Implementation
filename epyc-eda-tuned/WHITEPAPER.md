# WHITEPAPER — `epyc-eda` TuneD profile: mechanism, pedigree, and measurement

**Status:** living document for the `epyc-eda-tuned` lab  
**Audience:** OS/perf engineers and PD/EDA grid owners who refuse handwavy “tuning tips”

---

## 1. Executive summary

The TuneD profile `epyc-eda` (RHEL 8.10+, `tuned ≥ 2.22.1`) is AMD’s OS-level recommendation for Electronic Design Automation compute hosts on EPYC. Mechanically it is almost entirely **`throughput-performance`**, plus one deliberate AMD-only override:

```text
sched_migration_cost_ns:  5_000_000  →  10_000
```

That single change alters how aggressively the Completely Fair Scheduler (CFS) will **migrate runnable tasks onto idle CPUs** after a task last ran. AMD’s published EDA guidance states that the stock AMD throughput setting is **too sticky** for EDA-shaped work.

This white paper:

1. Reconstructs the profile from a **checksummed distro RPM** (not folklore).
2. Explains the scheduler knob in kernel terms.
3. Places OS tuning beside **BIOS / SKU** guidance (where the large effects usually live).
4. Defines a **CLAIM_GATE** microbenchmark so LinkedIn/posts cannot outrun evidence.

---

## 2. Pedigree and provenance

| Fact | Evidence |
|------|----------|
| Profile added | `tuned` changelog 2.22.1-2 — “profiles: added epyc-eda profile” (RHEL-27528) |
| Distro mirror used here | AlmaLinux 8.10 `tuned-2.22.1-5.el8_10.noarch.rpm` |
| Files in-repo | `profiles/epyc-eda/tuned.conf` (verbatim) |
| Independent confirmation | AMD EPYC 9004 HPC Tuning Guide §9.4 *EDA Configuration* names `epyc-eda` and the `10000` value |

### 2.1 Verbatim profile

```ini
[main]
summary=Optimize for EDA compute workloads on AMD EPYC CPUs
description=Configures virtual memory, CPU governors, and network settings for EDA compute workloads.
include=throughput-performance

[scheduler.amd]
type=scheduler
# Allow processes to rapidly move between cores to avoid idle time and maximize CPU usage
sched_migration_cost_ns=10000
```

Comment in the profile is normative intent: **reduce idle time via faster migration**, not “increase IPC via magic.”

### 2.2 What `include=throughput-performance` pulls in

From the mirrored parent profile (abridged categories):

- **CPU:** `governor=performance`, energy-performance preference/bias toward performance, `min_perf_pct=100`
- **ACPI:** `platform_profile=performance` (where supported)
- **Disk:** readahead floor `>= 4096` KiB
- **VM:** `vm.dirty_ratio=40`, `vm.dirty_background_ratio=10`, `vm.swappiness=10`
- **Net:** `net.core.somaxconn >= 2048`
- **Scheduler (generic):** larger min/wakeup granularity (throughput-oriented)
- **Scheduler (AMD match):** `sched_migration_cost_ns=5000000` — **then overridden by epyc-eda**

Contrast: `hpc-compute` includes **`latency-performance`**, forces THP, enables zone reclaim, busy-poll — a different philosophy. Do not casually substitute `hpc-compute` for EDA grids.

---

## 3. Kernel mechanism: `sched_migration_cost_ns`

### 3.1 Meaning

After a task runs on a CPU, CFS considers it **cache-hot** for `sched_migration_cost_ns` nanoseconds. While hot, the load balancer is **less willing** to move it. Higher values → stickier tasks → better locality for long-running stable threads; worse packing when work is bursty and cores go idle.

### 3.2 Sysctl vs debugfs

On older kernels the knob lived at:

```text
/proc/sys/kernel/sched_migration_cost_ns
```

On newer kernels many `sched_*` tunables moved under debugfs, typically:

```text
/sys/kernel/debug/sched/migration_cost_ns
```

TuneD’s **scheduler plugin** abstracts the path. Manual `sysctl` may silently fail on new kernels; prefer TuneD or write the debugfs node (root + debugfs mounted).

### 3.3 Order-of-magnitude change

| Profile | Value | Human |
|---------|-------|-------|
| throughput-performance (AMD) | 5 000 000 ns | 5 ms |
| epyc-eda | 10 000 ns | 10 µs |
| Ratio | 500× | — |

This is not a 5% tweak. It is a **policy flip** from sticky to migratory.

---

## 4. Why EDA is a different shape than “server throughput”

Typical EDA grid characteristics (qualitative, but load-shaping matters):

| Property | Implication for CFS |
|----------|---------------------|
| Many processes / threads with uneven runtimes | Idle cores appear while other cores stay saturated |
| Often **not** heavily multi-threaded inside one process (AMD: disable SMT) | Per-thread performance + packing dominate |
| Burst phases (elaborate → wait → fanout) | Transient imbalance is normal |
| Large memory footprints | Migration cost ≠ NUMA story; still need NPS/pinning discipline |

AMD’s own wording in §9.4: the 5 ms AMD throughput default is **detrimental** for EDA; testing favored **10 000**.

**Important:** that statement is AMD’s lab claim on their workloads. This repo’s CLAIM_GATE re-tests the *mechanism* on *your* host with a synthetic fan-out. Passing AMD’s marketing slide is not the same as passing CLAIM_GATE.

---

## 5. The rest of AMD’s EDA stack (do not pretend OS-only)

OS TuneD is the easy checkbox. Larger levers from AMD §9.4:

### 5.1 Platform

- Prefer **1P** for EDA; **2P** without socket pinning can cost ~**5%**.
- Memory channel fill: not always “populate all 12” on low-core F-parts.

### 5.2 BIOS

| Setting | AMD EDA lean |
|---------|----------------|
| SMT | **Disabled** (EDA often under-threads; prefer full core perf) |
| Determinism | **Power Determinism** (energy-efficient samples can boost harder within TDP) |
| NPS | **2** typical; **1** for mixed batch / consistency |
| Infinity Fabric P-states | **Disabled** |

### 5.3 SKU selection (4th Gen examples)

Frequency-heavy F-parts vs 3D V-Cache X-parts differ by tool class (RTL sim vs place/route vs STA). See `docs/WORKLOAD_SKU_MAP.md`. Wrong SKU swamps any TuneD delta.

---

## 6. Measurement methodology in this lab

### 6.1 Design constraints

Lessons carried from OS-noise work:

- **Fixed work**, not “spin until 100 ms wall” (preemption must stretch completion time).
- Report **median** over outer trials.
- Restore knobs after A/B.
- **SKIP ≠ PASS** when the host cannot write the knob.

### 6.2 `fanout_bench` spread mode

1. Create `T = nproc` workers.
2. Affinitize all to `pin_cpus ≈ nproc/4` CPUs.
3. Warm fixed burn (imbalance / piled runqueues).
4. Clear affinity (all CPUs).
5. Each thread completes `work_units` fixed burns.
6. Makespan = max per-thread phase-2 time; outer median.

**Prediction under AMD’s thesis:** after unpin, low migration cost spreads work onto idle cores faster → lower makespan.

### 6.3 Thresholds

- **PASS:** `median_low / median_high ≤ 0.97` (≥3% faster)
- **INCONCLUSIVE:** ratio in (0.97, 1.02]
- **FAIL:** ratio > 1.02

3% is deliberately above typical timer noise for this microbench class on multi-core VMs; adjust only via `configs/claim_gate.yaml` with justification.

### 6.4 What we do **not** measure here

Vendor tool walltime (NDA, license, multi-hour). Those belong in a private appendix appendix with the same A/B discipline once CLAIM_GATE mechanism PASS exists.

---

## 7. Operational runbook (condensed)

```bash
# Inventory
./scripts/detect_env.sh

# RHEL 8.10+ with package profile
sudo tuned-adm profile epyc-eda
tuned-adm verify
./scripts/verify_profile.sh

# Or install mirrored profile
sudo ./scripts/install_local_profile.sh

# Pre-8.10 / no package profile: parent + manual knob
sudo tuned-adm profile throughput-performance
sudo ./scripts/apply_epyc_eda.sh manual-sysctl

# Publishability
sudo ./scripts/claim_gate.sh
```

Full command matrix: `docs/COMMAND_RUNBOOK.md`.

---

## 8. Threats to validity

1. **Noisy neighbors** on shared VMs inflate variance → prefer bare metal / quiet queues.
2. **Governor / turbo / thermal** shifts between A/B legs → dump cpufreq and pin power profile.
3. **NUMA balancing** interactions on 2P — migration cost is not a NUMA API.
4. **debugfs unavailable** under lockdown/Secure Boot policies → TuneD may also fail to apply scheduler plugin settings.
5. **Synthetic ≠ Spectre** — mechanism evidence ≠ tool KPI.
6. **Profile drift** — always diff running system against `profiles/` mirrors.

---

## 9. Relationship to other OS work

| Work | Layer | Question |
|------|-------|----------|
| `epyc-eda` (this lab) | CFS migration policy | Pack bursty work faster? |
| `isolcpus` / `nohz_full` / OS-noise labs | Interference isolation | Protect FC-class latency? |
| cgroup / `sched-ext` experiments | Policy programming | Custom placement? |

These are complementary. Isolating a place job onto quiet CPUs does not obsolete migration policy for the compile/sim farm, and vice versa.

---

## 10. Conclusions

1. `epyc-eda` is a **documented, tiny, high-leverage overlay**: 500× reduction in migration stickiness on top of throughput-performance.
2. Treat AMD’s EDA section as **hypothesis + BIOS/SKU context**, not as a substitute for measurement.
3. This repository exists so every public sentence either (a) cites mirrored primary sources, or (b) carries a CLAIM_GATE stamp.

---

## Appendix A — RPM extraction record

See `profiles/PROVENANCE.md` for package URL and SHA256 of the RPM used to seed mirrors.

## Appendix B — Primary sources

1. AMD, *High Performance Computing Tuning Guide for AMD EPYC 9004 Series Processors*, §9.4 EDA Configuration.  
2. AlmaLinux / RHEL `tuned` package changelog (epyc-eda, RHEL-27528).  
3. Red Hat, *Monitoring and managing system status and performance* — TuneD scheduler plugin parameter mapping.
