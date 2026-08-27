# AutoFDO / PGO for Fusion Compiler & signoff runtime

**Theme:** CPU · Auto Feedback-Directed Optimization · *up to ~10% kernel latency improvement* (published).

| Artifact | Path |
|---|---|
| PD-shaped proxy microbench | [`src/signoff_proxy.cpp`](./src/signoff_proxy.cpp) |
| Mechanism (skewed switch) | [`src/dispatch_hot.cpp`](./src/dispatch_hot.cpp) |
| Compare harness | [`examples/compare_all.sh`](./examples/compare_all.sh) |
| Farm kernel cookbook | [`farm/KERNEL_AUTOFDO.md`](./farm/KERNEL_AUTOFDO.md) |
| Farm FC A/B template | [`farm/FC_AB_MEASURE.md`](./farm/FC_AB_MEASURE.md) |
| Measured SUMMARY | [`results/SUMMARY.txt`](./results/SUMMARY.txt) |
| White paper | [`WHITEPAPER.md`](./WHITEPAPER.md) · PDF under `docs/` |
| Defend Q&A | [`DEFEND_QA.md`](./DEFEND_QA.md) |

---

## The one-sentence claim

**You cannot AutoFDO Synopsys Fusion Compiler without the vendor** — but you *can* (1) AutoFDO the **farm Linux kernel** under FC/signoff (published ~10% kernel latency), and (2) PGO/AutoFDO **your own** CAD helpers and engines, and you must **measure** both.

---

## Quick start (on your machine)

```bash
cd autofdo-fc-runtime

# deps: g++, optionally clang++-18, llvm-profdata, perf
sudo apt-get install -y g++                          # required
# optional sample-AutoFDO / Clang IRPGO:
# sudo apt-get install -y clang-18 llvm-18 libclang-rt-18-dev linux-tools-generic

make baseline pgo
./examples/compare_all.sh
cat results/SUMMARY.txt results/CLAIM_GATE.txt

# mechanism demo (skewed switch — shows FDO can change codegen)
make mechanism
./examples/compare_mechanism.sh
```

Rebuild docs:

```bash
pip install matplotlib pillow markdown weasyprint
make all-docs
```

---

## Headline numbers (this host)

### A) Literature — kernel AutoFDO (cite this for the “10%”)

| Source | Metric | AutoFDO improvement |
|---|---|---:|
| Google/Meta kernel AutoFDO (Neper `tcp_rr`) | Latency | **~10.6%** |
| Same line of work | Warehouse-scale services | **up to ~5%** |

These are **kernel** numbers on bare-metal-ish farms with LBR — **not** “FC got 10% faster” and **not** measured in this cloud VM.

### B) This repo — user-space GCC PGO on `signoff_proxy`

See checked-in `results/SUMMARY.txt`. On the cloud agent host used to author this folder, PGO **changed codegen** (`size` text grew) but **wall time was ~neutral / slight regression** → `CLAIM_GATE=yes_proxy_measured_neutral`.

That is intentional honesty: FDO is not free magic. Re-run on your laptop/farm CPU; cite **your** SUMMARY.

---

## How this maps to reducing FC / signoff wall time

| Lever | Who owns it | What you do |
|---|---|---|
| **Kernel AutoFDO** | IT / OS / methodology | Pilot AutoFDO kernel on a rack; A/B same FC deck ([`farm/`](./farm/)) |
| **User-space PGO/AutoFDO** | CAD / tools | PGO your log tools, in-house engines, wrappers (this repo’s laptop path) |
| **Vendor FC/ICC2/PrimeTime** | Synopsys | Ask AE for profile-optimized builds; you cannot rebuild closed binaries |

```
FC / signoff job wall time
├── user-mode tool binary (vendor)     ← vendor PGO / wait for AE
├── your scripts & helpers             ← YOU can PGO/AutoFDO (this repo)
└── Linux kernel (syscalls, sched, NFS, license)  ← KERNEL AutoFDO (~10% lat.)
```

---

## Dimension table (methodology)

| Dimension | Kernel AutoFDO (farm) | Ad-hoc “just buy more CPUs” |
|---|---|---|
| Primary focus | Same silicon, better layout of *hot kernel paths* | More spend |
| Typical cite | ~10% kernel latency (Neper); ~5% services | Cost spreadsheet |
| Who can drive? | Methodology + IT with a pilot rack | Finance |
| Risk | Bad profile → no win / rare regress | Always works, always expensive |
| Audit | A/B same deck, watermarked kernels | Invoice |

| Dimension | PGO of *your* tool | Ad-hoc `-O3` and hope |
|---|---|---|
| LOC / process | Train → merge → rebuild | One flag |
| When it wins | Branchy / I-cache bound helpers | Already peak |
| Measure | `compare_all.sh` CLAIM_GATE | Vibes |

---

## Layout

```
autofdo-fc-runtime/
├── README.md
├── WHITEPAPER.md
├── DEFEND_QA.md
├── Makefile
├── src/signoff_proxy.cpp      # PD-shaped proxy
├── src/dispatch_hot.cpp       # mechanism microbench
├── examples/compare_*.sh
├── farm/KERNEL_AUTOFDO.md     # 10% literature path
├── farm/FC_AB_MEASURE.md      # A/B FC jobs on pilot hosts
├── results/                   # SUMMARY + CLAIM_GATE
├── docs/  demo/
```

---

## What this does *not* claim

- That Synopsys FC was rebuilt with AutoFDO in this repo.  
- That every FC job gets 10% wall-time reduction.  
- That user-space PGO always wins on every CPU (this host: neutral).

It **does** claim: the right levers for “reduce FC/signoff runtime via AutoFDO” are **kernel AutoFDO on the farm** + **PGO of owned code** + **vendor engagement** — with a reproducible measurement harness.
