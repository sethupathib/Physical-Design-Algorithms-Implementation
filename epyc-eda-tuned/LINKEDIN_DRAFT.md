# LINKEDIN_DRAFT — epyc-eda (gated)

**Do not post performance numbers unless `scripts/claim_gate.sh` → PASS.**  
If SKIP/FAIL, use the inventory-only variant below.

---

## Variant A — mechanism / engineering rigor (safe without PASS)

**Title lean:** What `tuned-adm profile epyc-eda` actually changes

Most “EDA server tuning” posts list 15 sysctls and a vibe.

AMD’s shipped answer on RHEL 8.10+ is narrower than that.

`epyc-eda` = `throughput-performance` + one AMD scheduler override:

`sched_migration_cost_ns`: 5,000,000 → 10,000

That knob is how long CFS treats a task as cache-hot before it will migrate it. Sticky helps some servers. Sticky also leaves cores idle when work is bursty and uneven — a common EDA farm shape.

We mirrored the AlmaLinux `tuned` profile verbatim, wrote apply/verify/A-B scripts, and put a CLAIM_GATE in front of any speedup sentence.

OS tuning still sits under BIOS (SMT off, NPS, determinism) and SKU choice (F vs X). TuneD is necessary hygiene, not a P&R miracle.

Repo: \<link to epyc-eda-tuned\>

#EDA #EPYC #Linux #PhysicalDesign #PerformanceEngineering

---

## Variant B — only after CLAIM_GATE PASS

Same as A, plus one quantitative sentence:

> On \<hostname / CPU\>, fanout_bench spread-mode median makespan at 10 µs migration cost was X% lower than at 5 ms (N=7). Method and raw logs in-repo.

Attach: host model, nproc, ratio, link to `results/claim_gate_<stamp>/`.

---

## Lines we will not post

- “epyc-eda makes Innovus 20% faster”
- “AMD says so, so we’re done measuring”
- Any number from a SKIP host
