# NUMA × Fusion Compiler — before/after farm memory policy

**White paper:** [`WHITEPAPER.md`](./WHITEPAPER.md) · [`docs/numa_fc_whitepaper.pdf`](./docs/numa_fc_whitepaper.pdf)

> Pin FC to one NUMA node’s cores **and** bind memory to that same node.

This project is the **memory-locality** twin of [`PD Job Acceleration`](../PD%20Job%20Acceleration/) (tmpfs + rsync).  
That one attacks **filesystem** placement. This one attacks **DRAM** placement on multi-socket servers.

| Layer | Pattern | Before → After |
|---|---|---|
| Disk / NFS | tmpfs + rsync | chatty I/O on NFS → hot scratch in RAM |
| **DRAM / sockets** | **`numactl` bind** | **remote fills across UPI → local DRAM** |

## The experiment (run this)

```bash
cd NUMA-EDA-Bench
./scripts/numa_report.sh
make -j
./examples/compare_numa.sh
cat examples/compare_results/SUMMARY.txt
```

What you get:

| Artifact | Meaning |
|---|---|
| `examples/compare_results/SUMMARY.txt` | BEFORE vs AFTER table + speedup ratios |
| `*.json` | machine-readable triad / chase / graph / wall_proxy |
| `*.log` | full human bench output |

### Two compare modes (auto-selected)

| Host | Mode | BEFORE | AFTER |
|---|---|---|---|
| **≥2 NUMA nodes** + `numactl` | `hardware` | `cpunodebind=0 --membind=1` (remote) | `cpunodebind=0 --membind=0` (local) |
| **1 NUMA node** (this cloud VM) | `emulated` | `--emulate-remote` DRAM tax | local / `membind=0` |

Emulated mode is the same idea as `NFS_US` in the PD farm I/O suite: a **labeled model** of the farm penalty so you can exercise the harness when the hardware topology is single-node. On a real 2S/4S box you get hardware numbers.

Knobs:

```bash
BYTES=1G THREADS=8 ./examples/compare_numa.sh
REMOTE_BW_MULT=0.50 REMOTE_LAT_MULT=2.0 ./examples/compare_numa.sh   # emulated tax
FORCE_EMULATE=1 ./examples/compare_numa.sh                          # force emulate even on 2S
```

## Production wrap (real FC / Innovus)

```bash
./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl
# ≡ numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

Safety: refuses `membind` if node `MemFree` < 8 GiB unless `FORCE=1`.  
Only hard-bind when peak RSS fits that node’s free RAM; otherwise `--preferred=0`.

## What the microbench measures

`numa_mem_bench` is an **FC-class memory proxy** (not a licensed tool):

1. **STREAM triad** — bandwidth (GiB/s)  
2. **Pointer chase** — latency-sensitive hops (ns)  
3. **Graph walk** — CSR-like random edges (timing/netlist proxy)  
4. **wall_proxy** — composite (lower = better)

```bash
./build/numa_mem_bench --bytes 512M --threads 4
./build/numa_mem_bench --json --emulate-remote
numactl --cpunodebind=0 --membind=0 ./build/numa_mem_bench --bytes 1g --threads 8
```

Vendored CLI (no root install needed): `tools/numactl-root/usr/bin/numactl`.

## LinkedIn demo asset

Animated story (unbound remote → policy → local):

| File | Use |
|---|---|
| `demo/numa_fc_demo.gif` | post media |
| `demo/numa_fc_demo_still.png` | thumbnail |
| `CAPTION.md` | post copy |

```bash
python3 demo/gen_numa_linkedin_gif.py
```

## Mental model

```
  Socket 0                         Socket 1
 ┌──────────────────┐             ┌──────────────────┐
 │ cores + DRAM 0   │◄── UPI/IF ►│ cores + DRAM 1   │
 └────────▲─────────┘             └────────▲─────────┘
          │                                 │
          │  local = fast                   │  remote = tax
          │                                 │
   AFTER: fc_shell + pages here      BEFORE: pages here, threads there
```

```bash
numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

## Layout

| Path | Role |
|---|---|
| `WHITEPAPER.md` | full design / ops white paper |
| `docs/numa_fc_whitepaper.pdf` | PDF render |
| `examples/compare_numa.sh` | BEFORE/AFTER harness |
| `examples/compare_results/` | measured SUMMARY + JSON |
| `src/numa_mem_bench.cpp` | STREAM + chase + graph |
| `scripts/run_eda_numactl.sh` | production wrapper |
| `scripts/numa_report.sh` | topology |
| `demo/` | LinkedIn GIF |
| `tools/numactl-root/` | vendored `numactl` |

## Safety rules

1. Hard `membind` to a node with insufficient free RAM → OOM / reclaim storms.  
2. One heavy EDA job per node when possible.  
3. Measure with `compare_numa.sh` / `numastat -p` before claiming a win.  
4. Don’t cargo-cult on 1-node machines — topology first.  
5. Emulated ratios are a **model**; quote hardware numbers from a 2S farm for design reviews.
