# AGENTS.md

## Cursor Cloud specific instructions

This repository is a study collection of standalone C/C++ algorithm implementations
for physical-design / EDA topics (Steiner routing, MST/DSU, LCA variants, etc.).
It is **not** a single buildable application: there is no build system, package
manager, dependency manifest, test suite, or lint config. Each source file under
`Steiner Routing/` (and its subdirectories) contains its own `main()` and is
compiled and run independently.

### Toolchain
- Only a C/C++ toolchain is required. `g++`, `gcc`, `make`, and `clang++` are
  preinstalled on the base image; there is nothing to install, so the startup
  update script is just a toolchain sanity check.

### Building / running a program
- Compile a single file and run it, e.g.:
  - `g++ -std=c++17 -O2 -o /tmp/prog "Steiner Routing/kruskals_mst.cpp" && /tmp/prog`
- `Steiner Routing/dsu.cpp`, `kruskals_mst.cpp`, and `lca_tarjans/lca.cpp` print
  to stdout directly.
- `sparse_table.cpp` reads from **stdin** (RMQ queries), e.g.
  `printf "5\n2 4 3 1 5\n2\n0 4\n1 3\n" | /tmp/sparse`.

### File-I/O programs (gotcha)
- `lca1/lca.cpp`, `lca_dp/lca_dp.cpp`, `lca_timer/lca_timer.cpp`, and
  `euler_tours.cpp` use `freopen("inputs.txt", ...)` / `freopen("outputs.txt", ...)`.
  They must be compiled and run **from inside their own directory** so the relative
  `inputs.txt`/`outputs.txt` paths resolve. Running them overwrites the committed
  `outputs.txt`; `git checkout -- <path>` to restore if you don't intend to change it.
- The compiler emits harmless `-Wunused-result` warnings for the `freopen` calls.

### Other notes
- `Steiner Routing/lca_dp/a1.c` uses `sin`/`cos`; compile with `gcc a1.c -lm`.
- `Convex Hull/`, `GPU - STA/`, and `Register Clustering/` contain only PDFs /
  placeholder files — no code to build.
