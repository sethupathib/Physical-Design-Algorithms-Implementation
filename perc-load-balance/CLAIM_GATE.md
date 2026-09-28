# CLAIM_GATE

## Allowed after `make smoke` PASS

- “We model LSF slot semantics as 1 slot = 1 core and refuse plans that exceed `max_slots_per_user`.”
- “We treat Calibre license tokens as a hard constraint alongside CPU/mem.”
- “Naive CPU-only sizing can look fine while the full planner BLOCKS or REDUCES.”

## Forbidden without on-farm measurement

- Any PERC/DRC walltime speedup %
- Any claim that default `tokens_per_turbo_thread` matches a named customer’s Siemens contract
- “TSRI recommends this exact turbo/hosts for all PERC”

## Site calibration stamp

When you calibrate, write `results/CALIBRATED.md`:

```text
date:
host:
busers_max_slots:
lmstat_features:
tokens_per_turbo_thread_measured:
notes:
```
