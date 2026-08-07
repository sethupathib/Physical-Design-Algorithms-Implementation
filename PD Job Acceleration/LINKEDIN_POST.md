# LinkedIn post draft

## Short version

Most Physical Design turnaround time is not "the algorithm is slow."
It is **"the filesystem is in the way."**

PD tools (place → CTS → route → STA) hammer disk with LEF/DEF/libs/DBs,
checkpoints, and logs — especially over NFS.

**Pattern that works in practice:**

1. `rsync` the job tree into a **tmpfs** workspace (`/dev/shm/...`)
2. Run Innovus / ICC2 / FC / STA **in RAM**
3. Periodically `rsync` checkpoints back to durable NFS
4. Final sync + cleanup on EXIT/TERM so kills still flush home

Same licenses. Same Tcl. Faster wall clock.

I open-sourced a working demo (no EDA license needed) + orchestrator scripts:
`PD Job Acceleration/` in this repo — `./scripts/run_pd_job.sh --demo`

---

## Longer technical version

**Problem**
On a typical farm, your "hot" working directory lives on NFS.
Every tiny random read (liberty, DB pages) and every save pays network RTT.
CPU cores wait. Licenses burn. Schedulers look "busy" while I/O stalls.

**Approach — tmpfs as the hot tier, rsync as the durability bus**

```
NFS (cold, durable)  --rsync-->  tmpfs (hot)  --run tool-->
                     <--rsync--  checkpoints / final outputs
```

**Why rsync (not cp)?**
- Incremental checkpoints (only deltas after the first sync)
- `--partial` survives flaky NFS mid-transfer
- Exclude regenerable junk (`*.tmp`, caches) so you do not ship trash home
- Easy to put on a timer while the tool runs

**Safety rules I always keep**
- tmpfs is volatile — never the source of truth
- Trap EXIT/INT/TERM → always finalize
- Size RAM for peak working set + headroom, not just inputs
- Namespace by user/job under `/dev/shm/pdjobs/$USER/$JOB`

**Try the demo**
```bash
cd "PD Job Acceleration"
./scripts/run_pd_job.sh --demo
./scripts/bench_io.sh 256    # disk vs tmpfs microbench on your host
```

If you run PNR / STA farms: happy to compare notes on what you exclude from sync and how you size tmpfs per block.
