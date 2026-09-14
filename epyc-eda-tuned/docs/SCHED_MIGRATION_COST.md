# SCHED_MIGRATION_COST — deep dive

## Definition

`sched_migration_cost_ns` — duration after a task’s last execution during which CFS treats the task as **cache-hot** for **migration decisions**. Larger ⇒ fewer migrations ⇒ more locality, slower rebalancing onto idle CPUs.

## Values that matter in this lab

| Context | ns | ms/µs |
|---------|----|-------|
| Historical “desktop-ish” defaults (order of) | ~500_000 | 0.5 ms |
| `latency-performance` / many low-latency profiles | 5_000_000 | 5 ms |
| `throughput-performance` **AMD** instance | 5_000_000 | 5 ms |
| **`epyc-eda`** | **10_000** | **10 µs** |

## Where to read/write

```bash
./scripts/dump_sched_knobs.sh
```

Paths (first readable wins in our scripts):

1. `/proc/sys/kernel/sched_migration_cost_ns`
2. `/sys/kernel/debug/sched/migration_cost_ns`  # needs debugfs + often root to write

TuneD scheduler plugin selects the correct backend for the running kernel.

## Interaction with other CFS knobs

From `throughput-performance` (still active under epyc-eda):

- `sched_min_granularity_ns = 10_000_000`
- `sched_wakeup_granularity_ns = 15_000_000`

Migration cost is **orthogonal** but coupled in practice: granularity shapes how long a task runs before preemption; migration cost shapes how eagerly it moves after.

## Mental model for EDA

```text
Job fan-out storm
    │
    ▼
Some CPUs runq long, some CPUs idle
    │
    ├─ high migration_cost → tasks stay "hot" on busy CPUs → idle wasted
    │
    └─ low migration_cost  → balancer moves work sooner → better packing
```

Locality-sensitive tight loops may prefer the left branch. Measure.

## A/B protocol

```bash
sudo ./scripts/compare_profiles.sh
```

Restores the original value via `trap` on EXIT.

## Failure modes

- **Permission denied** writing debugfs under lockdown → use TuneD or accept SKIP.
- **Profile applied but knob unchanged on Intel** → AMD regex instance did not match.
- **Thinking sysctl worked on RHEL 9 when it didn’t** → always read back with `dump_sched_knobs.sh`.
