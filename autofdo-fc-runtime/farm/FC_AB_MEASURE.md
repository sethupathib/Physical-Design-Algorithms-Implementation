# Farm A/B measurement — Fusion Compiler / signoff on AutoFDO kernels

Use with [`KERNEL_AUTOFDO.md`](./KERNEL_AUTOFDO.md). This is a **template**, not a Synopsys wrapper.

## Goal

Decide, with evidence, whether an AutoFDO kernel reduces **wall time** for *your* FC/signoff decks.

## Setup

1. Two hosts (or dual-boot) — **same** CPU SKU, memory, NFS mounts, license servers.  
2. Host **B** runs AutoFDO-optimized kernel; host **A** runs baseline distro kernel.  
3. Identical tool versions (`fc_shell -version`, PT, etc.).  
4. Freeze a **deck**: design, SDC, UPF, script list, seed. Hash the deck (`sha256sum` manifest).

## Run protocol

```bash
# On each host, for each deck:
/usr/bin/time -v -o /tmp/fc_time.txt \
  fc_shell -f run.tcl | tee /tmp/fc_log.txt

# Optional PMU / OS view (while job runs, another window):
perf stat -a sleep 60
# record: context switches, cycles, migrations, NFS client stats
```

Repeat **≥3** times per host; discard first cold NFS run if needed; report median wall time.

## Metrics to log

| Metric | Why |
|---|---|
| Wall time | Primary |
| User / sys time | Is kernel slice moving? |
| Voluntary / involuntary ctx switches | Scheduler behavior |
| NFS / license wait | I/O vs CPU |
| `perf` frontend stalls | Matches AutoFDO thesis |

## Gate (farm CLAIM_GATE)

```
CITEABLE=yes_farm_autofdo_kernel
  iff median wall time improves by agreed threshold (e.g. ≥3%)
  AND deck hash matches
  AND tool versions match
  AND no functional/QoR fail in logs
```

If sys time barely moved, AutoFDO kernel may be the wrong lever for that deck — try NUMA / I/O / vendor build next.

## What not to write on LinkedIn

- “We AutoFDO’d Fusion Compiler by 10%” ← false  
- “Kernel AutoFDO → 10% on Neper; our FC deck median −X% on pilot rack” ← true if measured  
