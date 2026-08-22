# NUMA × Fusion Compiler — LinkedIn demo

Visual demo of the DeepSeek-style farm hack:

> Pin FC to one NUMA node’s cores **and** bind memory to that same node.

Not a tutorial. A **post asset**: animated dual-socket story → remote UPI burn → `numactl` policy → local recovery.

## Asset

| File | Use |
|---|---|
| `demo/numa_fc_demo.gif` | LinkedIn post media (1280×720 loop) |
| `demo/numa_fc_demo_still.png` | thumbnail / carousel still |
| `CAPTION.md` | post copy |

Regenerate:

```bash
python3 demo/gen_numa_linkedin_gif.py
```

## Optional: measure on a real 2S box

This cloud VM is 1-node — you won’t see a local/remote gap here. On a dual-socket farm:

```bash
make -j
./scripts/compare_local_remote.sh
# expect: membind=remote triad ↓  and pointer-chase latency ↑
```

Wrapper for a real job (refuses membind if node MemFree < 8 GiB unless `FORCE=1`):

```bash
./scripts/run_eda_numactl.sh 0 fc_shell -f run.tcl
```
