# perc-load-balance

**Accelerate Calibre DRC / PERC on LSF-class farms without lying to yourself about capacity.**

> Clone-ready lab. Baseline: *EDA tool execution in TSRI EDA Cloud 2.0 User Guide r1.3* (IBM Spectrum LSF semantics).

## The thesis

Most engineers size distributed DRC/PERC by **CPU and memory requests** only.

The jobs that never start — or start then thrash — usually die on two silent killers:

1. **License tokens** (master + MT/remote consumption)  
2. **Per-slot resource semantics** (on TSRI-like LSF: **1 job slot = 1 CPU core**; `hosts × turbo` must fit `max_slots_per_user`; `-R select[mem>N]` **selects hosts but does not reserve RAM**)

This repo turns that thesis into a **planner + dispatch simulator + launch bundle emitter** you can run offline, then take to a real farm (TSRI EDA Cloud, design-house sandbox, etc.).

## Quick start

```bash
cd perc-load-balance
pip install -r requirements.txt
make smoke
```

```bash
# Plan a PERC-shaped job under farm caps
python3 scripts/plan_calibre_job.py --job configs/job_perc_example.yaml

# See naive CPU-only view vs full slot+license view
python3 scripts/simulate_dispatch.py --job configs/job_overask_example.yaml

# Emit reviewable run.sh + NOTES.md (does not bsub)
python3 scripts/emit_launch_bundle.py --job configs/job_drc_example.yaml
```

## Layout

```
perc-load-balance/
├── README.md
├── WHITEPAPER.md
├── DEFEND_QA.md
├── CLAIM_GATE.md
├── STANDALONE_REPO.md
├── configs/
│   ├── farm.yaml                 # slots, queues, license knobs
│   ├── job_drc_example.yaml      # 3×4 = 12 cores (guide-shaped)
│   ├── job_perc_example.yaml
│   └── job_overask_example.yaml  # intentionally infeasible / reduced
├── scripts/
│   ├── plan_calibre_job.py
│   ├── simulate_dispatch.py
│   ├── emit_launch_bundle.py
│   ├── parse_bacct_fixture.py
│   └── smoke_test.sh
├── fixtures/bacct_sample.yaml
└── docs/
    ├── TSRI_BASELINE.md
    └── COMMAND_RUNBOOK.md
```

## What “working” means here

| Claim | Proof |
|-------|-------|
| Slot math matches TSRI semantics | Planner refuses `master + slaves×turbo > max_slots` |
| License ceiling is first-class | Over-ask jobs BLOCK or REDUCE; never silent FEASIBLE at full want |
| Naive vs full view | `simulate_dispatch.py` prints both |
| Launch artifacts | `emit_launch_bundle.py` writes `run.sh` + checklist |
| Post-run efficiency | `parse_bacct_fixture.py` scores HOG/efficiency analogs |

**Non-claims:** this does not ship Siemens Calibre, does not call real `bsub`/`lmstat`, does not promise PERC walltime speedup. It prevents **impossible** launches and documents **feasible** ones.

## Farm calibration (do this on day 1 in a sandbox)

1. `busers` → confirm max slots / in-use  
2. `lmstat -a` (or site equivalent) while a small Calibre MT job runs → fill `configs/farm.yaml` `licenses.*`  
3. Re-plan with your real `want_*`  
4. Submit only the emitted plan  

## Extract as its own GitHub repo

See `STANDALONE_REPO.md`.
