# DEFEND_QA — adversarial questions for `epyc-eda`

Use this before posting or customer reviews. Short answers first; evidence pointers second.

---

### Q1. Isn’t this just `throughput-performance` with marketing?

**A.** Almost — and that honesty is the point. The only intentional delta in the shipped profile is `sched_migration_cost_ns=10000` on the AMD scheduler instance. Everything else is inherited. If someone claims “EPYC EDA profile rewrites the kernel,” they are wrong. Evidence: `profiles/epyc-eda/tuned.conf`.

---

### Q2. Why would *less* cache stickiness help?

**A.** Stickiness helps when the same hot thread runs for a long time on one core. EDA grids often look like **many uneven tasks** and **transient idle cores**. A 5 ms hot window can delay packing onto those idle cores. AMD measured EDA-like loads preferring 10 µs. Evidence: AMD 9004 HPC guide §9.4; profile comment in tuned.conf.

---

### Q3. Did you prove place-and-route gets faster?

**A.** No. CLAIM_GATE proves a **synthetic spread/makespan** effect under controlled migration-cost A/B, or it **SKIP**s. Tool KPI claims need a separate gated study with licenses and golden designs.

---

### Q4. Our cloud node has no `tuned` and can’t write debugfs. Did the project fail?

**A.** No. Inventory + dry-run are first-class. `claim_gate.sh` exits **3 (SKIP)** with `publishable_claim=NO`. That is success of process, not success of speedup.

---

### Q5. Should we use `hpc-compute` instead?

**A.** Different parent (`latency-performance`), THP forced on, zone reclaim, busy poll. That can help some MPI/HPC codes and hurt others. It is **not** AMD’s named EDA profile. Diff the mirrored configs before substituting.

---

### Q6. SMT off feels wasteful — why does AMD say disable it for EDA?

**A.** Many EDA executables are lightly threaded per process; siblings contend for core resources and hurt single-thread latency. Throughput of *jobs* often rises by running more *processes* across more physical cores with SMT off. Validate on your mix; don’t cargo-cult.

---

### Q7. NPS=2 vs NPS=1 vs NPS=4?

**A.** AMD’s EDA note: NPS=2 generally; NPS=1 for mixed batch consistency; non-X 9004 often prefers NPS=2 over NPS=4 in their testing. Wrong NPS can dwarf TuneD. See `docs/BIOS_CHECKLIST.md`.

---

### Q8. Can I set `10000` via `sysctl -w` on RHEL 9?

**A.** Maybe not — the knob may live in debugfs. Use TuneD’s scheduler plugin or write `/sys/kernel/debug/sched/migration_cost_ns` as root with debugfs mounted. `scripts/dump_sched_knobs.sh` shows which path exists.

---

### Q9. Is 3% CLAIM_GATE threshold arbitrary?

**A.** Yes, explicitly. It is a **publishability floor** against noise, declared in `configs/claim_gate.yaml`. Changing it is allowed only with a written rationale in the results stamp.

---

### Q10. What if low migration cost *slows* our farm?

**A.** Then CLAIM_GATE FAIL is the correct outcome. Some workloads are locality-bound; sticky is right. Keep `throughput-performance` or craft an overlay. The profile is a default recommendation, not a law.

---

### Q11. Does `epyc-eda` require AMD hardware to activate?

**A.** The `[scheduler.amd]` instance matches AMD `cpuinfo`. On Intel hosts the override may not apply even if the profile name is selected. Always `verify_profile.sh` and dump the knob.

---

### Q12. How do I answer “just buy more cores”?

**A.** Agree that capacity planning dominates. This work is about **not leaving bought cores idle** due to scheduler policy, and aligning BIOS/SKU with tool physics. It is complementary to buying cores, not a substitute.
