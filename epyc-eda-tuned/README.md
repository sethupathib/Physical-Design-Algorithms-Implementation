# epyc-eda-tuned

**Rigorous OS-tuning lab for AMD’s `epyc-eda` TuneD profile** — commands, mirrored profile sources, BIOS checklist, measurement harness, and a hard CLAIM_GATE.

> This directory is self-contained and intended to be extractable as its own Git repository (see [`STANDALONE_REPO.md`](STANDALONE_REPO.md)).

## What this is

`tuned-adm profile epyc-eda` is **not** a mysterious EDA accelerator. It is a thin TuneD overlay shipped in RHEL/Alma/Rocky **8.10+** (`tuned >= 2.22.1`, RHEL-27528) that:

1. **`include=throughput-performance`** (CPU governor performance, VM dirty ratios, readahead, …)
2. Overrides **one** AMD scheduler knob:

| Knob | `throughput-performance` on AMD | `epyc-eda` |
|------|----------------------------------|------------|
| `sched_migration_cost_ns` | `5000000` (5 ms) | `10000` (10 µs) |

AMD’s documented rationale: the 5 ms “cache-hot” stickiness helps many server workloads but **hurts EDA-like fan-out**, where idle cores + delayed migration dominate.

This repo treats that as a **falsifiable claim**, not a slogan.

## Non-claims (read before posting)

- Does **not** make Innovus / ICC2 / PrimeTime / Spectre faster by itself.
- Does **not** replace BIOS tuning (SMT, NPS, determinism).
- Does **not** imply every EDA job wants aggressive migration.
- A CLAIM_GATE **SKIP** on a locked-down cloud VM is not a PASS.

## Quick start

```bash
cd epyc-eda-tuned
make bin
make dry-inventory          # safe on any Linux host
./scripts/apply_epyc_eda.sh show

# On a RHEL-family box with tuned + root:
sudo ./scripts/apply_epyc_eda.sh apply
./scripts/verify_profile.sh
sudo ./scripts/claim_gate.sh
```

## Layout

```
epyc-eda-tuned/
├── README.md                 # this file
├── WHITEPAPER.md              # full technical write-up
├── DEFEND_QA.md              # adversarial Q&A
├── CLAIM_GATE.md             # publishability rules
├── LINKEDIN_DRAFT.md         # post draft (gated)
├── STANDALONE_REPO.md        # how to split into its own GitHub repo
├── Makefile
├── configs/claim_gate.yaml
├── profiles/                 # verbatim mirrors from AlmaLinux tuned RPM
│   ├── PROVENANCE.md
│   ├── epyc-eda/tuned.conf
│   ├── throughput-performance/tuned.conf
│   └── hpc-compute/tuned.conf
├── docs/
│   ├── COMMAND_RUNBOOK.md
│   ├── BIOS_CHECKLIST.md
│   ├── SCHED_MIGRATION_COST.md
│   └── WORKLOAD_SKU_MAP.md
├── scripts/                  # apply / verify / compare / claim_gate
├── src/fanout_bench.c        # fixed-work A/B microbench
└── results/                  # local run artifacts (gitignored contents)
```

## Measurement idea (CLAIM_GATE)

`fanout_bench --mode spread`:

1. Pin all workers onto a **small** CPU set (transient imbalance).
2. Do a little warm work.
3. **Unpin**, then finish a **fixed** remaining work budget.
4. Report makespan median over outer repeats.

A/B: `sched_migration_cost_ns=5000000` vs `10000`.  
**PASS** only if low-cost median makespan is **≥3% faster** (`ratio_low/high ≤ 0.97`).

Fixed work (not wall-clock-gated spin) so preemption/idle shows up as longer makespan.

## Host notes

This Cloud Agent VM is typically **Ubuntu without TuneD** and **cannot write** scheduler knobs → `claim_gate` exits **SKIP**. That is expected and recorded honestly in `results/`.

## References

- AMD EPYC 9004 HPC Tuning Guide §9.4 *EDA Configuration* (documents `epyc-eda` and `sched_migration_cost_ns=10000`)
- AlmaLinux package `tuned-2.22.1-5.el8_10` (mirrored under `profiles/`)
- Red Hat TuneD docs: scheduler plugin abstraction for `sched_migration_cost_ns` (`/proc` vs debugfs)

## License

Same as the parent repository unless extracted — then choose explicitly in the new repo.
