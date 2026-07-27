# PERC Runtime Optimizer (C++)

Educational C++17 project: understand **PERC** (Programmable Electrical Rules Checking) in physical design, and measure algorithmic ways to cut runtime.

See [docs/PERC_OVERVIEW.md](docs/PERC_OVERVIEW.md) for what PERC is and why signoff is slow.

## What is implemented

Synthetic hierarchical netlist + resistor-mesh stand-in for extracted parasitics, then PERC-like rules:

| Check | Rule id |
|-------|---------|
| ESD clamp present on every IO pad | `ESD_CLAMP_MISSING` |
| Floating MOSFET gates | `FLOATING_GATE` |
| Pad→rail point-to-point resistance | `P2P_RESISTANCE_HIGH` / `P2P_PATH_MISSING` |
| Simplified current-density along ESD path | `CURRENT_DENSITY` |

Engines:

| Mode | Idea |
|------|------|
| `baseline` | Full-chip, every rule, every time |
| `roi` | Prune floating-gate work to ESD-relevant devices |
| `hierarchical` | Per-block floating-gate + chip-level ESD/P2P/CD |
| `parallel` | Multi-threaded pad-pair P2P/CD (`std::async`) |
| `incremental` | Metadata cache keyed by scope fingerprint |
| `optimized` | Hierarchical ROI + cache + parallel P2P/CD |

This is **not** Calibre/ICV and does not run foundry decks. Geometry/extraction are abstracted as a weighted `RGraph` (Dijkstra).

## Build

```bash
cd "PERC Runtime Optimizer"
make -j
make test
```

## Run

```bash
./perc_optimizer --pads 32 --blocks 8 --devices 400
./perc_optimizer --bench --eco --workers 8
```

Flags: `--pads`, `--blocks`, `--devices`, `--workers`, `--eco`, `--bench`.

## Layout

```
include/     design, checks, engines, generator, metadata
src/         implementations + main CLI
tests/       self-contained assertions
docs/        PERC concepts
```

## Optimization takeaway

Cold full-chip walks dominate when every MOSFET and every pad pair is visited. Speedups come from **not redoing unchanged work**: ROI nets, block scopes, fingerprint caches after ECO, and parallel P2P queries — the same levers used in production reliability flows (LDL / metadata reuse / hierarchy / multi-CPU).
