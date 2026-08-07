# Accelerate Physical Design Jobs with tmpfs + rsync

**White paper (detailed):** [`WHITEPAPER.md`](./WHITEPAPER.md) ·
[`docs/pd_tmpfs_rsync_whitepaper.pdf`](./docs/pd_tmpfs_rsync_whitepaper.pdf)

Physical Design tools are often **I/O-bound**, not just CPU-bound —
especially over NFS (tiny random reads on libs/DB pages, chatty scratch).
This folder has **two modes**. Pick by RAM budget.

| Mode | When | What goes in RAM |
|---|---|---|
| **A. Full workspace** (`run_pd_job.sh`) | Design + scratch **fits** in free RAM with headroom | Job tree **except logs** (logs stay on disk by default) |
| **B. Hybrid scratch** (`ram_scratch.sh`) | RAM is limited (usual case) | Only small `tmp` / `TMPDIR` |

**Fat PD logs (often 10–50GB+) do not go in RAM** in either recommended setup.
Keep them on **local SSD/NVMe** (best) or NFS. Putting a 20GB log in `tmpfs`
is how you OOM the node.

```
Mode B (limited RAM) — the practical default:

  disk / NFS                         RAM (/dev/shm scratch)
  +----------------------+           +----------------------+
  | design DB, libs     |           | tmp/  (symlink)      |
  | scripts              |           | TMPDIR               |
  | logs/  (STAY HERE)   |           |                      |
  | final outputs        |  flush    | small regenerable    |
  +----------------------+ <-------- +----------------------+
```

## Mode B — limited RAM (recommended default)

Keep the job on disk. Redirect only small scratch into `/dev/shm`.

```bash
cd "PD Job Acceleration"

export PD_DURABLE_ROOT=/proj/chip/blockA/pnr_run42
export PD_RAM_PATHS="tmp"    # default — NOT logs
export PD_TOOL_CMD='innovus -files run_route.tcl -log logs/route.log'
./scripts/ram_scratch.sh run
```

What happens:

1. Creates `/dev/shm/pdjobs/$USER/<job>.scratch/`
2. Makes `tmp/` a **symlink into RAM** (under the durable job dir)
3. Exports `TMPDIR` / `TMP` / `TEMP` into that scratch
4. Runs the tool with cwd = durable root  
   - `logs/route.log` → disk  
   - `tmp/...` and tempfile APIs → RAM  
   - design DB saves → disk (wherever Tcl points)
5. On teardown: materialize `tmp/` back to disk, delete scratch, free RAM

Demo (no EDA license):

```bash
./scripts/ram_scratch.sh --demo
```

| Tier | Put this there |
|---|---|
| RAM (`tmpfs`) | Small regenerable scratch, `TMPDIR` — **only if measured to fit** |
| Local SSD | Huge logs, fat temp that exceeds RAM |
| NFS | Inputs, final DBs, shared deliverables |

## Mode A — full workspace in tmpfs (only if it fits)

Stage the durable tree into RAM, run there, `rsync` checkpoints home.
**Logs still stay on disk by default** (`PD_KEEP_LOGS_ON_DISK=1`): after staging,
`logs/` in the workspace is a symlink to the durable `logs/` directory and is
excluded from rsync — so a 20GB tool log never lands in tmpfs.

```bash
export PD_DURABLE_ROOT=/proj/chip/blockA/pnr_run42
export PD_JOB_NAME=blockA_route_iter3
export PD_TMPFS_SIZE=64G
export PD_TOOL_CMD='innovus -files run_route.tcl -log logs/route.log'
./scripts/run_pd_job.sh
```

Flow:

1. Prepare workspace under `/dev/shm/pdjobs/<job>`
2. `rsync` durable → tmpfs (**excluding `logs/`**)
3. Rewire `logs/` → durable disk
4. Run tool with cwd = tmpfs (relative `logs/...` hits disk)
5. Optional periodic `rsync` checkpoints → durable
6. Final `rsync`, write `STATUS`, cleanup

Demo:

```bash
./scripts/run_pd_job.sh --demo
```

**Warning:** Mode A still needs the design DB + scratch to fit in RAM.
If they do not, use Mode B. Set `PD_KEEP_LOGS_ON_DISK=0` only if you have
measured that logs are small enough for tmpfs.

## Scripts

| Script | Role |
|---|---|
| `scripts/ram_scratch.sh` | Mode B: small `tmp`/`TMPDIR` in RAM; logs stay on disk |
| `scripts/run_pd_job.sh` | Mode A: full tree in tmpfs; **logs stay on disk by default** |
| `scripts/stage_to_tmpfs.sh` | Durable → tmpfs staging |
| `scripts/checkpoint_sync.sh` | Hot → durable incremental sync |
| `scripts/finalize_job.sh` | Final sync + cleanup |
| `scripts/pd_job_env.sh` | Shared helpers (`pd_durable_sync`, perf discovery) |
| `scripts/pd_perf_profile.sh` | **perf** (+ GNU time) I/O-vs-CPU profile + Mode A/B advice |
| `scripts/bench_io.sh` | Disk vs tmpfs microbench |
| `scripts/demo_*.sh` | License-free demos |

