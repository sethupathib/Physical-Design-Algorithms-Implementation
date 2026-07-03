# Metal Fill (FEOL / BEOL) — recursive-partitioned dummy fill

A small, dependency-free C++17 engine that inserts **dummy metal fill** into a
GDSII layout so that every layer meets CMP density rules. It processes the die by
**recursive quadtree partitioning** (like commercial fill flows) so leaves can be
filled independently and in parallel, then merged.

> Status: CPU implementation (OpenMP-parallel across partitions). The heavy
> stages are isolated behind a `FillBackend` interface so a CUDA/GPU backend can
> be added later. GPU offload is intentionally future work.

## Why dummy fill?

Chemical-Mechanical Polishing (CMP) needs a **uniform** metal density across the
die. Sparse regions dish/erode differently from dense regions, hurting yield and
timing. Foundries therefore require, per layer and per density window:

- a **minimum** density (add fill where too sparse),
- a **maximum** density (don't over-fill),
- a bounded **window-to-window gradient** (no abrupt steps),
- **spacing** from existing geometry (a keep-out halo), and a min fill area.

## Pipeline

For each layer (FEOL base: `OD`, `PO`; BEOL metals: `M1..M14`):

1. **Rasterize** existing geometry into an occupancy grid.
2. **Density** via a summed-area table (integral image): O(1) per window.
3. **Keep-out** = morphological dilation of geometry by the spacing rule.
4. **Fill** on a pitch lattice, per window, up to a per-window target density,
   never exceeding max and never entering the keep-out halo.
5. **Iterative DRC**: measure achieved density, then raise the target of any
   window that is still below `min` or too far below a denser neighbor
   (gradient), and refill. Targets increase monotonically, so it converges.

### Recursive partitioning (the scaling trick)

The die is split by a **quadtree** into leaf partitions that are filled
independently (OpenMP now, GPU later) and then merged by concatenation.

Correctness at partition boundaries is guaranteed by two things:

- **Lattice-aligned cuts**: partitions are cut on a lattice equal to
  `lcm(density_window, fill_pitch)`, so a density window and every fill position
  is identical whether computed globally or per-partition.
- **Halo / guard band**: each leaf reads a ring of neighboring geometry as
  read-only context (so density and keep-out are exact at the edge) but only
  *emits* fill inside its **core**. Cores are disjoint and tile the die, so
  merging is a plain concatenation — no de-duplication or stitching.

A unit test (`partition == global`) asserts the merged result is bit-for-bit
equivalent to a single-shot global fill.

## Build & run

```sh
make            # builds tools into build/
make test       # builds and runs the unit tests
make demo       # generate dummy.gds -> filled.gds + report.txt

# manual
build/make_dummy_gds -o build/dummy.gds
build/run_fill -i build/dummy.gds -o build/filled.gds -r build/report.txt
build/render_layer -i build/filled.gds -o build/m3.ppm -l 12   # visualize M3
```

`make OPENMP=0` builds a serial version.

## Layout of the code

| File | Responsibility |
|------|----------------|
| `include/metalfill/geometry.hpp` | points, bbox, polygons (integer dbu) |
| `gdsii.{hpp,cpp}` | minimal GDSII reader/writer (BOUNDARY/BOX) |
| `raster.{hpp,cpp}` | polygon scanline rasterization |
| `density.{hpp,cpp}` | summed-area table + windowed density |
| `fill.{hpp,cpp}` | keep-out dilation + per-window fill placement |
| `partition.{hpp,cpp}` | recursive quadtree partitioner |
| `drc.{hpp,cpp}` | density / gradient / spacing / min-area checks |
| `backend.hpp`, `backend_cpu.cpp` | compute backend (CPU/OpenMP; CUDA later) |
| `engine.{hpp,cpp}` | orchestration: partition → fill → iterate → merge |
| `layermap.{hpp,cpp}` | default GDS layers + fill rules |
| `tools/` | `make_dummy_gds`, `run_fill`, `render_layer` |
| `tests/test_main.cpp` | unit + end-to-end tests |

The default layer map and rules are illustrative, **not** a real PDK; edit
`layermap.cpp` to match your technology.
