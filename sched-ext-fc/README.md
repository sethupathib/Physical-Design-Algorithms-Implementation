# sched_ext × Fusion Compiler — farm CPU layers

## What this is

A **measurement** exercise about multi-tenant CPU policy on a node that runs:

| Class | FC-farm meaning | Probe here |
|---|---|---|
| **batch** | overnight `fc_shell -f` place/CTS/route workers | N always-runnable CPU threads |
| **interactive-class** | engineer debug / Vortex log forensics / short heavy queries that compete for CPU | 1 always-runnable burn thread |

It is **not** a Synopsys patch, not a claim that Fusion Compiler’s internal thread pool was rewritten, and **not** a demo that loaded a BPF `sched_ext` scheduler on this host.

## Kernel facts (this host)

```text
kernel:              6.12.94+   (upstream sched_ext exists since 6.12)
/sys/kernel/sched_ext: ABSENT   → CONFIG_SCHED_EXT off
/sys/kernel/btf/vmlinux: ABSENT → typed BPF schedulers cannot load
cgroup v2 cpu:       available (measured control plane)
```

So the runnable control plane today is **cgroup v2 `cpu.weight` / nice / `SCHED_BATCH`**.  
`configs/scx_layered_*.json` documents the **same policy shape** for `scx_layered` when a farm kernel has `CONFIG_SCHED_EXT=y`.

If you cannot say that sentence in a LinkedIn post, do not post.

## Quick start

```bash
cd sched-ext-fc
make
./scripts/probe_sched_ext.sh
DURATION=30 ./scripts/compare_all.sh   # needs sudo for cgroups
cat results/SUMMARY.txt results/CLAIM_GATE.txt
```

Default compare: pin both roles to **2 CPUs** (`PIN_CPUS=0-1`), **6** batch workers + **1** interactive burn — deliberate oversubscription.

## Policies

| Name | Mechanism | scx_layered analogue |
|---|---|---|
| `flat` | one cgroup, equal weight | single layer |
| `nice` | interactive `nice -5`, batch `nice +10` | approximate via match on nice |
| `sched_batch` | batch under `SCHED_BATCH` | not a layer weight story |
| `layers` | interactive `cpu.weight=500`, batch `100` (5:1) | `configs/scx_layered_layers.json` |
| `protect` | weight 1000:50 + `cpu.max` on batch | `configs/scx_layered_protect.json` |

## Measured (this host, see `results/`)

Pinned to CPUs `0-1`, 30s, always-runnable interactive burn:

| policy | ix CPU-eq | batch iters/s | vs flat ix | vs flat batch |
|---|---:|---:|---:|---:|
| flat | 0.500 | 750.20 | 1.00× | 1.00× |
| nice | 0.999 | 501.22 | **2.00×** | 0.67× |
| sched_batch | 0.500 | 750.17 | 1.00× | 1.00× |
| **layers** | **1.000** | 500.69 | **2.00×** | 0.67× |
| protect | 1.000 | 500.60 | 2.00× | 0.67× |

`CLAIM_GATE` (share mode): postable iff interactive CPU-eq ≥ 1.4× flat **and** batch ≥ 0.55× flat.  
**PASS: `nice`, `layers`, `protect`.** Prefer citing **`layers`** for the sched_ext narrative; `nice` is the magnitude control.

### How to read this without handwaving

1. **Work-conserving weights:** under `layers` (5:1), the interactive cgroup is entitled to most of the two CPUs, but a single burn thread can only consume **1.0** CPU-eq. Leftover bandwidth goes to batch (~1.0 CPU-eq). That is why batch does not fall to 1/6 — CFS cgroups are work-conserving.
2. **`SCHED_BATCH` was a null result** for this always-runnable mix. Do not invent a win.
3. **Paced short wakeups** (`IX_MODE=interactive`) barely move p50/p99 under CFS — EEVDF already protects that shape. The share experiment is the honest signal for layer policy.
4. **Cannot claim** “we ran `scx_rusty` / `scx_layered` on this box.”

## Farm playbook (Monday morning)

```bash
# 1) Create two cgroups on the farm node (or via your orchestrator)
sudo mkdir -p /sys/fs/cgroup/fc_farm/{interactive,batch}
echo '+cpu' | sudo tee /sys/fs/cgroup/fc_farm/cgroup.subtree_control
echo 500 | sudo tee /sys/fs/cgroup/fc_farm/interactive/cpu.weight
echo 100 | sudo tee /sys/fs/cgroup/fc_farm/batch/cpu.weight

# 2) Launch overnight FC into batch; debug/Vortex into interactive
echo $FC_PID   | sudo tee /sys/fs/cgroup/fc_farm/batch/cgroup.procs
echo $VTX_PID  | sudo tee /sys/fs/cgroup/fc_farm/interactive/cgroup.procs

# 3) When the node kernel has CONFIG_SCHED_EXT=y, load scx_layered
#    with configs/scx_layered_layers.json (match on those cgroup prefixes).
```

Measure **interactive wall** and **batch iters / job runtime** separately. Only cite numbers that pass your own CLAIM_GATE on **that** kernel.

## Non-claims

- Did not modify Fusion Compiler.
- Did not load a BPF scheduler here.
- Did not prove farm NFS / license / memory effects.
- Did not show interactive *latency* wins for sub-millisecond wakeups (CFS already good there).

## Layout

```
sched-ext-fc/
├── src/fc_sched_bench.c
├── scripts/{probe_sched_ext,setup_cgroups,run_pair,run_one_policy,compare_all}.sh
├── configs/scx_layered_{layers,protect}.json
├── results/{SUMMARY,CLAIM_GATE}.txt
├── LINKEDIN_DRAFT.md
└── DEFEND_QA.md
```
