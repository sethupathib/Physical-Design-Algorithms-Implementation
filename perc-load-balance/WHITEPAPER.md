# WHITEPAPER — Accelerating PERC/DRC without ignoring licenses and slots

## 1. Problem

Distributed Calibre **DRC** and **PERC** jobs are marketed as “add `-turbo` and remote hosts.” On shared LSF farms (including TSRI EDA Cloud 2.0-class environments), that slogan collides with two constraints that are not optional:

1. **License tokens** — the job may never acquire enough features for master + MT/remote workers.  
2. **Job-slot semantics** — capacity is not “the cluster has 2k cores”; it is **your** `max_slots_per_user`, with **1 slot = 1 core** (TSRI guide).

Engineers who only tune CPU/memory requests systematically over-parallelize, then debug “pending forever,” random aborts, or terrible `CPU_EFFICIENCY`.

## 2. Baseline (TSRI EDA Cloud 2.0 User Guide r1.3)

Relevant facts we encode as defaults in `configs/farm.yaml`:

| Fact | Implication |
|------|-------------|
| Queues `int` / `bat.m` / `bat.l` with max **128 slots/user** | Parallelism is capped per user, not per wish |
| 1 job slot ↔ 1 CPU core | `remote_hosts × cpu_per_host` is slot spend |
| Prefer `bat.l` + multi-host multi-thread for large work | Throughput via distribution, not one fat node only |
| Calibre hierarchical DRC: `-turbo N`; remote Concurrent Jobs = M | Child cores ≈ **M × N** (guide example 3×4=12) |
| Remote Calibre master often needs **1** core | Don’t `-n 64` the master “just in case” |
| `Number of Hosts × CPU per Host` must not exceed user slot max | Otherwise **job never dispatches** (ICV section; same math for Calibre) |
| `-R select[mem>N]` selects hosts; **memory not reserved** | Contention + OOM risk remain |
| Hyperflex/hyper can inflate memory → LSF kill | Prefer off until measured |
| After run: `bacct -l` — HOG_FACTOR ≈ cores, CPU_EFFICIENCY ≈ 100% | Feedback into next plan |

PERC follows the same **distribution physics** as hierarchical DRC on LSF; ruledeck and license feature names differ by site.

## 3. The two silent killers

### 3.1 License tokens

A CPU-feasible plan can still be license-infeasible. Typical failure modes:

- Master starts; remote slaves abort as MT features exhaust.  
- Job sits waiting on license, misread as “LSF slow.”  
- Two users’ “reasonable” 8×8 jobs exhaust a 64-token MT pool.

This lab treats license availability as a **hard constraint** in the planner. Token rates in `farm.yaml` are **knobs you must calibrate** with `lmstat` on your contract — we do not invent Siemens pricing.

### 3.2 Per-slot semantics

“Ask for 16 hosts × 8 threads” is not 16 machines of vague capacity. Under TSRI semantics it is **128 child slots** plus master — which equals the **entire** default per-user ceiling with **zero** headroom. The planner refuses or reduces such asks.

## 4. Method in this repository

```text
farm.yaml (caps) + job_*.yaml (intent)
        │
        ▼
plan_calibre_job.py  → FEASIBLE | REDUCED | BLOCKED
        │
        ├─ simulate_dispatch.py   (naive CPU view vs full view)
        └─ emit_launch_bundle.py  (run.sh + NOTES checklist)
```

Search order when reducing: keep turbo when possible, reduce remote slaves first (license/slot bind often scales with `slaves × turbo`).

## 5. Accelerating PERC specifically

PERC walltime improves when:

1. The job **actually runs** at planned concurrency (licenses + slots satisfied).  
2. Concurrency matches **parallel efficiency** (bacct HOG/efficiency), not vanity `-turbo`.  
3. Memory policy matches design size (no silent LSF kills from hyper + underspecified RAM).

So “accelerate PERC” here means **feasible high-efficiency parallelism**, not magic flags.

## 6. CLAIM_GATE

Public claims allowed only if `make smoke` passes and any site numbers are labeled **calibrated** vs **assumed**. See `CLAIM_GATE.md`.

## 7. Non-goals

- Replacing Siemens documentation or TSRI official support  
- Guaranteeing PERC QoR or runtime regressions vs a golden  
- Auto-submitting production jobs without human review of `NOTES.md`
