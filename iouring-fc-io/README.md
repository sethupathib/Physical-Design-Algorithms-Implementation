# io_uring for Fusion Compiler workflows

**Detailed write-up:** [`WHITEPAPER.md`](./WHITEPAPER.md) · PDF [`docs/iouring_fc_io_whitepaper.pdf`](./docs/iouring_fc_io_whitepaper.pdf) · [`DEFEND_QA.md`](./DEFEND_QA.md)

## Honest scope

Synopsys **Fusion Compiler is a closed binary**. You cannot recompile it against `io_uring`.

What you *can* accelerate with io_uring:

1. **Deck stage-in** — copy LEF/DEF/netlist/libs from NFS (or cold disk) to local NVMe before `fc_shell`
2. **Multi-file hydrate** — thousands of small views (liberty/LEF fragments) into page cache / local tree
3. **Log / report ingest** — post-FC multi-GB log reads for Vortex / grep / QA wrappers
4. **Your own CAD tools** — anything you compile (Vortex-class forensics, custom checkers)

If FC is already CPU-bound in place/CTS/route with warm cache, io_uring will not move wall time.

## Quick start

```bash
cd iouring-fc-io
sudo apt-get install -y liburing-dev build-essential
make
./scripts/gen_dataset.sh          # FC-shaped files
./examples/compare_all.sh
cat results/SUMMARY.txt
```

## Workloads

| Subset | Proxy for |
|---|---|
| `small_files` | many liberty/LEF-ish cell views |
| `large_files` | DEF / netlist / log blobs |
| `mixed` | full deck hydrate |

Backends: **posix** · **iouring** (sync open + uring read) · **iouring_openat** (uring openat+read+close).

## Farm playbook (FC wrapper sketch)

```bash
# 1) Stage deck to local NVMe with an io_uring-aware copier (or this bench's pattern)
# 2) Point FC_WORK_DIR at the local tree
# 3) Run fc_shell as today
# 4) Optionally io_uring-read logs into Vortex
```

Measure **stage-in seconds** and **FC wall** separately. Only cite stage-in wins from this repo’s CLAIM_GATE.

## Layout

```
iouring-fc-io/
├── src/fc_io_bench.c      # liburing vs POSIX
├── scripts/gen_dataset.sh
├── examples/compare_all.sh
├── results/
└── README.md
```

## Measured on this host (see `results/SUMMARY.txt`)

Warm page-cache on cloud overlay storage (not farm NFS→NVMe):

- **large_files**: io_uring ≈ **1.04–1.11×** vs posix (modest win)
- **small_files / mixed**: posix faster here — uring setup dwarfs cached tiny reads

That is a real finding, not a failure of the exploration: **io_uring helps when I/O latency and queue depth matter** (cold NFS, many outstanding ops). Re-run on a farm node with `drop_caches` + NFS-backed libs before citing wins.
