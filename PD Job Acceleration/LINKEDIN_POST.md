# LinkedIn post draft

## Short version

Most Physical Design turnaround time is not "the algorithm is slow."
It is **"the filesystem is in the way."**

But the fix is **not** "put everything in RAM."

PD logs are often **20GB+**. Those stay on **local SSD**.
What belongs in **tmpfs** is the small, chatty scratch (`tmp` / `TMPDIR`).
Design DBs stay on disk/NFS unless you have measured that the whole tree fits.

**Pattern:**

1. Job dir on disk (DB + fat logs)
2. Symlink only `tmp/` into `/dev/shm`
3. Export `TMPDIR` into that scratch
4. Run Innovus / ICC2 / FC as usual
5. Teardown: materialize scratch home, free RAM

Same licenses. Same Tcl. Less I/O wait — without OOMing the node.

Working scripts + demos: `PD Job Acceleration/`  
`./scripts/ram_scratch.sh --demo`

---

## Longer technical version

**Problem**
Farms put hot working dirs on NFS. Tiny random I/O and tempfile spam pay RTT.
CPU and licenses wait.

**Wrong fix**
Staging a 20GB log into tmpfs. That is just a creative way to OOM.

**Right fix (limited RAM)**
```
disk: DB + logs          RAM: tmp + TMPDIR only
         ▲                      |
         └──── flush on end ────┘
```

**When you have spare RAM**
You can stage the whole workspace into tmpfs and rsync checkpoints home —
but still point huge logs at local SSD outside that tree.

**Safety**
- tmpfs is volatile
- flush on EXIT/TERM
- namespace `/dev/shm/pdjobs/$USER/$JOB`
- measure before you redirect a path into RAM

```bash
cd "PD Job Acceleration"
./scripts/ram_scratch.sh --demo    # hybrid (practical default)
./scripts/run_pd_job.sh --demo     # full tree (only if it fits)
```
