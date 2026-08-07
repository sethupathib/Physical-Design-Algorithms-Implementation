# Accelerate Physical Design Jobs with tmpfs + rsync

Physical Design tools are often **I/O-bound**, not just CPU-bound.
Placement, CTS, routing, and STA thrash disk with huge LEF/DEF/lib/DB files,
incremental saves, reports, and logs — especially over NFS.

**Idea:** stage the hot working directory into **RAM (`tmpfs`)**, run the tool
there at memory bandwidth, and use **`rsync`** to checkpoint / finalize back to
persistent storage (NFS or local disk).

```
  NFS / disk (cold, durable)          RAM tmpfs (hot, fast)
  +---------------------+   rsync    +---------------------+
  | design inputs       | -------->  | job workspace       |
  | scripts, libs, LEF  |            | Innovus / ICC2 / .. |
  |                     | <--------  | checkpoints, logs   |
  | durable outputs     |   rsync    | reports, DBs        |
  +---------------------+            +---------------------+
```

## Why this helps PD workloads

| Bottleneck | What tmpfs changes |
|---|---|
| NFS latency on tiny random reads (libs, DB pages) | Local RAM latency |
| Frequent checkpoint / save writes | Sequential RAM writes, then batched rsync |
| Log / report spam during long runs | Cheap appends in RAM |
| Multi-iteration ECO loops | Keep the hot tree resident between iterations |

You still need durable storage. tmpfs is **volatile** — reboot = gone.
That is why rsync checkpoints matter.

## Quick start (demo, no EDA license needed)

```bash
cd "PD Job Acceleration"

# 1) Create a fake design tree + simulate a PD job in tmpfs
./scripts/run_pd_job.sh --demo

# 2) Inspect what landed on durable storage
ls -la examples/demo_durable/outputs/
```

The demo mounts (or uses) a tmpfs workspace, stages inputs with rsync,
runs a synthetic I/O-heavy "PD tool", checkpoints mid-run, then finalizes.

## Real-job pattern

```bash
# Configure once
export PD_DURABLE_ROOT=/proj/chip/blockA/pnr_run42
export PD_JOB_NAME=blockA_route_iter3
export PD_TMPFS_SIZE=64G          # size of RAM workspace
export PD_TOOL_CMD='innovus -files run_route.tcl -log route.log'

./scripts/run_pd_job.sh
```

Flow inside `run_pd_job.sh`:

1. **Prepare** tmpfs mount under `/dev/shm/pdjobs/<job>` (or custom path)
2. **Stage in** — `rsync -aH --info=stats2` durable → tmpfs
3. **Run** tool with `cwd` = tmpfs workspace
4. **Checkpoint** (optional timer) — rsync outputs tmpfs → durable
5. **Finalize** — full rsync, write `STATUS`, unmount/cleanup

## Limited RAM: logs/temp only (hybrid)

If you **cannot** fit the whole design DB in RAM, do **not** stage the full tree.
Keep LEF/DEF/libs/DB on NFS/disk; put only **chatty, regenerable, or append-heavy**
paths into a small `/dev/shm` scratch:

```bash
export PD_DURABLE_ROOT=/proj/chip/blockA/pnr_run42
export PD_RAM_PATHS="logs tmp timing_tmp"   # relative dirs only
export PD_TOOL_CMD='innovus -files run_route.tcl -log logs/route.log'
./scripts/ram_scratch.sh run
```

What it does:

1. Creates `/dev/shm/pdjobs/$USER/<job>.scratch/`
2. Replaces `logs/`, `tmp/`, … with **symlinks into RAM**
3. Exports `TMPDIR` (and `TMP`/`TEMP`) into that scratch so libc/tempfile traffic hits RAM
4. On teardown, **materializes** those dirs back onto durable disk and frees RAM

Demo:

```bash
./scripts/ram_scratch.sh --demo
```

**Rule of thumb:** RAM-tier = high IOPS / small files / throwaway. Disk-tier = large DBs and anything expensive to regenerate.

## Scripts

| Script | Role |
|---|---|
| `scripts/pd_job_env.sh` | Shared defaults / path helpers |
| `scripts/stage_to_tmpfs.sh` | Durable → tmpfs staging |
| `scripts/checkpoint_sync.sh` | Hot → durable incremental sync |
| `scripts/finalize_job.sh` | Final sync + cleanup |
| `scripts/run_pd_job.sh` | Orchestrator (stage → run → sync) |
| `scripts/ram_scratch.sh` | Limited-RAM: redirect logs/tmp only |
| `scripts/demo_pd_workload.sh` | Synthetic PD I/O for demos / LinkedIn |
| `scripts/bench_io.sh` | Quick disk vs tmpfs write/read microbench |

## Safety rules (worth posting)

1. **Never** treat tmpfs as source of truth — always checkpoint.
2. Size tmpfs for peak working set (design DB + temps + headroom), not just inputs.
3. Exclude huge regenerable junk from sync (`*.tmp`, tool caches) via `--exclude`.
4. Prefer `--partial --append-verify` (or checksum mode) for long checkpoints over flaky NFS.
5. Trap `EXIT`/`TERM` so a killed job still flushes outputs home.
6. On shared farms, put jobs under `/dev/shm/pdjobs/$USER/$JOB` and enforce quotas.

## LinkedIn angle (one-liner)

> Most PD turnaround time is not "the algorithm is slow" — it is "the filesystem is in the way."
> Stage the hot workspace into tmpfs, run the tool in RAM, rsync durability back to NFS.
> Same licenses. Same Tcl. Faster wall clock.

See [`LINKEDIN_POST.md`](./LINKEDIN_POST.md) for a ready-to-share draft.
