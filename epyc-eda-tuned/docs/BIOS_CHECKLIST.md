# BIOS_CHECKLIST — AMD EDA-oriented platform settings

Source baseline: AMD EPYC **9004** HPC Tuning Guide §9.4 *EDA Configuration*  
(plus general BIOS chapters). **OEM menus differ**; map by meaning, not label.

Use this as a **signoff checklist** beside `tuned-adm profile epyc-eda`. OS tuning does not fix a wrong BIOS.

---

## 1. Platform topology

| Item | Recommended lean | Notes / verify |
|------|------------------|----------------|
| Socket count | Prefer **1P** for EDA | 2P OK if jobs pinned to one socket; AMD cites ~**5%** loss otherwise |
| Memory population | Match core count / bandwidth needs | Low-core F-parts may not need all channels filled |
| DIMM symmetry | Symmetric per channel | Check `dmidecode -t memory`, `numactl -H` |

---

## 2. Core / SMT

| Setting | EDA lean | Rationale |
|---------|----------|-----------|
| **SMT / Simultaneous Multithreading** | **Disabled** | Many EDA codes under-thread; prefer full core for each worker process |
| Core Performance Boost | Enabled (typical) | Confirm turbo not thermally clipped |
| 3D V-Cache mode (X parts) | Per OEM / workload | X-parts for cache-sensitive tools |

Verify in OS after boot:

```bash
lscpu | grep -E 'Thread|CPU\(s\)|Socket|Model name'
# Thread(s) per core: 1  => SMT off
```

---

## 3. Power / determinism

| Setting | EDA lean | Rationale |
|---------|----------|-----------|
| **Determinism mode** | **Power Determinism** | Lets efficient parts run closer to max speed within TDP |
| Power profile | Performance / HPC | Align with TuneD `governor=performance` |
| APBDIS / DF C-states / IF P-states | Per AMD EDA note: **Infinity Fabric P-states Disabled** | Reduce IF frequency dithering |
| Global C-states | Site policy | Latency vs power; don’t copy HPC blind |

---

## 4. NUMA (NPS)

| Setting | EDA lean | When to deviate |
|---------|----------|-----------------|
| **NPS (NUMA Per Socket)** | **2** | Default AMD EDA testing lean |
| NPS=1 | Mixed batch / many workload types | More consistent behavior across job mix |
| NPS=4 | Usually **not** preferred vs NPS=2 on non-X 9004 per AMD EDA note | Measure |

Verify:

```bash
numactl -H
ls /sys/devices/system/node/node*/meminfo | wc -l
```

---

## 5. Memory controllers / prefetchers

| Setting | Lean | Note |
|---------|------|------|
| Memory speed | Max JEDEC / validated | Bandwidth-sensitive tools (analog, some sim) |
| Prefetchers | OEM default unless A/B says otherwise | Don’t disable casually |

---

## 6. Security mitigations

Spectre/MDS mitigations can cost single-thread performance. Corporate policy may force them on. Record mitigation state in every CLAIM_GATE inventory:

```bash
grep . /sys/devices/system/cpu/vulnerabilities/* 2>/dev/null | head
```

Never disable mitigations for a LinkedIn graph.

---

## 7. Signoff table (copy into results/)

| Check | Expected | Actual | Pass? |
|-------|----------|--------|-------|
| SMT | Off (1 thread/core) | | |
| NPS | 2 (or documented 1) | | |
| IF P-states | Disabled | | |
| Determinism | Power | | |
| Tuned profile | epyc-eda | | |
| migration_cost_ns | 10000 | | |
| 1P or pinned 2P | Documented | | |

Stamp: `results/bios_signoff_<date>.md`
