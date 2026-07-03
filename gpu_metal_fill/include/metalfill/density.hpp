#pragma once
#include <cstdint>
#include <vector>
#include "metalfill/raster.hpp"

namespace mf {

// Summed-area table (integral image) over a boolean occupancy grid. Allows O(1)
// area queries for any axis-aligned window and is the core primitive that maps
// cleanly onto a GPU (prefix sums + box lookups).
struct SummedAreaTable {
    int nx = 0;
    int ny = 0;
    std::vector<int64_t> sat;  // (ny+1) x (nx+1), row-major

    // Occupied-cell count in the half-open cell range [x0,x1) x [y0,y1).
    int64_t area(int x0, int y0, int x1, int y1) const;
};

SummedAreaTable build_sat(const Grid& grid);

// A single density evaluation window.
struct Window {
    int ix = 0, iy = 0;      // tile index
    int x0 = 0, y0 = 0;      // cell range [x0,x1) x [y0,y1)
    int x1 = 0, y1 = 0;
    double density = 0.0;     // occupied_area / window_area
};

// A grid of density windows produced by sliding a `win_cells` window with
// `step_cells` stride over the occupancy grid.
struct DensityMap {
    int ntiles_x = 0;
    int ntiles_y = 0;
    std::vector<Window> tiles;  // row-major (iy*ntiles_x + ix)

    const Window& at(int ix, int iy) const { return tiles[static_cast<size_t>(iy) * ntiles_x + ix]; }
    double min_density() const;
    double max_density() const;
    double mean_density() const;
};

// Computes the density map from a SAT. win_cells/step_cells are in grid cells.
DensityMap compute_density(const SummedAreaTable& sat, int win_cells, int step_cells);

}  // namespace mf