## perf — measure before you move data

`perf` does not accelerate the job; it tells you **whether** tmpfs will help.

```bash
# Standalone profile of any command
./scripts/pd_perf_profile.sh --out /tmp/pd_perf -- \
  bash -c 'your_pd_tool ...'

# Or wrap Mode A / Mode B
PD_PERF=1 PD_DURABLE_ROOT=... PD_TOOL_CMD='...' ./scripts/ram_scratch.sh run
```

Output: `SUMMARY.txt` with classification (`I/O-bound` / `CPU-bound` / `Mixed`) and a
Mode A/B recommendation. HW counters may be unavailable in VMs; soft events +
GNU `time -v` still classify well.

## `sync` — durability after rsync (not the same as rsync)

**rsync** copies bytes into the destination filesystem. The shell **`sync`**
command flushes kernel writeback so a crash cannot silently lose a “successful”
checkpoint/finalize.

| Knob | Default | Meaning |
|---|---|---|
| `PD_SYNC_MODE` | `fs` | `off` / `file` / `fs` / `global` |
| `PD_SYNC_AFTER_FINALIZE` | `1` | sync after final rsync / Mode B flush |
| `PD_SYNC_AFTER_CHECKPOINT` | `0` | sync every checkpoint (often costly on NFS) |

Prefer `fs` (filesystem containing the durable root) over `global` on busy farm
nodes. Enable checkpoint sync only when the redo window matters more than NFS load.

```bash
# Smoke demo: perf profile + Mode B + durable sync
./examples/demo_perf_and_sync.sh
```

## Safety rules

1. tmpfs is volatile — never the source of truth; always flush/checkpoint.
2. **Do not put 20GB+ logs in RAM.** Prefer local SSD.
3. Size RAM for peak scratch (or peak full tree in Mode A), with headroom.
4. Exclude regenerable junk from sync when using Mode A.
5. Trap `EXIT`/`TERM` so killed jobs still flush.
6. On shared farms: `/dev/shm/pdjobs/$USER/$JOB` and enforce quotas.
7. After finalize, **`sync`** (or `PD_SYNC_MODE=fs`) so durable media has the data.
8. Profile with **`perf`** before claiming an I/O win — CPU-bound phases will not move.

## Real workload example (RC Extraction)

There is **no metal-fill project on `main`**. The closest real PD binary in this
repo family is **RC Extraction** (from `cursor/rc-extraction-signoff-6f4a`).

```bash
# from repo root — builds RC Extraction if needed, then runs Mode B
./PD\ Job\ Acceleration/examples/run_rcx_accelerated.sh
./PD\ Job\ Acceleration/examples/run_rcx_accelerated.sh --mode-a
```

That job extracts `simple_net` / `coupled_nets` / `via_stack` / a generated
`big_bus.lay`, writes SPEF under `outputs/`, logs under `logs/` (disk), and
uses `tmp/` (+ `TMPDIR`) for scratch.

Compare **with vs without** acceleration (same job, wall times + SPEF checksums):

```bash
./PD\ Job\ Acceleration/examples/compare_accel.sh
cat "PD Job Acceleration/examples/compare_results/SUMMARY.txt"
```

### Metal fill (`gpu_metal_fill`)

Same exercise on the BEOL metal-fill engine
(`cursor/beol-metal-fill-partitioning-caf3/gpu_metal_fill`):

```bash
./PD\ Job\ Acceleration/examples/compare_metal_fill.sh
cat "PD Job Acceleration/examples/compare_metal_fill_results/SUMMARY.txt"
```

### I/O-bound PD job (liberty vault + checkpoints)

Synthetic but PD-shaped: tens of thousands of tiny liberty-like files with
random lookups, fat DB checkpoints, report spam. Shows filesystem wins clearly.

```bash
./PD\ Job\ Acceleration/examples/compare_pd_io.sh
cat "PD Job Acceleration/examples/compare_pd_io_results/SUMMARY.txt"
```

### Monumental farm I/O suite (NFS RTT vs tmpfs)

Multi-phase PD farm workload (liberty vault → random lookups → SPEF shards →
ECO checkpoints → report spam). Baseline adds emulated **NFS per-op RTT**;
Mode B/A run the same work on tmpfs with `nfs-us=0`.

```bash
./PD\ Job\ Acceleration/examples/compare_pd_farm_io.sh
cat "PD Job Acceleration/examples/compare_pd_farm_io_results/SUMMARY.txt"
```

Example on this host (`NFS_US=400µs`): baseline **~115s** → Mode A **~2.3s (~50×)**.

## LinkedIn one-liner

> Most PD turnaround time is not "the algorithm is slow" — it is "the filesystem is in the way."
> Keep fat logs on SSD. Put only small scratch in tmpfs. rsync durability back to NFS.

See [`LINKEDIN_POST.md`](./LINKEDIN_POST.md) for a longer draft.
