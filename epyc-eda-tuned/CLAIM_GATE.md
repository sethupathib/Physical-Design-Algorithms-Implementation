# CLAIM_GATE

Public performance claims about `epyc-eda` require a **PASS** from `scripts/claim_gate.sh`.

## Claim under test

> On this host, under `fanout_bench` **spread** mode, setting `sched_migration_cost_ns=10000` (epyc-eda) reduces median makespan by **≥ 3%** versus `5000000` (throughput-performance AMD default).

Claim ID: `epyc_eda_lower_migration_cost_reduces_spread_makespan`

## Outcomes

| Result | Meaning | Publish performance number? |
|--------|---------|-------------------------------|
| **PASS** | A/B met threshold | Yes, with host + method attached |
| **FAIL** | A/B opposite or missing | No |
| **INCONCLUSIVE** | within ±2% | No (say inconclusive) |
| **SKIP** | cannot write knob / no path | No (inventory-only OK) |

## Method requirements

1. Fixed-work bench (`src/fanout_bench.c`), not timed busy-wait.
2. Outer repeats ≥ 5 (scripts use 7).
3. Restore original migration cost on exit.
4. Record `results/claim_gate_<stamp>/` including inventory + knobs + bench outputs.
5. Do not average away a FAIL by re-running until PASS.

## Allowed public sentences

**If PASS:**
> Under fanout_bench spread mode on \<host\>, `sched_migration_cost_ns=10000` cut median makespan by X% vs `5000000` (N outer trials).

**If SKIP (this cloud VM):**
> We mirrored the RHEL `epyc-eda` profile and automated inventory/verify/A-B scripts; this host cannot write scheduler knobs, so no speedup claim is made.

**Never:**
> `tuned-adm profile epyc-eda` makes place-and-route 20% faster.

## Thresholds

See `configs/claim_gate.yaml`.
